from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.adapters.types import RawTrendVideo
from app.core.config import Settings
from app.pipelines import SelectorRunConfig, SelectorThresholds, run_selector
from app.pipelines.candidate_filter import CandidateFilterConfig, run_candidate_filter
from app.schemas.generated_images import GeneratedImageOut
from app.schemas.pipeline import PipelinePlatformRunOut, PipelineRunOut, PipelineRunRequest
from app.services.downloader import TrendDownloadService
from app.services.filesystem_store import FilesystemStore
from app.services.generated_images import GeneratedImageService
from app.services.influencers import InfluencerService
from app.services.trend_parser import TrendParserService


class PipelineRunnerService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.trends = TrendParserService(db=db, settings=settings)
        self.downloader = TrendDownloadService(db=db, settings=settings)
        self.influencers = InfluencerService(db=db, settings=settings)
        self.generated_images = GeneratedImageService(db=db, settings=settings)
        self.fs = FilesystemStore(settings=settings)

    def run(self, request: PipelineRunRequest) -> PipelineRunOut:
        influencer = self.influencers.require_ready_influencer(request.influencer_id)
        persona = self.influencers.to_persona_profile(influencer)
        enabled_platforms = [platform for platform, cfg in request.platforms.items() if cfg.enabled]
        if not enabled_platforms and not request.image.enabled:
            raise ValueError("Enable at least one platform or the image stage.")
        if enabled_platforms and request.filter.enabled and not request.download.enabled:
            raise ValueError("Filter stage requires downloads to be enabled.")
        if enabled_platforms and request.vlm.enabled and not request.filter.enabled:
            raise ValueError("Gemini stage requires filter stage to be enabled.")

        started_at = datetime.now(UTC)
        stamp = started_at.strftime("%Y%m%d_%H%M%S")
        base_dir = self.fs.influencer_pipeline_runs_dir(request.influencer_id) / stamp
        base_dir.mkdir(parents=True, exist_ok=True)

        platform_outputs: list[PipelinePlatformRunOut] = []
        generated_images: list[GeneratedImageOut] = []
        for platform, cfg in request.platforms.items():
            platform_name = platform.lower().strip()
            if not cfg.enabled:
                continue

            selector_payload = cfg.selector.model_dump()
            if not selector_payload.get("hashtags"):
                selector_payload["hashtags"] = influencer.hashtags or []

            platform_dir = base_dir / platform_name
            download_dir = platform_dir / "downloads"
            analysis_dir = platform_dir / "analysis"
            filtered_dir = platform_dir / "filtered"
            vlm_dir = platform_dir / "vlm"
            selected_dir = platform_dir / "selected"
            rejected_dir = platform_dir / "rejected"

            if self.settings.storage_mode == "filesystem":
                platform_output = self._run_platform_filesystem(
                    influencer=influencer,
                    persona=persona,
                    platform_name=platform_name,
                    selector_payload=selector_payload,
                    cfg=cfg,
                    request=request,
                    platform_dir=platform_dir,
                    download_dir=download_dir,
                    analysis_dir=analysis_dir,
                    filtered_dir=filtered_dir,
                    vlm_dir=vlm_dir,
                    selected_dir=selected_dir,
                    rejected_dir=rejected_dir,
                    stamp=stamp,
                )
                platform_outputs.append(platform_output)
                continue

            run = self.trends.ingest(
                platforms=[platform_name],
                limit_per_platform=cfg.limit,
                source=cfg.source,
                selectors={platform_name: selector_payload},
            )
            counts = Counter(item.platform for item in run.items)

            download_counts: dict[str, int] = {}
            if request.download.enabled:
                records = self.downloader.download_from_run(
                    run_id=run.id,
                    platform=platform_name,
                    limit=cfg.limit,
                    force=request.download.force,
                    download_dir=str(download_dir),
                )
                download_counts = dict(Counter(record.status for record in records))

            candidate_report_path = None
            if request.filter.enabled:
                report, report_path = run_candidate_filter(
                    CandidateFilterConfig(
                        db_path=self._candidate_filter_db_path(),
                        download_dir=download_dir,
                        report_dir=analysis_dir,
                        filtered_dir=filtered_dir,
                        probe_seconds=request.filter.probe_seconds,
                        top_k=request.filter.top_k,
                        workers=request.filter.workers,
                        sync_filtered=True,
                    )
                )
                candidate_report_path = str(report_path.resolve())
            else:
                report = None

            accepted = None
            rejected = None
            vlm_summary_path = None
            if request.vlm.enabled and request.filter.enabled:
                run_selector(
                    SelectorRunConfig(
                        input_dir=filtered_dir,
                        output_dir=vlm_dir,
                        selected_dir=selected_dir,
                        rejected_dir=rejected_dir,
                        theme=request.vlm.theme,
                        hashtags=influencer.hashtags or [],
                        model=request.vlm.model,
                        api_key_env=request.vlm.api_key_env,
                        timeout_sec=request.vlm.timeout_sec,
                        mock=request.vlm.mock,
                        max_videos=request.vlm.max_videos,
                        sync_folders=request.vlm.sync_folders,
                        thresholds=SelectorThresholds(
                            min_readiness=request.vlm.thresholds.min_readiness,
                            min_confidence=request.vlm.thresholds.min_confidence,
                            min_persona_fit=request.vlm.thresholds.min_persona_fit,
                            max_occlusion_risk=request.vlm.thresholds.max_occlusion_risk,
                            max_scene_cut_complexity=request.vlm.thresholds.max_scene_cut_complexity,
                        ),
                        persona=persona,
                        video_suggestions_requirement=influencer.video_suggestions_requirement,
                    )
                )
                summary_file = self._latest_summary(vlm_dir)
                if summary_file is not None:
                    payload = json.loads(summary_file.read_text(encoding="utf-8"))
                    accepted = int(payload.get("accepted", 0))
                    rejected = int(payload.get("rejected", 0))
                    vlm_summary_path = str(summary_file.resolve())

            platform_outputs.append(
                PipelinePlatformRunOut(
                    platform=platform_name,
                    source=cfg.source,
                    trend_run_id=run.id,
                    ingested_items=int(counts.get(platform_name, 0)),
                    download_counts=download_counts,
                    candidate_report_path=candidate_report_path,
                    filtered_dir=str(filtered_dir.resolve()) if request.filter.enabled else None,
                    vlm_summary_path=vlm_summary_path,
                    selected_dir=str(selected_dir.resolve()) if request.vlm.enabled else None,
                    accepted=accepted,
                    rejected=rejected,
                )
            )

        if request.image.enabled:
            record = self.generated_images.generate(
                influencer_id=influencer.influencer_id,
                prompt=request.image.prompt,
                picture_idea_id=request.image.picture_idea_id,
                reference_image_path=request.image.reference_image_path,
                model=request.image.model,
                api_key_env=request.image.api_key_env,
                aspect_ratio=request.image.aspect_ratio,
                hashtag_strategy=request.image.hashtag_strategy,
                hashtag_platforms=request.image.hashtag_platforms,
                trend_run_ids=request.image.trend_run_ids,
                trend_window_days=request.image.trend_window_days,
                max_hashtags=request.image.max_hashtags,
                mock=request.image.mock,
            )
            generated_images.append(GeneratedImageOut.model_validate(record))

        result = PipelineRunOut(
            influencer_id=influencer.influencer_id,
            started_at=started_at,
            base_dir=str(base_dir.resolve()),
            platforms=platform_outputs,
            generated_images=generated_images,
        )
        self.fs.save_pipeline_manifest(
            influencer.influencer_id,
            stamp,
            {
                "influencer_id": influencer.influencer_id,
                "started_at": started_at.isoformat(),
                "base_dir": str(base_dir.resolve()),
                "storage_mode": self.settings.storage_mode,
                "platforms": [item.model_dump(mode="json") for item in platform_outputs],
                "generated_images": [item.model_dump(mode="json") for item in generated_images],
                "request": request.model_dump(mode="json"),
            },
        )
        return result

    def _run_platform_filesystem(
        self,
        *,
        influencer,
        persona,
        platform_name: str,
        selector_payload: dict,
        cfg,
        request: PipelineRunRequest,
        platform_dir: Path,
        download_dir: Path,
        analysis_dir: Path,
        filtered_dir: Path,
        vlm_dir: Path,
        selected_dir: Path,
        rejected_dir: Path,
        stamp: str,
    ) -> PipelinePlatformRunOut:
        collected = self.trends.collect_raw(
            platforms=[platform_name],
            limit_per_platform=cfg.limit,
            source=cfg.source,
            selectors={platform_name: selector_payload},
        )
        videos = collected.get(platform_name, [])
        synthetic_run_id = int(datetime.now(UTC).timestamp() * 1000)

        download_records: list[dict] = []
        download_counts: dict[str, int] = {}
        if request.download.enabled:
            download_records = self.downloader.download_raw_videos(
                platform=platform_name,
                videos=videos,
                force=request.download.force,
                download_dir=str(download_dir),
            )
            download_counts = dict(Counter(record["status"] for record in download_records))

        candidate_report_path = None
        if request.filter.enabled:
            report, report_path = run_candidate_filter(
                CandidateFilterConfig(
                    db_path=Path("/nonexistent"),
                    download_dir=download_dir,
                    report_dir=analysis_dir,
                    filtered_dir=filtered_dir,
                    probe_seconds=request.filter.probe_seconds,
                    top_k=request.filter.top_k,
                    workers=request.filter.workers,
                    sync_filtered=True,
                )
            )
            candidate_report_path = str(report_path.resolve())
        else:
            report = None

        accepted = None
        rejected = None
        vlm_summary_path = None
        if request.vlm.enabled and request.filter.enabled:
            run_selector(
                SelectorRunConfig(
                    input_dir=filtered_dir,
                    output_dir=vlm_dir,
                    selected_dir=selected_dir,
                    rejected_dir=rejected_dir,
                    theme=request.vlm.theme,
                    hashtags=influencer.hashtags or [],
                    model=request.vlm.model,
                    api_key_env=request.vlm.api_key_env,
                    timeout_sec=request.vlm.timeout_sec,
                    mock=request.vlm.mock,
                    max_videos=request.vlm.max_videos,
                    sync_folders=request.vlm.sync_folders,
                    thresholds=SelectorThresholds(
                        min_readiness=request.vlm.thresholds.min_readiness,
                        min_confidence=request.vlm.thresholds.min_confidence,
                        min_persona_fit=request.vlm.thresholds.min_persona_fit,
                        max_occlusion_risk=request.vlm.thresholds.max_occlusion_risk,
                        max_scene_cut_complexity=request.vlm.thresholds.max_scene_cut_complexity,
                    ),
                    persona=persona,
                    video_suggestions_requirement=influencer.video_suggestions_requirement,
                )
            )
            summary_file = self._latest_summary(vlm_dir)
            if summary_file is not None:
                payload = json.loads(summary_file.read_text(encoding="utf-8"))
                accepted = int(payload.get("accepted", 0))
                rejected = int(payload.get("rejected", 0))
                vlm_summary_path = str(summary_file.resolve())

        manifest_payload = {
            "run_id": synthetic_run_id,
            "platform": platform_name,
            "source": cfg.source,
            "selector": selector_payload,
            "ingested_items": [self._raw_video_to_dict(video) for video in videos],
            "download_records": download_records,
            "candidate_report_path": candidate_report_path,
            "vlm_summary_path": vlm_summary_path,
            "selected_dir": str(selected_dir.resolve()) if selected_dir.exists() else None,
            "accepted": accepted,
            "rejected": rejected,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        manifest_path = platform_dir / "platform_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        return PipelinePlatformRunOut(
            platform=platform_name,
            source=cfg.source,
            trend_run_id=synthetic_run_id,
            ingested_items=len(videos),
            download_counts=download_counts,
            candidate_report_path=candidate_report_path,
            filtered_dir=str(filtered_dir.resolve()) if request.filter.enabled else None,
            vlm_summary_path=vlm_summary_path,
            selected_dir=str(selected_dir.resolve()) if request.vlm.enabled else None,
            accepted=accepted,
            rejected=rejected,
        )

    def _latest_summary(self, output_dir: Path) -> Path | None:
        summaries = sorted(output_dir.glob("vlm_summary_*.json"))
        if not summaries:
            return None
        return summaries[-1]

    def _candidate_filter_db_path(self) -> Path:
        raw = self.settings.database_url
        prefix = "sqlite+pysqlite:///"
        if raw.startswith(prefix):
            return Path(raw[len(prefix):]).expanduser()
        return Path("/nonexistent")

    def _raw_video_to_dict(self, video: RawTrendVideo) -> dict:
        return {
            "platform": video.platform,
            "source_item_id": video.source_item_id,
            "video_url": video.video_url,
            "caption": video.caption,
            "hashtags": video.hashtags,
            "audio": video.audio,
            "style_hint": video.style_hint,
            "published_at": video.published_at.isoformat() if video.published_at else None,
            "views": video.views,
            "likes": video.likes,
            "comments": video.comments,
            "shares": video.shares,
        }

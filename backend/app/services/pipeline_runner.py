from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.pipelines import SelectorRunConfig, SelectorThresholds, run_selector
from app.pipelines.candidate_filter import CandidateFilterConfig, run_candidate_filter
from app.schemas.generated_images import GeneratedImageOut
from app.schemas.pipeline import PipelinePlatformRunOut, PipelineRunOut, PipelineRunRequest
from app.services.downloader import TrendDownloadService
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
        base_dir = self.settings.pipeline_runs_data_dir / f"{request.influencer_id}_{stamp}"
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

            run = self.trends.ingest(
                platforms=[platform_name],
                limit_per_platform=cfg.limit,
                source=cfg.source,
                selectors={platform_name: selector_payload},
            )
            counts = Counter(item.platform for item in run.items)

            platform_dir = base_dir / platform_name
            download_dir = platform_dir / "downloads"
            analysis_dir = platform_dir / "analysis"
            filtered_dir = platform_dir / "filtered"
            vlm_dir = platform_dir / "vlm"
            selected_dir = platform_dir / "selected"
            rejected_dir = platform_dir / "rejected"

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
                        db_path=Path("/tmp/influencer_dev.db"),
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

        return PipelineRunOut(
            influencer_id=influencer.influencer_id,
            started_at=started_at,
            base_dir=str(base_dir.resolve()),
            platforms=platform_outputs,
            generated_images=generated_images,
        )

    def _latest_summary(self, output_dir: Path) -> Path | None:
        summaries = sorted(output_dir.glob("vlm_summary_*.json"))
        if not summaries:
            return None
        return summaries[-1]

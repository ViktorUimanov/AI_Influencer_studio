from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.schemas.generated_images import GeneratedImageOut
from app.schemas.pipeline import (
    PipelineAssetOut,
    PipelinePlatformRunDetailOut,
    PipelinePlatformRunOut,
    PipelineRunDetailOut,
    PipelineRunSummaryOut,
)
from app.services.filesystem_store import FilesystemStore


class PipelineHistoryService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.fs = FilesystemStore(settings=settings)

    def list_runs(self, influencer_id: str | None = None) -> list[PipelineRunSummaryOut]:
        summaries: list[PipelineRunSummaryOut] = []
        for manifest_path in self._iter_manifest_paths(influencer_id):
            payload = self._load_manifest(manifest_path)
            summaries.append(
                PipelineRunSummaryOut(
                    run_id=manifest_path.parent.name,
                    influencer_id=str(payload.get("influencer_id") or manifest_path.parents[1].name),
                    started_at=self._parse_dt(payload.get("started_at")),
                    base_dir=str(payload.get("base_dir") or manifest_path.parent),
                    status="Completed",
                    request=payload.get("request"),
                    platforms=[
                        PipelinePlatformRunOut.model_validate(item)
                        for item in (payload.get("platforms") or [])
                    ],
                    generated_images_count=len(payload.get("generated_images") or []),
                )
            )
        summaries.sort(key=lambda item: item.started_at, reverse=True)
        return summaries

    def get_run(self, influencer_id: str, run_id: str) -> PipelineRunDetailOut | None:
        manifest_path = self.fs.influencer_pipeline_runs_dir(influencer_id) / run_id / "run_manifest.json"
        if not manifest_path.exists():
            return None

        payload = self._load_manifest(manifest_path)
        base_dir = Path(str(payload.get("base_dir") or manifest_path.parent))
        platform_details: list[PipelinePlatformRunDetailOut] = []
        for item in payload.get("platforms") or []:
            platform = PipelinePlatformRunOut.model_validate(item)
            selected_assets = self._collect_assets(platform.selected_dir, kind="selected", platform=platform.platform)
            filtered_assets = self._collect_assets(platform.filtered_dir, kind="filtered", platform=platform.platform)
            platform_details.append(
                PipelinePlatformRunDetailOut(
                    **platform.model_dump(),
                    selected_assets=selected_assets,
                    filtered_assets=filtered_assets,
                )
            )

        generated_images = [
            GeneratedImageOut.model_validate(item)
            for item in (payload.get("generated_images") or [])
        ]
        return PipelineRunDetailOut(
            run_id=run_id,
            influencer_id=str(payload.get("influencer_id") or influencer_id),
            started_at=self._parse_dt(payload.get("started_at")),
            base_dir=str(base_dir),
            status="Completed",
            request=payload.get("request"),
            platforms=platform_details,
            generated_images_count=len(generated_images),
            generated_images=generated_images,
        )

    def _iter_manifest_paths(self, influencer_id: str | None) -> list[Path]:
        if influencer_id:
            base = self.fs.influencer_pipeline_runs_dir(influencer_id)
            return sorted(base.glob("*/run_manifest.json")) if base.exists() else []

        base = self.settings.influencers_data_dir
        if not base.exists():
            return []
        return sorted(base.glob("*/pipeline_runs/*/run_manifest.json"))

    def _load_manifest(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _collect_assets(self, directory: str | None, *, kind: str, platform: str) -> list[PipelineAssetOut]:
        if not directory:
            return []
        root = Path(directory)
        if not root.exists():
            return []

        assets: list[PipelineAssetOut] = []
        for path in sorted(root.iterdir()):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in {".mp4", ".mov", ".webm", ".mkv", ".png", ".jpg", ".jpeg", ".webp"}:
                continue
            media_type = "video" if suffix in {".mp4", ".mov", ".webm", ".mkv"} else "image"
            stat = path.stat()
            assets.append(
                PipelineAssetOut(
                    id=f"{kind}:{platform}:{path.name}",
                    name=path.name,
                    path=str(path.resolve()),
                    media_type=media_type,
                    kind=kind,
                    platform=platform,
                    size_bytes=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                )
            )
        assets.sort(key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return assets

    def _parse_dt(self, value: object) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(UTC)
        if value:
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
            except ValueError:
                pass
        return datetime.now(UTC)

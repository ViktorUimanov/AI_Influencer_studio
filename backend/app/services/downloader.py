from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import TrendDownload, TrendItem


class TrendDownloadService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    def download_item(self, item_id: int, force: bool = False, download_dir: str | None = None) -> TrendDownload:
        item = self.db.get(TrendItem, item_id)
        if item is None:
            raise ValueError(f"Trend item {item_id} not found")

        latest = self._latest_download_for_item(item_id=item.id)
        if latest and latest.status == "downloaded" and not force:
            return latest

        if not item.video_url:
            skipped = TrendDownload(
                trend_item_id=item.id,
                platform=item.platform,
                source_url="",
                status="skipped",
                downloader="yt-dlp",
                completed_at=datetime.now(UTC),
                error_message="Item has no video_url",
            )
            self.db.add(skipped)
            self.db.commit()
            self.db.refresh(skipped)
            return skipped

        record = TrendDownload(
            trend_item_id=item.id,
            platform=item.platform,
            source_url=item.video_url,
            status="running",
            downloader="yt-dlp",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        try:
            download_info = self._run_ytdlp(url=item.video_url, platform=item.platform, download_dir=download_dir)
            downloaded_path = Path(download_info["local_path"])
            path = self._rename_download_for_item(downloaded_path, item)

            record.status = "downloaded"
            record.local_path = str(path)
            record.file_ext = path.suffix.lstrip(".") or None
            record.file_size_bytes = path.stat().st_size
            record.sha256 = self._sha256(path)
            record.completed_at = datetime.now(UTC)
            record.download_metadata = {
                "stdout_tail": download_info.get("stdout_tail"),
                "stderr_tail": download_info.get("stderr_tail"),
            }
            self.db.commit()
            self.db.refresh(record)
            return record

        except Exception as exc:
            record.status = "failed"
            record.completed_at = datetime.now(UTC)
            record.error_message = str(exc)
            record.download_metadata = {
                "error_type": type(exc).__name__,
            }
            self.db.commit()
            self.db.refresh(record)
            return record

    def download_from_run(
        self,
        run_id: int,
        platform: str | None = None,
        limit: int = 20,
        force: bool = False,
        download_dir: str | None = None,
    ) -> list[TrendDownload]:
        stmt = (
            select(TrendItem)
            .where(TrendItem.run_id == run_id)
            .order_by(desc(TrendItem.trending_score), desc(TrendItem.id))
            .limit(limit)
        )
        if platform:
            stmt = stmt.where(TrendItem.platform == platform.lower())

        items = list(self.db.scalars(stmt))
        return [self.download_item(item_id=item.id, force=force, download_dir=download_dir) for item in items]

    def list_downloads(
        self,
        run_id: int | None = None,
        platform: str | None = None,
        status: str | None = None,
        trend_item_id: int | None = None,
        limit: int = 100,
    ) -> list[TrendDownload]:
        stmt = select(TrendDownload).join(TrendItem).order_by(desc(TrendDownload.id)).limit(limit)

        if trend_item_id:
            stmt = stmt.where(TrendDownload.trend_item_id == trend_item_id)
        if run_id:
            stmt = stmt.where(TrendItem.run_id == run_id)
        if platform:
            stmt = stmt.where(TrendDownload.platform == platform.lower())
        if status:
            stmt = stmt.where(TrendDownload.status == status.lower())

        return list(self.db.scalars(stmt))

    def _latest_download_for_item(self, item_id: int) -> TrendDownload | None:
        stmt = (
            select(TrendDownload)
            .where(TrendDownload.trend_item_id == item_id)
            .order_by(desc(TrendDownload.id))
            .limit(1)
        )
        return self.db.scalar(stmt)

    def _run_ytdlp(self, url: str, platform: str, download_dir: str | None = None) -> dict:
        command = self.settings.yt_dlp_command.strip()
        if not command:
            raise RuntimeError("YT_DLP_COMMAND is empty")

        command_parts = shlex.split(command)
        binary = command_parts[0]
        resolved_binary = self._resolve_downloader_binary(binary)
        command_parts[0] = resolved_binary

        base_dir = self._resolve_download_dir(download_dir=download_dir)
        platform_dir = base_dir / platform
        platform_dir.mkdir(parents=True, exist_ok=True)

        output_template = str(platform_dir / "%(extractor)s_%(id)s.%(ext)s")
        args = [
            *command_parts,
            "--no-progress",
            "--newline",
            "--no-playlist",
            "--restrict-filenames",
            "--format",
            self.settings.yt_dlp_format,
            "--merge-output-format",
            self.settings.yt_dlp_merge_format,
            "--print",
            "after_move:filepath",
            "--output",
            output_template,
            url,
        ]

        cookie_file = self.settings.yt_dlp_cookies_file
        if cookie_file:
            cookie_path = Path(cookie_file).expanduser()
            if cookie_path.exists():
                args[1:1] = ["--cookies", str(cookie_path)]

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=self.settings.download_timeout_sec,
            env=os.environ.copy(),
        )

        stdout_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        stderr_lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]

        if result.returncode != 0:
            tail = "\n".join(stderr_lines[-4:] or stdout_lines[-4:])
            raise RuntimeError(f"yt-dlp failed: {tail}")

        local_path = stdout_lines[-1] if stdout_lines else ""
        if not local_path:
            raise RuntimeError("yt-dlp did not return a file path")

        path = Path(local_path)
        if not path.exists():
            raise RuntimeError(f"Downloaded file does not exist: {path}")

        return {
            "local_path": str(path),
            "stdout_tail": stdout_lines[-5:],
            "stderr_tail": stderr_lines[-5:],
        }

    def _sha256(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with file_path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def _resolve_download_dir(self, download_dir: str | None) -> Path:
        if download_dir:
            return Path(download_dir).expanduser().resolve()
        return self.settings.downloads_data_dir.resolve()

    def _resolve_downloader_binary(self, binary: str) -> str:
        binary_path = Path(binary).expanduser()
        if binary_path.is_file():
            return str(binary_path.resolve())

        resolved = shutil.which(binary)
        if resolved:
            return resolved

        if binary == "yt-dlp":
            # Prefer the currently running virtualenv's yt-dlp when PATH is not configured.
            candidates = [
                Path(sys.executable).with_name("yt-dlp"),
                Path(sys.executable).resolve().parent / "yt-dlp",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return str(candidate)

        raise RuntimeError(
            f"Downloader '{binary}' not found in PATH. Install yt-dlp and/or update YT_DLP_COMMAND"
        )

    def _rename_download_for_item(self, downloaded_path: Path, item: TrendItem) -> Path:
        if not downloaded_path.exists():
            raise RuntimeError(f"Downloaded file does not exist: {downloaded_path}")

        suffix = downloaded_path.suffix or ".mp4"
        target_name = self._build_item_filename(item=item, suffix=suffix)
        if downloaded_path.name == target_name:
            return downloaded_path

        target_path = downloaded_path.with_name(target_name)
        if target_path.exists():
            target_path.unlink()
        downloaded_path.rename(target_path)
        return target_path

    def _build_item_filename(self, item: TrendItem, suffix: str) -> str:
        date_part = (
            item.published_at.astimezone(UTC).strftime("%Y%m%d")
            if item.published_at
            else "unknown"
        )
        views_part = str(max(0, int(item.views or 0)))
        source_uid = self._sanitize_token(item.source_item_id or "")
        if not source_uid:
            fallback_seed = item.video_url or f"{item.platform}-{item.id}"
            source_uid = hashlib.sha1(fallback_seed.encode("utf-8")).hexdigest()[:12]

        return f"{item.platform}_{date_part}_views{views_part}_uid{source_uid}{suffix}"

    def _sanitize_token(self, raw: str, limit: int = 64) -> str:
        token = re.sub(r"[^a-zA-Z0-9_-]+", "", str(raw or ""))
        return token[:limit]

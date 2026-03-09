#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.pipelines.candidate_filter import CandidateFilterConfig, run_candidate_filter
from app.pipelines.selector import resolve_project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run candidate filtering pipeline for substitution-ready videos.")
    parser.add_argument(
        "--db-path",
        default="/tmp/influencer_dev.db",
        help="Path to SQLite database with trend_downloads/trend_items metadata.",
    )
    parser.add_argument(
        "--download-dir",
        default="backend/data/downloads",
        help="Fallback directory scan when DB is missing/empty.",
    )
    parser.add_argument("--probe-seconds", type=int, default=12, help="Analyze only first N seconds per video.")
    parser.add_argument("--top-k", type=int, default=8, help="How many best candidates to output.")
    parser.add_argument("--report-dir", default="backend/data/analysis", help="Directory for JSON report output.")
    parser.add_argument(
        "--filtered-dir",
        default="backend/data/tmp/filtered",
        help="Folder to sync top candidates for next VLM stage.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel worker count for video analysis (ffmpeg/ffprobe).",
    )
    parser.add_argument("--no-sync-filtered", action="store_true", help="Do not sync top candidates into filtered dir.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = CandidateFilterConfig(
        db_path=resolve_project_path(args.db_path),
        download_dir=resolve_project_path(args.download_dir),
        report_dir=resolve_project_path(args.report_dir),
        filtered_dir=resolve_project_path(args.filtered_dir),
        probe_seconds=max(3, int(args.probe_seconds)),
        top_k=max(1, int(args.top_k)),
        sync_filtered=not args.no_sync_filtered,
        workers=max(1, int(args.workers)),
    )

    try:
        report, report_path = run_candidate_filter(config)
    except RuntimeError as exc:
        print(f"[pipeline] {exc}")
        return 1

    print("\n=== TOP CANDIDATES ===")
    for idx, row in enumerate(report["top_candidates"], start=1):
        print(
            f"{idx:02d}. score={row['scores']['final']:.4f} "
            f"platform={row['platform']:<10} "
            f"views={row['views']:<8d} "
            f"cuts/min={row['derived']['scene_cuts_per_min']:<6} "
            f"motion={row['analysis'].get('motion_avg')} "
            f"file={row['file_name']}"
        )

    print("\n=== SUMMARY ===")
    print(
        f"processed={report['processed_ok']} accepted={report['accepted']} "
        f"rejected={report['rejected']} errors={report['errors']} "
        f"elapsed_sec={report.get('elapsed_sec')} avg_video_sec={report.get('avg_video_sec')}"
    )
    print(f"report: {report_path.resolve()}")
    if config.sync_filtered:
        print(f"filtered synced: {config.filtered_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

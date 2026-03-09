#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.db.base import Base
from app.db.migrations import run_prototype_migrations
from app.db.session import SessionLocal, engine
from app.pipelines import (
    SelectorRunConfig,
    SelectorThresholds,
    load_persona,
    resolve_project_path,
    run_selector,
)
from app.pipelines.candidate_filter import CandidateFilterConfig, run_candidate_filter
from app.services.downloader import TrendDownloadService
from app.services.trend_parser import TrendParserService


HEALTH_HASHTAGS = [
    "healthylifestyle",
    "wellness",
    "fitness",
    "selfcare",
    "healthyhabits",
    "nutrition",
    "mealprep",
    "healthtips",
    "mentalwellness",
    "hydration",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Strict health pipeline: parse 50 -> download -> custom filter -> Gemini selector"
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--source", default="apify", choices=["apify", "seed"])
    parser.add_argument("--min-views", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--probe-seconds", type=int, default=8)
    parser.add_argument("--top-k", type=int, default=20)

    parser.add_argument("--download-dir", default="backend/data/downloads")
    parser.add_argument("--report-dir", default="backend/data/analysis")
    parser.add_argument("--filtered-dir", default="backend/data/tmp/filtered")
    parser.add_argument("--output-dir", default="backend/data/analysis/vlm")
    parser.add_argument("--selected-dir", default="backend/data/tmp/selected")
    parser.add_argument("--rejected-dir", default="backend/data/tmp/rejected")

    parser.add_argument("--theme", default="healthy lifestyle channel")
    parser.add_argument("--persona-file", default="backend/data/personas/default_persona.json")
    parser.add_argument("--model", default="gemini-3.1-flash-lite-preview")
    parser.add_argument("--api-key-env", default="GEMINI_API_KEY")
    parser.add_argument("--timeout-sec", type=int, default=300)
    parser.add_argument("--mock", action="store_true")

    parser.add_argument("--min-readiness", type=float, default=7.0)
    parser.add_argument("--min-confidence", type=float, default=0.70)
    parser.add_argument("--min-persona-fit", type=float, default=6.5)
    parser.add_argument("--max-occlusion-risk", type=float, default=6.0)
    parser.add_argument("--max-scene-cut-complexity", type=float, default=6.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    limit = max(1, int(args.limit))

    Base.metadata.create_all(bind=engine)
    run_prototype_migrations(engine)

    settings = get_settings()
    print(f"[health-main] source={args.source} limit={limit}")
    print(f"[health-main] hashtags={HEALTH_HASHTAGS}")

    db = SessionLocal()
    try:
        parser = TrendParserService(db=db, settings=settings)
        run = parser.ingest(
            platforms=["tiktok"],
            limit_per_platform=limit,
            source=args.source,
            selectors={
                "tiktok": {
                    "mode": "hashtag",
                    "hashtags": HEALTH_HASHTAGS,
                    "min_views": int(args.min_views),
                }
            },
        )
        print(f"[health-main] ingest_run_id={run.id} items={len(run.items)}")

        downloader = TrendDownloadService(db=db, settings=settings)
        records = downloader.download_from_run(
            run_id=run.id,
            platform="tiktok",
            limit=limit,
            force=False,
            download_dir=str(resolve_project_path(args.download_dir)),
        )
        counts = {}
        for rec in records:
            counts[rec.status] = counts.get(rec.status, 0) + 1
        print(f"[health-main] download_status={counts}")

    finally:
        db.close()

    filter_config = CandidateFilterConfig(
        db_path=resolve_project_path("/tmp/influencer_dev.db"),
        download_dir=resolve_project_path(args.download_dir),
        report_dir=resolve_project_path(args.report_dir),
        filtered_dir=resolve_project_path(args.filtered_dir),
        probe_seconds=max(3, int(args.probe_seconds)),
        top_k=max(1, int(args.top_k)),
        workers=max(1, int(args.workers)),
        sync_filtered=True,
    )
    report, report_path = run_candidate_filter(filter_config)
    print(f"[health-main] candidate_report={report_path.resolve()}")
    print(
        f"[health-main] filter_summary processed={report['processed_ok']} "
        f"accepted={report['accepted']} elapsed_sec={report.get('elapsed_sec')}"
    )

    persona = load_persona(resolve_project_path(args.persona_file))
    selector_config = SelectorRunConfig(
        input_dir=filter_config.filtered_dir,
        output_dir=resolve_project_path(args.output_dir),
        selected_dir=resolve_project_path(args.selected_dir),
        rejected_dir=resolve_project_path(args.rejected_dir),
        theme=args.theme,
        hashtags=HEALTH_HASHTAGS,
        model=args.model,
        api_key_env=args.api_key_env,
        timeout_sec=int(args.timeout_sec),
        mock=bool(args.mock),
        max_videos=max(1, int(args.top_k)),
        sync_folders=True,
        thresholds=SelectorThresholds(
            min_readiness=float(args.min_readiness),
            min_confidence=float(args.min_confidence),
            min_persona_fit=float(args.min_persona_fit),
            max_occlusion_risk=float(args.max_occlusion_risk),
            max_scene_cut_complexity=float(args.max_scene_cut_complexity),
        ),
        persona=persona,
    )
    return run_selector(selector_config)


if __name__ == "__main__":
    raise SystemExit(main())

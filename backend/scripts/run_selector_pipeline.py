#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.pipelines import (
    SelectorRunConfig,
    SelectorThresholds,
    parse_hashtags,
    resolve_persona,
    resolve_project_path,
    run_selector,
)
from app.db.base import Base
from app.db.migrations import run_prototype_migrations
from app.db.session import SessionLocal, engine
from app.pipelines.candidate_filter import CandidateFilterConfig, run_candidate_filter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run end-to-end selector pipeline: candidates -> filtered -> selected/rejected")

    parser.add_argument("--db-path", default="/tmp/influencer_dev.db")
    parser.add_argument("--download-dir", default="backend/data/downloads")
    parser.add_argument("--probe-seconds", type=int, default=12)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--top-k", type=int, default=15)
    parser.add_argument("--report-dir", default="backend/data/analysis")
    parser.add_argument("--filtered-dir", default="backend/data/tmp/filtered")

    parser.add_argument("--output-dir", default="backend/data/analysis/vlm")
    parser.add_argument("--selected-dir", default="backend/data/tmp/selected")
    parser.add_argument("--rejected-dir", default="backend/data/tmp/rejected")

    parser.add_argument("--theme", default="healthy lifestyle channel")
    parser.add_argument("--hashtags", default="")
    parser.add_argument("--persona-file", default="backend/data/personas/default_persona.json")
    parser.add_argument("--persona-id", default="")
    parser.add_argument("--no-persona", action="store_true")

    parser.add_argument("--model", default="gemini-3.1-flash-lite-preview")
    parser.add_argument("--api-key-env", default="GEMINI_API_KEY")
    parser.add_argument("--timeout-sec", type=int, default=240)
    parser.add_argument("--mock", action="store_true")

    parser.add_argument("--min-readiness", type=float, default=7.0)
    parser.add_argument("--min-confidence", type=float, default=0.70)
    parser.add_argument("--min-persona-fit", type=float, default=6.5)
    parser.add_argument("--max-occlusion-risk", type=float, default=6.0)
    parser.add_argument("--max-scene-cut-complexity", type=float, default=6.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    filter_config = CandidateFilterConfig(
        db_path=resolve_project_path(args.db_path),
        download_dir=resolve_project_path(args.download_dir),
        report_dir=resolve_project_path(args.report_dir),
        filtered_dir=resolve_project_path(args.filtered_dir),
        probe_seconds=max(3, int(args.probe_seconds)),
        workers=max(1, int(args.workers)),
        top_k=max(1, int(args.top_k)),
        sync_filtered=True,
    )

    try:
        _, report_path = run_candidate_filter(filter_config)
    except RuntimeError as exc:
        print(f"[selector-pipeline] candidate filter failed: {exc}")
        return 1

    persona = None
    if not args.no_persona:
        Base.metadata.create_all(bind=engine)
        run_prototype_migrations(engine)
        persona_path = resolve_project_path(args.persona_file) if args.persona_file else None
        db = SessionLocal()
        try:
            persona = resolve_persona(
                db=db,
                persona_id=args.persona_id,
                persona_path=persona_path,
                prefer_db=True,
                sync_file_to_db=True,
            )
        finally:
            db.close()

    selector_config = SelectorRunConfig(
        input_dir=filter_config.filtered_dir,
        output_dir=resolve_project_path(args.output_dir),
        selected_dir=resolve_project_path(args.selected_dir),
        rejected_dir=resolve_project_path(args.rejected_dir),
        theme=args.theme,
        hashtags=parse_hashtags(args.hashtags),
        model=args.model,
        api_key_env=args.api_key_env,
        timeout_sec=args.timeout_sec,
        mock=args.mock,
        max_videos=max(1, int(args.top_k)),
        sync_folders=True,
        thresholds=SelectorThresholds(
            min_readiness=args.min_readiness,
            min_confidence=args.min_confidence,
            min_persona_fit=args.min_persona_fit,
            max_occlusion_risk=args.max_occlusion_risk,
            max_scene_cut_complexity=args.max_scene_cut_complexity,
        ),
        persona=persona,
    )

    print(f"[selector-pipeline] candidate report: {report_path.resolve()}")
    return run_selector(selector_config)


if __name__ == "__main__":
    raise SystemExit(main())

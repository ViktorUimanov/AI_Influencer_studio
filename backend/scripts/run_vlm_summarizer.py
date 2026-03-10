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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Gemini-based VLM summarizer for substitution suitability.")
    parser.add_argument("--input-dir", default="backend/data/tmp/filtered")
    parser.add_argument("--output-dir", default="backend/data/analysis/vlm")
    parser.add_argument("--selected-dir", default="backend/data/tmp/selected")
    parser.add_argument("--rejected-dir", default="backend/data/tmp/rejected")
    parser.add_argument("--sync-folders", action="store_true")

    parser.add_argument("--theme", default="healthy lifestyle channel")
    parser.add_argument("--hashtags", default="")
    parser.add_argument("--persona-file", default="backend/data/personas/default_persona.json")
    parser.add_argument("--persona-id", default="")
    parser.add_argument("--max-videos", type=int, default=15)

    parser.add_argument("--model", default="gemini-3.1-flash-lite-preview")
    parser.add_argument("--api-key-env", default="GEMINI_API_KEY")
    parser.add_argument("--timeout-sec", type=int, default=240)
    parser.add_argument("--mock", action="store_true")

    parser.add_argument("--min-readiness", type=float, default=7.0)
    parser.add_argument("--min-confidence", type=float, default=0.70)
    parser.add_argument("--min-persona-fit", type=float, default=6.5)
    parser.add_argument("--max-occlusion-risk", type=float, default=6.0)
    parser.add_argument("--max-scene-cut-complexity", type=float, default=6.0)
    parser.add_argument(
        "--no-persona",
        action="store_true",
        help="Disable persona-aware scoring and prompt block.",
    )
    return parser.parse_args()


def run(args: argparse.Namespace) -> int:
    persona = None
    if not args.no_persona and (args.persona_file or args.persona_id):
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

    config = SelectorRunConfig(
        input_dir=resolve_project_path(args.input_dir),
        output_dir=resolve_project_path(args.output_dir),
        selected_dir=resolve_project_path(args.selected_dir),
        rejected_dir=resolve_project_path(args.rejected_dir),
        theme=args.theme,
        hashtags=parse_hashtags(args.hashtags),
        model=args.model,
        api_key_env=args.api_key_env,
        timeout_sec=args.timeout_sec,
        mock=args.mock,
        max_videos=args.max_videos,
        sync_folders=args.sync_folders,
        thresholds=SelectorThresholds(
            min_readiness=args.min_readiness,
            min_confidence=args.min_confidence,
            min_persona_fit=args.min_persona_fit,
            max_occlusion_risk=args.max_occlusion_risk,
            max_scene_cut_complexity=args.max_scene_cut_complexity,
        ),
        persona=persona,
    )
    return run_selector(config)


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))

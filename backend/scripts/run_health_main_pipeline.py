#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import os
import re
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
    resolve_persona,
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

HEALTH_SEARCH_TERMS = [
    "healthy lifestyle",
    "wellness routine",
    "nutrition tips",
    "fitness routine",
    "meal prep",
]

SUPPORTED_PLATFORMS = {"tiktok", "instagram"}


def _parse_platforms(raw: str) -> list[str]:
    items = [p.strip().lower() for p in (raw or "").split(",") if p.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in SUPPORTED_PLATFORMS and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _topic_terms(topic: str, max_terms: int = 3) -> list[str]:
    normalized = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (topic or "").lower())).strip()
    terms: list[str] = []
    if normalized:
        terms.append(normalized)
    terms.extend(HEALTH_SEARCH_TERMS)
    uniq: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(term)
    return uniq[: max(1, int(max_terms))]


def _csv_terms(raw: str) -> list[str]:
    items = [item.strip() for item in (raw or "").split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower().lstrip("#").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Health pipeline: parse/download (TikTok+Instagram) -> custom filter -> Gemini selector"
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--platforms", default="tiktok")
    parser.add_argument("--topic", default="healthy lifestyle")
    parser.add_argument("--hashtags", default="")
    parser.add_argument("--search-terms", default="")
    parser.add_argument(
        "--source",
        default="tiktok_custom",
        choices=["tiktok_custom", "instagram_custom", "apify", "seed"],
    )
    parser.add_argument("--min-views", type=int, default=10000, help="TikTok minimum views.")
    parser.add_argument("--instagram-min-views", type=int, default=0)
    parser.add_argument("--instagram-min-likes", type=int, default=500)
    parser.add_argument("--recent-days", type=int, default=45)
    parser.add_argument("--strict-topic-match", dest="strict_topic_match", action="store_true", default=True)
    parser.add_argument("--no-strict-topic-match", dest="strict_topic_match", action="store_false")
    parser.add_argument("--apify-cost-optimized", dest="apify_cost_optimized", action="store_true", default=None)
    parser.add_argument("--no-apify-cost-optimized", dest="apify_cost_optimized", action="store_false")
    parser.add_argument("--db-path", default="/tmp/influencer_dev.db")
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
    parser.add_argument("--persona-id", default="")
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
    total_limit = max(1, int(args.limit))
    platforms = _parse_platforms(args.platforms)
    if not platforms:
        raise SystemExit("No supported platforms in --platforms. Use tiktok and/or instagram.")
    if args.source == "tiktok_custom":
        platforms = [p for p in platforms if p == "tiktok"]
        if not platforms:
            raise SystemExit("source=tiktok_custom supports only TikTok; include tiktok in --platforms.")
    if args.source == "instagram_custom":
        platforms = [p for p in platforms if p == "instagram"]
        if not platforms:
            raise SystemExit("source=instagram_custom supports only Instagram; include instagram in --platforms.")
    per_platform_limit = max(1, int(math.ceil(total_limit / len(platforms))))
    recent_days = max(1, int(args.recent_days))
    hashtags = _csv_terms(args.hashtags) or list(HEALTH_HASHTAGS)
    topic_terms = _csv_terms(args.search_terms) or _topic_terms(args.topic)

    Base.metadata.create_all(bind=engine)
    run_prototype_migrations(engine)

    if args.apify_cost_optimized is not None:
        os.environ["APIFY_COST_OPTIMIZED"] = "true" if args.apify_cost_optimized else "false"
    settings = get_settings()
    print(f"[health-main] source={args.source} total_limit={total_limit} per_platform_limit={per_platform_limit}")
    print(f"[health-main] platforms={platforms}")
    print(f"[health-main] topic={args.topic!r} terms={topic_terms}")
    print(f"[health-main] recent_days={recent_days}")
    print(f"[health-main] strict_topic_match={bool(args.strict_topic_match)}")
    print(f"[health-main] apify_cost_optimized={bool(settings.apify_cost_optimized)}")
    print(f"[health-main] hashtags={hashtags}")

    selectors: dict[str, dict] = {}
    if "tiktok" in platforms:
        selectors["tiktok"] = {
            "mode": "mixed",
            "hashtags": hashtags,
            "search_terms": topic_terms,
            "min_views": int(args.min_views),
            "published_within_days": recent_days,
            "require_topic_match": bool(args.strict_topic_match),
        }
    if "instagram" in platforms:
        selectors["instagram"] = {
            "mode": "mixed",
            "hashtags": hashtags,
            "search_terms": topic_terms,
            "min_views": max(0, int(args.instagram_min_views)),
            "min_likes": max(0, int(args.instagram_min_likes)),
            "published_within_days": recent_days,
            "require_topic_match": bool(args.strict_topic_match),
            "source_params": {"resultsType": "reels"},
        }

    db = SessionLocal()
    try:
        parser = TrendParserService(db=db, settings=settings)
        run = parser.ingest(
            platforms=platforms,
            limit_per_platform=per_platform_limit,
            source=args.source,
            selectors=selectors,
        )
        platform_counts: dict[str, int] = {}
        for item in run.items:
            platform_counts[item.platform] = platform_counts.get(item.platform, 0) + 1
        print(f"[health-main] ingest_run_id={run.id} items={len(run.items)} by_platform={platform_counts}")
        if not run.items:
            print(
                "[health-main] no items ingested. Try broader topic/hashtags, larger --recent-days, "
                "or disable strict topic match."
            )
            return 1

        downloader = TrendDownloadService(db=db, settings=settings)
        all_counts: dict[str, dict[str, int]] = {}
        downloaded_total = 0
        for platform in platforms:
            records = downloader.download_from_run(
                run_id=run.id,
                platform=platform,
                limit=per_platform_limit,
                force=False,
                download_dir=str(resolve_project_path(args.download_dir)),
            )
            counts: dict[str, int] = {}
            for rec in records:
                counts[rec.status] = counts.get(rec.status, 0) + 1
            all_counts[platform] = counts
            downloaded_total += counts.get("downloaded", 0) + counts.get("skipped", 0)
        print(f"[health-main] download_status_by_platform={all_counts}")
        if downloaded_total == 0:
            print("[health-main] no downloadable videos found for this run; aborting before filter stage.")
            return 1

    finally:
        db.close()

    filter_config = CandidateFilterConfig(
        db_path=resolve_project_path(args.db_path),
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

    persona_db = SessionLocal()
    try:
        persona = resolve_persona(
            db=persona_db,
            persona_id=args.persona_id,
            persona_path=resolve_project_path(args.persona_file) if args.persona_file else None,
            prefer_db=True,
            sync_file_to_db=True,
        )
    finally:
        persona_db.close()
    selector_config = SelectorRunConfig(
        input_dir=filter_config.filtered_dir,
        output_dir=resolve_project_path(args.output_dir),
        selected_dir=resolve_project_path(args.selected_dir),
        rejected_dir=resolve_project_path(args.rejected_dir),
        theme=args.theme,
        hashtags=hashtags,
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

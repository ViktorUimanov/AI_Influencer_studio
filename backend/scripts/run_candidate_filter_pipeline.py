#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class Candidate:
    path: Path
    platform: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0


def _run(cmd: list[str], timeout_sec: int = 90) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"command timed out after {timeout_sec}s: {' '.join(cmd[:4])} ...") from exc


def _safe_float(value: str | None, default: float = 0.0) -> float:
    if not value:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: str | None, default: int = 0) -> int:
    if not value:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _parse_fps(raw: str | None) -> float:
    if not raw:
        return 0.0
    if "/" in raw:
        n, d = raw.split("/", 1)
        den = _safe_float(d, 1.0)
        if den == 0:
            return 0.0
        return _safe_float(n, 0.0) / den
    return _safe_float(raw, 0.0)


def _load_candidates_from_db(db_path: Path) -> list[Candidate]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                d.local_path,
                d.platform,
                COALESCE(i.views, 0) AS views,
                COALESCE(i.likes, 0) AS likes,
                COALESCE(i.comments, 0) AS comments,
                COALESCE(i.shares, 0) AS shares
            FROM trend_downloads d
            LEFT JOIN trend_items i ON i.id = d.trend_item_id
            WHERE d.status = 'downloaded' AND d.local_path IS NOT NULL
            ORDER BY d.id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    seen: set[str] = set()
    output: list[Candidate] = []
    for row in rows:
        local_path = str(row["local_path"] or "").strip()
        if not local_path or local_path in seen:
            continue
        seen.add(local_path)
        path = Path(local_path)
        if not path.exists():
            continue
        output.append(
            Candidate(
                path=path,
                platform=str(row["platform"] or "unknown"),
                views=_safe_int(str(row["views"])),
                likes=_safe_int(str(row["likes"])),
                comments=_safe_int(str(row["comments"])),
                shares=_safe_int(str(row["shares"])),
            )
        )
    return output


def _scan_download_dir(download_dir: Path) -> list[Candidate]:
    if not download_dir.exists():
        return []
    patterns = ["*.mp4", "*.mov", "*.mkv", "*.webm"]
    out: list[Candidate] = []
    for pattern in patterns:
        for path in download_dir.rglob(pattern):
            platform = path.parent.name
            out.append(Candidate(path=path, platform=platform))
    return sorted(out, key=lambda c: str(c.path))


def _probe_video(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video_stream:
        raise RuntimeError("no video stream found")

    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    duration = _safe_float(
        str(video_stream.get("duration") or payload.get("format", {}).get("duration") or "0"),
        0.0,
    )
    fps = _parse_fps(video_stream.get("avg_frame_rate"))
    bit_rate = _safe_int(
        str(video_stream.get("bit_rate") or payload.get("format", {}).get("bit_rate") or "0"),
        0,
    )

    return {
        "duration_sec": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "bit_rate": bit_rate,
        "has_audio": audio_stream is not None,
    }


def _analyze_motion(path: Path, probe_seconds: int) -> float | None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-v",
        "info",
        "-i",
        str(path),
        "-t",
        str(probe_seconds),
        "-vf",
        "vmafmotion",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = _run(cmd)
    text = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"VMAF Motion avg:\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    return _safe_float(match.group(1), 0.0)


def _analyze_scene_cuts(path: Path, probe_seconds: int, threshold: float = 12.0) -> int:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-v",
        "info",
        "-i",
        str(path),
        "-t",
        str(probe_seconds),
        "-vf",
        f"scdet=t={threshold}",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = _run(cmd)
    text = f"{result.stdout}\n{result.stderr}"
    return len(re.findall(r"lavfi\.scd\.score:\s*[0-9.]+", text))


def _analyze_blur(path: Path, probe_seconds: int) -> float | None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-v",
        "info",
        "-i",
        str(path),
        "-t",
        str(probe_seconds),
        "-vf",
        "blurdetect",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = _run(cmd)
    text = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"blur mean:\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    return _safe_float(match.group(1), 0.0)


def _score_candidate(record: dict, max_virality: float) -> dict:
    width = int(record["metrics"]["width"])
    height = int(record["metrics"]["height"])
    duration = float(record["metrics"]["duration_sec"])
    fps = float(record["metrics"]["fps"])
    bit_rate = int(record["metrics"]["bit_rate"])
    has_audio = bool(record["metrics"]["has_audio"])

    motion = record["analysis"].get("motion_avg")
    blur_mean = record["analysis"].get("blur_mean")
    scene_cuts = int(record["analysis"].get("scene_cuts", 0))

    analyzed_duration = max(1.0, float(record["analysis"].get("analyzed_duration_sec", duration)))
    scene_cuts_per_min = scene_cuts / (analyzed_duration / 60.0)
    aspect_ratio = (height / width) if width else 0.0

    reject_reasons: list[str] = []
    if duration < 4.0:
        reject_reasons.append("too_short")
    if width < 480 or height < 480:
        reject_reasons.append("low_resolution")
    if scene_cuts_per_min > 24:
        reject_reasons.append("too_many_scene_cuts")
    if motion is not None and motion > 22:
        reject_reasons.append("too_much_motion")
    if blur_mean is not None and blur_mean > 10:
        reject_reasons.append("too_blurry")

    resolution_score = _clamp01((width * height) / (1080 * 1920))
    bitrate_mbps = bit_rate / 1_000_000 if bit_rate > 0 else 0.0
    bitrate_score = _clamp01(bitrate_mbps / 2.0)
    fps_score = _clamp01(fps / 30.0) if fps >= 15 else _clamp01((fps / 15.0) * 0.5)
    blur_score = 0.55 if blur_mean is None else _clamp01(1.0 - (blur_mean / 12.0))

    quality_score = (
        0.35 * resolution_score
        + 0.25 * bitrate_score
        + 0.20 * fps_score
        + 0.20 * blur_score
    )

    cut_stability_score = _clamp01(1.0 - (scene_cuts_per_min / 20.0))
    motion_stability_score = 0.6 if motion is None else _clamp01(1.0 - (motion / 18.0))
    temporal_stability = 0.6 * cut_stability_score + 0.4 * motion_stability_score

    duration_score = _clamp01(1.0 - abs(duration - 12.0) / 12.0)
    orientation_score = 1.0 if aspect_ratio >= 1.4 else 0.45
    swap_compatibility = 0.7 * duration_score + 0.3 * orientation_score

    virality_raw = math.log1p(record["views"]) + 0.3 * math.log1p(
        max(0, record["likes"]) + max(0, record["comments"]) + max(0, record["shares"])
    )
    virality_score = _clamp01(virality_raw / max_virality) if max_virality > 0 else 0.0

    if not has_audio:
        quality_score *= 0.9

    final_score = (
        0.35 * quality_score
        + 0.25 * temporal_stability
        + 0.20 * swap_compatibility
        + 0.20 * virality_score
    )

    return {
        "scores": {
            "quality": round(quality_score, 4),
            "temporal_stability": round(temporal_stability, 4),
            "swap_compatibility": round(swap_compatibility, 4),
            "virality": round(virality_score, 4),
            "final": round(final_score, 4),
        },
        "derived": {
            "aspect_ratio_h_over_w": round(aspect_ratio, 4) if aspect_ratio else 0.0,
            "scene_cuts_per_min": round(scene_cuts_per_min, 3),
            "bitrate_mbps": round(bitrate_mbps, 3),
        },
        "reject_reasons": reject_reasons,
        "hard_reject": len(reject_reasons) > 0,
    }


def run_pipeline(
    candidates: list[Candidate],
    probe_seconds: int,
    top_k: int,
    report_path: Path,
) -> dict:
    analyzed: list[dict] = []
    print(f"[pipeline] analyzing {len(candidates)} videos (probe_seconds={probe_seconds}) ...", flush=True)
    for idx, item in enumerate(candidates, start=1):
        print(f"[{idx}/{len(candidates)}] {item.path.name}", flush=True)
        record: dict = {
            "path": str(item.path),
            "file_name": item.path.name,
            "platform": item.platform,
            "views": item.views,
            "likes": item.likes,
            "comments": item.comments,
            "shares": item.shares,
            "metrics": {},
            "analysis": {},
            "status": "ok",
            "error": None,
        }
        try:
            metrics = _probe_video(item.path)
            analyzed_duration = min(float(metrics["duration_sec"]), float(probe_seconds))
            motion = _analyze_motion(item.path, probe_seconds=int(max(3, analyzed_duration)))
            scene_cuts = _analyze_scene_cuts(item.path, probe_seconds=int(max(3, analyzed_duration)))
            blur = _analyze_blur(item.path, probe_seconds=int(max(3, analyzed_duration)))

            record["metrics"] = metrics
            record["analysis"] = {
                "analyzed_duration_sec": round(analyzed_duration, 3),
                "motion_avg": None if motion is None else round(motion, 4),
                "scene_cuts": scene_cuts,
                "blur_mean": None if blur is None else round(blur, 4),
            }
        except Exception as exc:
            record["status"] = "error"
            record["error"] = str(exc)
        analyzed.append(record)

    ok_records = [r for r in analyzed if r["status"] == "ok"]
    virality_values = [
        math.log1p(r["views"]) + 0.3 * math.log1p(max(0, r["likes"]) + max(0, r["comments"]) + max(0, r["shares"]))
        for r in ok_records
    ]
    max_virality = max(virality_values) if virality_values else 0.0

    for record in ok_records:
        decision = _score_candidate(record, max_virality=max_virality)
        record.update(decision)

    accepted = [r for r in ok_records if not r.get("hard_reject")]
    rejected = [r for r in ok_records if r.get("hard_reject")]
    accepted.sort(key=lambda r: r["scores"]["final"], reverse=True)
    rejected.sort(key=lambda r: r["scores"]["final"], reverse=True)

    top_candidates = accepted[:top_k]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "probe_seconds": probe_seconds,
        "total_candidates": len(candidates),
        "processed_ok": len(ok_records),
        "errors": len(analyzed) - len(ok_records),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "top_k": top_k,
        "top_candidates": top_candidates,
        "rejected_candidates": rejected,
        "errored_candidates": [r for r in analyzed if r["status"] != "ok"],
        "all_candidates": analyzed,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2))
    return report


def _build_report_path(base_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return base_dir / f"candidate_filter_report_{stamp}.json"


def main() -> int:
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
    parser.add_argument(
        "--report-dir",
        default="backend/data/analysis",
        help="Directory for JSON report output.",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    report_dir = Path(args.report_dir)
    download_dir = Path(args.download_dir)

    candidates = _load_candidates_from_db(db_path)
    source = "database"
    if not candidates:
        candidates = _scan_download_dir(download_dir)
        source = "filesystem"

    if not candidates:
        print("[pipeline] no downloaded videos found.", flush=True)
        return 1

    report_path = _build_report_path(report_dir)
    print(f"[pipeline] source={source}; candidates={len(candidates)}; report={report_path}", flush=True)
    report = run_pipeline(
        candidates=candidates,
        probe_seconds=max(3, int(args.probe_seconds)),
        top_k=max(1, int(args.top_k)),
        report_path=report_path,
    )

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
        f"rejected={report['rejected']} errors={report['errors']}"
    )
    print(f"report: {report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

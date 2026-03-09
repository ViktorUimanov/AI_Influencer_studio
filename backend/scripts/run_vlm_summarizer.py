#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests


@dataclass
class VlmDecision:
    file_name: str
    source_path: str
    decision: str
    confidence: float
    substitution_readiness: float
    reasons: list[str]
    output_json_path: str


MIME_BY_SUFFIX = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
}


def _sanitize_error_message(message: str, api_key: str | None = None) -> str:
    safe = str(message or "")
    safe = re.sub(r"([?&]key=)[^&\s]+", r"\1REDACTED", safe)
    if api_key:
        safe = safe.replace(api_key, "REDACTED")
    return safe


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sanitize_stem(path: Path) -> str:
    base = path.stem[:80]
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", base).strip("._-")
    if not clean:
        clean = "video"
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:10]
    return f"{clean}_{digest}"


def _extract_json_object(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty model response")
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found in model response")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("model response JSON is not an object")
    return payload


def _build_prompt(theme: str, hashtags: list[str]) -> str:
    hashtags_text = ", ".join(hashtags) if hashtags else "(none provided)"
    return f"""
You are a strict video suitability judge for AI subject substitution (face/person replacement).

Channel theme: {theme}
Target hashtags: {hashtags_text}

Task:
Evaluate whether this video is suitable for replacing the main person with an AI influencer.

Scoring rubric (0-10):
- theme_match
- single_subject_clarity
- face_visibility
- motion_stability
- occlusion_risk (higher means worse)
- scene_cut_complexity (higher means worse)
- substitution_readiness

Hard rejection guidance:
- Multiple dominant people in most of the clip
- Main person is small/unclear/rarely visible
- Heavy occlusion
- Extremely rapid cuts that hurt stable replacement

Output format rules:
- Return ONLY valid JSON
- No markdown, no extra commentary
- Use this exact top-level schema:
{{
  "summary": "short summary",
  "scores": {{
    "theme_match": 0,
    "single_subject_clarity": 0,
    "face_visibility": 0,
    "motion_stability": 0,
    "occlusion_risk": 0,
    "scene_cut_complexity": 0,
    "substitution_readiness": 0
  }},
  "decision": "accept|reject|maybe",
  "confidence": 0.0,
  "reasons": ["reason1", "reason2"],
  "best_segments": [
    {{"start_sec": 0.0, "end_sec": 0.0, "why": "reason"}}
  ]
}}
""".strip()


def _call_gemini(
    *,
    model: str,
    api_key: str,
    video_path: Path,
    prompt: str,
    timeout_sec: int,
) -> tuple[dict, str]:
    mime_type = MIME_BY_SUFFIX.get(video_path.suffix.lower())
    if not mime_type:
        raise RuntimeError(f"unsupported video extension: {video_path.suffix}")

    binary = video_path.read_bytes()
    payload = {
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64.b64encode(binary).decode("ascii"),
                        }
                    },
                ],
            }
        ],
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=timeout_sec,
    )
    response.raise_for_status()
    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"no candidates returned: {data}")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text_parts = [str(part.get("text") or "").strip() for part in parts if part.get("text")]
    model_text = "\n".join([p for p in text_parts if p]).strip()
    if not model_text:
        raise RuntimeError(f"no text output in model response: {data}")
    parsed = _extract_json_object(model_text)
    return parsed, model_text


def _mock_summary(video_path: Path) -> tuple[dict, str]:
    seed = int(hashlib.sha1(str(video_path).encode("utf-8")).hexdigest()[:8], 16)
    readiness = 5.5 + ((seed % 420) / 100.0)  # 5.5..9.69
    confidence = 0.55 + ((seed % 35) / 100.0)  # 0.55..0.89
    occlusion_risk = 2 + (seed % 5)  # 2..6
    cut_complexity = 2 + ((seed // 7) % 6)  # 2..7
    decision = "accept" if readiness >= 7.2 and confidence >= 0.70 and occlusion_risk <= 5 else "maybe"
    payload = {
        "summary": "Mock summary for local pipeline test.",
        "scores": {
            "theme_match": round(6.5 + ((seed // 11) % 30) / 10.0, 2),
            "single_subject_clarity": round(6.0 + ((seed // 13) % 35) / 10.0, 2),
            "face_visibility": round(6.0 + ((seed // 17) % 35) / 10.0, 2),
            "motion_stability": round(5.5 + ((seed // 19) % 35) / 10.0, 2),
            "occlusion_risk": float(occlusion_risk),
            "scene_cut_complexity": float(cut_complexity),
            "substitution_readiness": round(readiness, 2),
        },
        "decision": decision,
        "confidence": round(confidence, 3),
        "reasons": ["mock_mode_enabled"],
        "best_segments": [{"start_sec": 0.0, "end_sec": 6.0, "why": "mock best segment"}],
    }
    return payload, json.dumps(payload)


def _auto_decide(
    payload: dict,
    min_readiness: float,
    min_confidence: float,
    max_occlusion_risk: float,
    max_scene_cut_complexity: float,
) -> tuple[str, list[str]]:
    scores = payload.get("scores") or {}
    readiness = _safe_float(scores.get("substitution_readiness"), 0.0)
    confidence = _safe_float(payload.get("confidence"), 0.0)
    occlusion_risk = _safe_float(scores.get("occlusion_risk"), 10.0)
    cut_complexity = _safe_float(scores.get("scene_cut_complexity"), 10.0)
    model_decision = str(payload.get("decision") or "").strip().lower()

    reasons: list[str] = []
    if readiness < min_readiness:
        reasons.append("low_substitution_readiness")
    if confidence < min_confidence:
        reasons.append("low_model_confidence")
    if occlusion_risk > max_occlusion_risk:
        reasons.append("high_occlusion_risk")
    if cut_complexity > max_scene_cut_complexity:
        reasons.append("high_scene_cut_complexity")
    if model_decision in {"reject"}:
        reasons.append("model_rejected")

    if reasons:
        return "reject", reasons
    return "accept", []


def _copy_results(
    decisions: list[VlmDecision],
    selected_dir: Path,
    rejected_dir: Path,
) -> None:
    selected_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir.mkdir(parents=True, exist_ok=True)

    for folder in [selected_dir, rejected_dir]:
        for file in folder.iterdir():
            if file.is_file() or file.is_symlink():
                file.unlink()

    for row in decisions:
        src = Path(row.source_path)
        dst_dir = selected_dir if row.decision == "accept" else rejected_dir
        shutil.copy2(src, dst_dir / src.name)


def _find_video_files(input_dir: Path, max_videos: int) -> list[Path]:
    video_files: list[Path] = []
    for pattern in ["*.mp4", "*.mov", "*.mkv", "*.webm"]:
        video_files.extend(input_dir.glob(pattern))
    unique = sorted({p.resolve() for p in video_files if p.is_file()})
    return unique[:max_videos]


def run(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    selected_dir = Path(args.selected_dir)
    rejected_dir = Path(args.rejected_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = _find_video_files(input_dir, max_videos=args.max_videos)
    if not files:
        print(f"[vlm] no video files in {input_dir}")
        return 1

    hashtags = [h.strip().lstrip("#") for h in args.hashtags.split(",") if h.strip()] if args.hashtags else []
    prompt = _build_prompt(theme=args.theme, hashtags=hashtags)

    api_key = os.getenv(args.api_key_env, "").strip()
    if not args.mock and not api_key:
        print(f"[vlm] missing API key env: {args.api_key_env}")
        print("[vlm] set it in shell, e.g. export GEMINI_API_KEY=...")
        return 2

    print(
        f"[vlm] files={len(files)} model={args.model} mock={args.mock} output_dir={output_dir}",
        flush=True,
    )
    decisions: list[VlmDecision] = []
    per_video_outputs: list[dict] = []

    for idx, video_path in enumerate(files, start=1):
        print(f"[{idx}/{len(files)}] {video_path.name}", flush=True)
        try:
            if args.mock:
                payload, raw_text = _mock_summary(video_path)
            else:
                payload, raw_text = _call_gemini(
                    model=args.model,
                    api_key=api_key,
                    video_path=video_path,
                    prompt=prompt,
                    timeout_sec=args.timeout_sec,
                )

            auto_decision, auto_reasons = _auto_decide(
                payload=payload,
                min_readiness=args.min_readiness,
                min_confidence=args.min_confidence,
                max_occlusion_risk=args.max_occlusion_risk,
                max_scene_cut_complexity=args.max_scene_cut_complexity,
            )
            scores = payload.get("scores") or {}
            confidence = _clamp(_safe_float(payload.get("confidence"), 0.0), 0.0, 1.0)
            readiness = _clamp(_safe_float(scores.get("substitution_readiness"), 0.0), 0.0, 10.0)
            model_reasons = [str(x) for x in (payload.get("reasons") or []) if str(x).strip()]
            reasons = list(dict.fromkeys([*auto_reasons, *model_reasons]))

            safe_stem = _sanitize_stem(video_path)
            out_path = output_dir / f"{safe_stem}.json"
            result_payload = {
                "video_path": str(video_path),
                "file_name": video_path.name,
                "model": args.model,
                "generated_at": datetime.now(UTC).isoformat(),
                "auto_decision": auto_decision,
                "thresholds": {
                    "min_readiness": args.min_readiness,
                    "min_confidence": args.min_confidence,
                    "max_occlusion_risk": args.max_occlusion_risk,
                    "max_scene_cut_complexity": args.max_scene_cut_complexity,
                },
                "model_output": payload,
                "model_raw_text": raw_text,
                "reasons": reasons,
            }
            out_path.write_text(json.dumps(result_payload, ensure_ascii=True, indent=2))

            decisions.append(
                VlmDecision(
                    file_name=video_path.name,
                    source_path=str(video_path),
                    decision=auto_decision,
                    confidence=confidence,
                    substitution_readiness=readiness,
                    reasons=reasons,
                    output_json_path=str(out_path),
                )
            )
            per_video_outputs.append(result_payload)
        except Exception as exc:
            safe_stem = _sanitize_stem(video_path)
            out_path = output_dir / f"{safe_stem}.json"
            err_payload = {
                "video_path": str(video_path),
                "file_name": video_path.name,
                "model": args.model,
                "generated_at": datetime.now(UTC).isoformat(),
                "auto_decision": "error",
                "error": _sanitize_error_message(str(exc), api_key=api_key),
            }
            out_path.write_text(json.dumps(err_payload, ensure_ascii=True, indent=2))
            decisions.append(
                VlmDecision(
                    file_name=video_path.name,
                    source_path=str(video_path),
                    decision="reject",
                    confidence=0.0,
                    substitution_readiness=0.0,
                    reasons=["inference_error"],
                    output_json_path=str(out_path),
                )
            )

    if args.sync_folders:
        _copy_results(decisions=decisions, selected_dir=selected_dir, rejected_dir=rejected_dir)

    accepted = [d for d in decisions if d.decision == "accept"]
    rejected = [d for d in decisions if d.decision != "accept"]
    accepted_sorted = sorted(accepted, key=lambda x: (x.substitution_readiness, x.confidence), reverse=True)

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "model": args.model,
        "mock": args.mock,
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "sync_folders": args.sync_folders,
        "selected_dir": str(selected_dir),
        "rejected_dir": str(rejected_dir),
        "total": len(decisions),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "accepted_top": [
            {
                "file_name": row.file_name,
                "readiness": row.substitution_readiness,
                "confidence": row.confidence,
                "reasons": row.reasons,
                "json_path": row.output_json_path,
            }
            for row in accepted_sorted[:10]
        ],
    }
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    summary_path = output_dir / f"vlm_summary_{stamp}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2))

    print("\n=== VLM SUMMARY ===")
    print(
        f"accepted={summary['accepted']} rejected={summary['rejected']} total={summary['total']} "
        f"mock={args.mock}"
    )
    for idx, row in enumerate(summary["accepted_top"], start=1):
        print(
            f"{idx:02d}. readiness={row['readiness']:.2f} confidence={row['confidence']:.2f} "
            f"file={row['file_name']}"
        )
    print(f"summary: {summary_path.resolve()}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Gemini-based VLM summarizer for substitution suitability.")
    parser.add_argument("--input-dir", default="backend/data/tmp/filtered")
    parser.add_argument("--output-dir", default="backend/data/analysis/vlm")
    parser.add_argument("--selected-dir", default="backend/data/tmp/selected")
    parser.add_argument("--rejected-dir", default="backend/data/tmp/rejected")
    parser.add_argument("--sync-folders", action="store_true")

    parser.add_argument("--theme", default="health lifestyle influencer channel")
    parser.add_argument("--hashtags", default="")
    parser.add_argument("--max-videos", type=int, default=15)

    parser.add_argument("--model", default="gemini-3.1-flash-lite-preview")
    parser.add_argument("--api-key-env", default="GEMINI_API_KEY")
    parser.add_argument("--timeout-sec", type=int, default=240)
    parser.add_argument("--mock", action="store_true")

    parser.add_argument("--min-readiness", type=float, default=7.0)
    parser.add_argument("--min-confidence", type=float, default=0.70)
    parser.add_argument("--max-occlusion-risk", type=float, default=6.0)
    parser.add_argument("--max-scene-cut-complexity", type=float, default=6.0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))

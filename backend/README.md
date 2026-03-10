# Backend API (Prototype)

FastAPI backend for trend ingestion and summarization, focused on TikTok + Instagram video trends.

## What is implemented

- Trend ingestion pipeline for `tiktok` and `instagram`
- Instagram ingestion currently stores only video/reel posts (photo parsing can be enabled later)
- Adapter layer with source strategy:
  - `tiktok_custom` (local `TikTokApi`, no Apify)
  - `instagram_custom` (local `instaloader`, no Apify)
  - `apify` (if configured)
  - `seed` fallback (local sample data)
- Persistent job tracking in Postgres:
  - ingestion runs
  - raw trend items
  - extracted trend signals
- REST API to run ingestion and inspect outputs
- Download stage for trend videos via `yt-dlp` (best available quality)

## Quick start

1. Start Postgres:

```bash
cd backend
docker compose up -d
```

2. Create a virtual environment and install deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For local API smoke tests with `TestClient`, install dev extras:

```bash
pip install -r requirements-dev.txt
```

3. Configure env:

```bash
cp .env.example .env
```

4. Run API:

```bash
uvicorn app.main:app --reload --port 8000
```

If Postgres is down, use auto-fallback launcher (falls back to SQLite):

```bash
./scripts/run_dev.sh
```

Open simple UI:

```bash
http://localhost:8000/ui
```

5. Trigger parsing:

```bash
curl -X POST 'http://localhost:8000/api/v1/trends/ingest' \
  -H 'Content-Type: application/json' \
  -d '{"platforms": ["tiktok", "instagram"], "limit_per_platform": 20}'
```

Selector-based parsing (hashtags/search/min metrics):

```bash
curl -X POST 'http://localhost:8000/api/v1/trends/ingest' \
  -H 'Content-Type: application/json' \
  -d '{
    "platforms": ["tiktok", "instagram"],
    "limit_per_platform": 20,
    "selectors": {
      "tiktok": {
        "mode": "hashtag",
        "hashtags": ["dayinmylife", "tutorial"],
        "min_views": 400000
      },
      "instagram": {
        "mode": "search",
        "search_terms": ["hooks", "retention"]
      }
    }
  }'
```

For the currently tested actors (`clockworks/tiktok-scraper`, `apify/instagram-scraper`), hashtag mode is the most reliable:

```bash
curl -X POST 'http://localhost:8000/api/v1/trends/ingest' \
  -H 'Content-Type: application/json' \
  -d '{
    "platforms": ["tiktok", "instagram"],
    "limit_per_platform": 10,
    "source": "apify",
    "selectors": {
      "tiktok": {"mode": "hashtag", "hashtags": ["fyp", "viral"]},
      "instagram": {"mode": "hashtag", "hashtags": ["reels", "trendingreels"]}
    }
  }'
```

Note: for `clockworks/tiktok-scraper`, the adapter uses your `limit_per_platform` as the total budget and spreads `resultsPerPage` across selected hashtags/search queries.
For `apify/instagram-scraper`, the adapter defaults to `resultsType: "reels"` (video-only).

Per-platform source selection is also supported on the API:

```bash
curl -X POST 'http://localhost:8000/api/v1/trends/ingest' \
  -H 'Content-Type: application/json' \
  -d '{
    "platforms": ["tiktok", "instagram"],
    "limit_per_platform": 20,
    "sources": {
      "tiktok": "tiktok_custom",
      "instagram": "apify"
    },
    "selectors": {
      "tiktok": {"mode": "hashtag", "hashtags": ["dancechallenge"]},
      "instagram": {"mode": "hashtag", "hashtags": ["dance"]}
    }
  }'
```

6. Onboard an influencer first:

If an influencer does not have a reference image, description, and hashtags in the database yet, the pipeline API returns an onboarding-required error (`409`).

```bash
curl -X POST 'http://localhost:8000/api/v1/influencers/onboarding' \
  -F 'influencer_id=mina-main' \
  -F 'name=Mina' \
  -F 'description=Young female dance and lifestyle creator with clean natural look and confident solo performance style.' \
  -F 'hashtags=dance,dancing,choreography,dancechallenge' \
  -F 'reference_image=@/absolute/path/to/reference.jpg'
```

Inspect influencer records:

```bash
curl 'http://localhost:8000/api/v1/influencers'
curl 'http://localhost:8000/api/v1/influencers/mina-main'
```

7. Run the configurable API pipeline:

```bash
curl -X POST 'http://localhost:8000/api/v1/pipeline/run' \
  -H 'Content-Type: application/json' \
  -d '{
    "influencer_id": "mina-main",
    "platforms": {
      "tiktok": {
        "enabled": true,
        "source": "tiktok_custom",
        "limit": 30,
        "selector": {
          "mode": "mixed",
          "hashtags": ["dancechallenge", "choreography"],
          "search_terms": ["solo dance", "dance tutorial"],
          "published_within_days": 45
        }
      },
      "instagram": {
        "enabled": true,
        "source": "apify",
        "limit": 30,
        "selector": {
          "mode": "mixed",
          "hashtags": ["dance", "dancechallenge"],
          "published_within_days": 45,
          "source_params": {"resultsType": "reels"}
        }
      }
    },
    "download": {"enabled": true, "force": false},
    "filter": {"enabled": true, "probe_seconds": 8, "workers": 4, "top_k": 15},
    "vlm": {
      "enabled": true,
      "theme": "dance creator channel",
      "model": "gemini-3.1-flash-lite-preview",
      "max_videos": 15,
      "thresholds": {
        "min_readiness": 7.0,
        "min_confidence": 0.7,
        "min_persona_fit": 6.5,
        "max_occlusion_risk": 6.0,
        "max_scene_cut_complexity": 6.0
      }
    }
  }'
```

8. Inspect run:

```bash
curl 'http://localhost:8000/api/v1/trends/runs'
curl 'http://localhost:8000/api/v1/trends/latest?platform=tiktok'
curl 'http://localhost:8000/api/v1/trends/items?platform=instagram&limit=10'
curl 'http://localhost:8000/api/v1/trends/signals?platform=tiktok&signal_type=hashtag&limit=10'
curl 'http://localhost:8000/api/v1/trends/items?platform=tiktok&hashtag=tutorial&min_views=300000'
curl 'http://localhost:8000/api/v1/trends/items?platform=instagram&query=hooks'
```

9. Download assets for a run:

```bash
curl -X POST 'http://localhost:8000/api/v1/trends/downloads/run' \
  -H 'Content-Type: application/json' \
  -d '{"run_id": 1, "platform": "tiktok", "limit": 5, "download_dir": "~/Downloads/healthy_videos"}'

curl 'http://localhost:8000/api/v1/trends/downloads?run_id=1&status=downloaded'
```

10. Optional one-shot demo:

```bash
./scripts/demo_ingest.sh
./scripts/demo_downloads.sh 1
```

11. Candidate filtering + VLM summarizer:

```bash
# 1) Deterministic pre-filter / ranking
./scripts/run_candidate_filter_pipeline.py --probe-seconds 8 --top-k 8

# 2) VLM suitability scoring (real Gemini run, persona-aware)
export GEMINI_API_KEY=your_api_key
./scripts/run_vlm_summarizer.py \
  --theme "healthy lifestyle channel" \
  --hashtags "wellness,healthylifestyle,mealprep" \
  --persona-file backend/data/personas/default_persona.json \
  --persona-id forest_health_creator_v1 \
  --max-videos 15 \
  --sync-folders

# 3) Local dry-run without API (for pipeline validation)
./scripts/run_vlm_summarizer.py --mock --sync-folders

# 4) One-command end-to-end selector pipeline (filter -> Gemini -> selected/rejected)
./scripts/run_selector_pipeline.py \
  --top-k 15 \
  --theme "healthy lifestyle channel" \
  --hashtags "wellness,fitness,nutrition" \
  --persona-id forest_health_creator_v1

# 5) Main health pipeline (TikTok + Instagram, topic-focused + recent, then custom filter -> Gemini)
./scripts/run_health_main_pipeline.py \
  --source tiktok_custom \
  --platforms "tiktok" \
  --topic "healthy lifestyle" \
  --persona-id forest_health_creator_v1 \
  --recent-days 45 \
  --limit 50 \
  --top-k 20

# Relax strict topic filtering if ingestion returns too few candidates
./scripts/run_health_main_pipeline.py --no-strict-topic-match --limit 50

# Cross-platform run (uses Apify adapters)
./scripts/run_health_main_pipeline.py --source apify --platforms "tiktok,instagram" --limit 50

# Custom topic/hashtags run
./scripts/run_health_main_pipeline.py \
  --source tiktok_custom \
  --platforms "tiktok" \
  --topic "dance" \
  --hashtags "dance,dancing,choreography,dancetrend,dancechallenge" \
  --search-terms "dance,dancing,dance trend"

# Disable Apify cost-optimized mode for a broader (and usually more expensive) scrape
./scripts/run_health_main_pipeline.py --source apify --no-apify-cost-optimized --limit 50

# Instagram-only custom parser (no Apify)
./scripts/run_health_main_pipeline.py --source instagram_custom --platforms "instagram" --limit 50
```

## Notes

- `source=tiktok_custom` uses local `TikTokApi` sessions (no Apify) and is TikTok-only.
- `source=instagram_custom` uses local `instaloader` hashtag parsing (no Apify) and is Instagram-only.
- `source=apify` supports TikTok + Instagram with actor IDs from `.env`.
- `source=seed` is deterministic local test data.
- Actor IDs can be provided as either `owner/actor` or `owner~actor`; the adapter normalizes both.
- If Apify returns auth/rate errors, ingestion now fails with explicit `502` by default (instead of silently returning empty data). Set `APIFY_FALLBACK_TO_SEED=true` only if you intentionally want fallback behavior.
- TikTok and Instagram Store actors are paid per event/result; cost grows quickly with many hashtags/search terms.
- Apify cost optimization is enabled by default (`APIFY_COST_OPTIMIZED=true`) and caps selector terms (`APIFY_MAX_SELECTOR_TERMS=1`) while keeping APIFY over-fetch disabled (`APIFY_OVERFETCH_MULTIPLIER=1`).
- Apify cost optimization is optional: set `APIFY_COST_OPTIMIZED=false` or run with `--no-apify-cost-optimized`.
- For `clockworks/tiktok-scraper`, `resultsPerPage` is now distributed across selected hashtags/search queries so a single run stays close to your requested `limit_per_platform`.
- Transient Apify gateway/network errors (`429/5xx`, timeouts) are retried automatically with exponential backoff (`APIFY_REQUEST_RETRIES`, `APIFY_RETRY_BACKOFF_SEC`, `APIFY_RETRY_MAX_BACKOFF_SEC`).
- For Instagram/TikTok downloads behind auth walls, set `YT_DLP_COOKIES_FILE` to a valid cookies file.
- VLM summarizer script (`scripts/run_vlm_summarizer.py`) reads videos from `backend/data/tmp/filtered` and writes per-video JSON outputs to `backend/data/analysis/vlm`.
- Default persona profile lives in `backend/data/personas/default_persona.json` and is injected into Gemini prompt/scoring (`persona_fit`).
- Persona access is centralized: pipelines can load by `--persona-id` from the `personas` table, with JSON file fallback via `--persona-file`.
- When a persona file is provided, the resolver can sync it into the DB automatically so later pipeline stages can fetch the same persona by ID.
- With `--sync-folders`, VLM decisions are synced to `backend/data/tmp/selected` and `backend/data/tmp/rejected`.
- Candidate filter script now syncs top-K candidates into `backend/data/tmp/filtered` by default.
- End-to-end `scripts/run_selector_pipeline.py` runs candidate filtering and VLM selection in one command.
- `scripts/run_health_main_pipeline.py` supports both TikTok and Instagram with shared hashtag/topic selectors.
- `scripts/run_health_main_pipeline.py` accepts `--hashtags` and `--search-terms` to override the default topic preset.
- For tighter topical relevance, selectors support `published_within_days` and `require_topic_match`.
- For `tiktok_custom`, optionally set `TIKTOK_MS_TOKENS` (comma-separated) for more stable sessions.
- First-time custom source setup requires `playwright install chromium`.
- For `instagram_custom`, optional auth settings are `INSTAGRAM_CUSTOM_USERNAME`, `INSTAGRAM_CUSTOM_PASSWORD`, and `INSTAGRAM_CUSTOM_SESSION_FILE`.
- Instagram frequently returns `login_required` for hashtag endpoints; in practice, `instagram_custom` usually needs auth/session configured.
- Set `GEMINI_API_KEY` for real Gemini runs. Default model in script/env is `gemini-3.1-flash-lite-preview`.
- Seed URLs in `backend/data/seeds/*.json` are placeholders; downloader quality tests require real URLs.
- Some Instagram rows can still have `views=0` when upstream metadata does not expose play count; ranking prioritizes freshness + reach and de-prioritizes zero-view engagement inflation.
- IG sidecar carousel posts can include videos inside `childPosts`; the adapter now extracts those nested videos as separate items.
- ComfyUI and Telegram are intentionally out of scope at this stage and can be integrated later through separate modules.

## VPS launch

For a simple VPS bootstrap, use the one-command launcher:

```bash
cd backend
./scripts/launch_vps.sh
```

What it does:

- starts Postgres with `docker compose up -d postgres`
- creates `.venv` if needed
- installs Python dependencies
- starts `uvicorn` on `0.0.0.0:${PORT:-8000}`

Recommended VPS flow:

1. Clone the repo.
2. Create `backend/.env`.
3. Run `./scripts/launch_vps.sh`.
4. Put Nginx or Caddy in front of `:8000` if you want HTTPS/public access.

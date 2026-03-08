# Backend API (Prototype)

FastAPI backend for trend ingestion and summarization, focused on TikTok + Instagram video trends.

## What is implemented

- Trend ingestion pipeline for `tiktok` and `instagram`
- Instagram ingestion currently stores only video/reel posts (photo parsing can be enabled later)
- Adapter layer with source strategy:
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

6. Inspect run:

```bash
curl 'http://localhost:8000/api/v1/trends/runs'
curl 'http://localhost:8000/api/v1/trends/latest?platform=tiktok'
curl 'http://localhost:8000/api/v1/trends/items?platform=instagram&limit=10'
curl 'http://localhost:8000/api/v1/trends/signals?platform=tiktok&signal_type=hashtag&limit=10'
curl 'http://localhost:8000/api/v1/trends/items?platform=tiktok&hashtag=tutorial&min_views=300000'
curl 'http://localhost:8000/api/v1/trends/items?platform=instagram&query=hooks'
```

7. Download assets for a run:

```bash
curl -X POST 'http://localhost:8000/api/v1/trends/downloads/run' \
  -H 'Content-Type: application/json' \
  -d '{"run_id": 1, "platform": "tiktok", "limit": 5, "download_dir": "~/Downloads/influencer_videos"}'

curl 'http://localhost:8000/api/v1/trends/downloads?run_id=1&status=downloaded'
```

8. Optional one-shot demo:

```bash
./scripts/demo_ingest.sh
./scripts/demo_downloads.sh 1
```

## Notes

- Default source is `seed` to ensure parser works without external credentials.
- To use Apify, set `DEFAULT_SOURCE=apify` and provide token + actor IDs in `.env`.
- Actor IDs can be provided as either `owner/actor` or `owner~actor`; the adapter normalizes both.
- If Apify returns auth/rate errors, ingestion now fails with explicit `502` by default (instead of silently returning empty data). Set `APIFY_FALLBACK_TO_SEED=true` only if you intentionally want fallback behavior.
- TikTok and Instagram Store actors are paid per event/result; cost grows quickly with many hashtags/search terms. The parser now caps selector terms by default (`APIFY_MAX_SELECTOR_TERMS=3`) and disables APIFY over-fetch by default (`APIFY_OVERFETCH_MULTIPLIER=1`).
- For `clockworks/tiktok-scraper`, `resultsPerPage` is now distributed across selected hashtags/search queries so a single run stays close to your requested `limit_per_platform`.
- Transient Apify gateway/network errors (`429/5xx`, timeouts) are retried automatically with exponential backoff (`APIFY_REQUEST_RETRIES`, `APIFY_RETRY_BACKOFF_SEC`, `APIFY_RETRY_MAX_BACKOFF_SEC`).
- For Instagram/TikTok downloads behind auth walls, set `YT_DLP_COOKIES_FILE` to a valid cookies file.
- Seed URLs in `backend/data/seeds/*.json` are placeholders; downloader quality tests require real URLs.
- Some Instagram rows can still have `views=0` when upstream metadata does not expose play count; ranking prioritizes freshness + reach and de-prioritizes zero-view engagement inflation.
- IG sidecar carousel posts can include videos inside `childPosts`; the adapter now extracts those nested videos as separate items.
- ComfyUI and Telegram are intentionally out of scope at this stage and can be integrated later through separate modules.

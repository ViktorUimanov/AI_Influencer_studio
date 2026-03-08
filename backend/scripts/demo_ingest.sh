#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

curl -sS -X POST "${BASE_URL}/api/v1/trends/ingest" \
  -H 'Content-Type: application/json' \
  -d '{
    "platforms": ["tiktok", "instagram"],
    "limit_per_platform": 20,
    "source": "seed",
    "selectors": {
      "tiktok": {"mode": "hashtag", "hashtags": ["tutorial", "dayinmylife"], "min_views": 500000},
      "instagram": {"mode": "search", "search_terms": ["hooks", "tutorial"]}
    }
  }'

echo

echo "Top TikTok hashtags:"
curl -sS "${BASE_URL}/api/v1/trends/signals?platform=tiktok&signal_type=hashtag&limit=10"

echo

echo "Top Instagram videos:"
curl -sS "${BASE_URL}/api/v1/trends/items?platform=instagram&limit=5"

echo
echo "Filtered TikTok tutorial videos:"
curl -sS "${BASE_URL}/api/v1/trends/items?platform=tiktok&hashtag=tutorial&limit=5"
echo

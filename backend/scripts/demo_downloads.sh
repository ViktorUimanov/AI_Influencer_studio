#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
RUN_ID="${1:-}"

if [[ -z "${RUN_ID}" ]]; then
  echo "Usage: $0 <run_id>"
  exit 1
fi

curl -sS -X POST "${BASE_URL}/api/v1/trends/downloads/run" \
  -H 'Content-Type: application/json' \
  -d "{\"run_id\": ${RUN_ID}, \"platform\": \"tiktok\", \"limit\": 5}"

echo

echo "Download records:"
curl -sS "${BASE_URL}/api/v1/trends/downloads?run_id=${RUN_ID}&limit=20"
echo

#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi

if [[ "${DATABASE_URL:-}" == postgresql* ]]; then
  if command -v docker >/dev/null 2>&1; then
    docker compose up -d postgres
  else
    echo "[launch] DATABASE_URL points to Postgres but docker is unavailable." >&2
    exit 1
  fi
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

pip install -r requirements.txt

export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:////tmp/influencer_dev.db}"

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

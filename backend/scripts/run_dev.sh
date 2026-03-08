#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

DB_URL_DEFAULT="postgresql+psycopg://postgres:postgres@localhost:5432/influencer"
DB_URL="${DATABASE_URL:-${DB_URL_DEFAULT}}"

if [[ "$DB_URL" == postgresql* ]]; then
  if command -v pg_isready >/dev/null 2>&1 && pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
    echo "[run_dev] Postgres is reachable. Using: $DB_URL"
  else
    echo "[run_dev] Postgres is not reachable. Falling back to SQLite."
    export DATABASE_URL="sqlite+pysqlite:////tmp/influencer_dev.db"
  fi
fi

echo "[run_dev] Starting API on http://localhost:8000"
exec uvicorn app.main:app --reload --port 8000

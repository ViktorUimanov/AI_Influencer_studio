# Frontend

React + Vite frontend for the AI Influencer workspace.

## What It Does

The frontend currently supports:

- runs history
- dedicated run detail pages
- influencer editing
- settings
- live parser run creation against the backend API
- mocked Comfy outputs layered on top of real parser results

The UI has two data modes:

- `mock`: frontend-only demo data
- `live`: real backend influencers + real parser pipeline + mocked Comfy outputs

## Prerequisites

- Node.js 18+
- npm
- backend API running on `http://127.0.0.1:8000`

For live mode, the backend should be started in filesystem storage mode and have CORS enabled for the Vite origin.

## Install

```bash
cd /Users/viktor/data_science/influencer_project/frontend
npm install
```

## Run

```bash
cd /Users/viktor/data_science/influencer_project/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

- mock mode: `http://127.0.0.1:5173/`
- live mode: `http://127.0.0.1:5173/?api=live`

## Backend

Run the backend in another terminal:

```bash
cd /Users/viktor/data_science/influencer_project/backend
source .venv/bin/activate
set -a
source .env 2>/dev/null
set +a
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Recommended backend env for prototype mode:

```env
STORAGE_MODE=filesystem
DATABASE_URL=sqlite+pysqlite:////tmp/influencer_dev.db
```

## Live Mode Behavior

When `?api=live` is enabled:

1. influencers are loaded from the backend
2. pipeline run history is loaded from backend run manifests
3. starting a run sends a real `POST /api/v1/pipeline/run`
4. the selected influencer is synced into backend filesystem storage before the run
5. selected parser assets are shown as real run inputs
6. a mocked Comfy output is attached in the frontend workspace

Important:

- run execution is still synchronous on the backend
- the UI shows a temporary `Running` row while waiting for the backend response
- Comfy is not called yet from the frontend flow

## Main Routes

- `#/runs`
- `#/run/<run-id>`
- `#/influencer`
- `#/settings`

## Build

```bash
cd /Users/viktor/data_science/influencer_project/frontend
npm run build
```

Preview production build:

```bash
npm run preview -- --host 127.0.0.1 --port 4173
```

## Notes

- local sample media is reused from the repository for mocked assets
- live parser output paths come from backend filesystem manifests
- long asset filenames and wide run layouts were explicitly handled in the current UI build

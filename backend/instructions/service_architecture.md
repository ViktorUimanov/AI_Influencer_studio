# Service Architecture

This document summarizes the current service split across the Studio backend, the Comfy agent, and the future frontend.

## Overview

Current system shape:

```text
User / Operator
  -> Studio Backend API
  -> Comfy Agent
     -> Telegram bot
     -> VastAI GPU manager
     -> ComfyUI workflow runner
     -> ISP postprocessing
```

Intended production flow:

```text
Frontend / Telegram
  -> Studio Backend API
     -> trend parsing
     -> downloads
     -> filtering
     -> Gemini selection / generation
  -> Comfy Agent
     -> rents GPU
     -> runs ComfyUI workflow remotely
     -> postprocesses outputs
```

## Studio Backend

Location:
- `backend/`

Main responsibility:
- own the data model and API
- onboard influencers
- parse platform content
- download source media
- filter and rank candidates
- run Gemini-based analysis and generation

Main API areas:
- influencer onboarding and profile storage
- trend ingestion and download pipeline
- X parsing / draft generation
- image generation
- pipeline orchestration

Important current backend route:
- `POST /api/v1/pipeline/run`

Current implemented request shape:

```json
{
  "influencer_id": "alt-girl-dance",
  "platforms": {
    "tiktok": {
      "enabled": true,
      "source": "tiktok_custom",
      "limit": 20,
      "selector": {
        "hashtags": ["dance"],
        "search_terms": ["alt girl dance"]
      }
    }
  },
  "download": {"enabled": true},
  "filter": {"enabled": true},
  "vlm": {"enabled": true}
}
```

Key point:
- `platforms` is currently a dictionary of per-platform configs
- not a list of platform names

Important backend runtime requirements:
- Python dependencies in `.venv`
- `ffmpeg` / `ffprobe` for candidate filtering
- Playwright browser binaries for `tiktok_custom`
- API keys / runtime config in `backend/.env`

## Comfy Agent

Location:
- `Comfy_agent/`

Main responsibility:
- execute generation workflows after the Studio backend has already chosen source material

Its job is not trend parsing. Its job is GPU orchestration and Comfy execution.

Main layers:

1. `telegram_bot`
- user interface for manual and parse-driven generation
- supports `/start`, `/parse`, `/resume`, `/stop`, etc.

2. `vast_agent`
- rents and destroys VastAI GPU servers
- pushes code to the remote host
- runs commands remotely via SSH / rsync

3. `comfy_pipeline`
- installs ComfyUI and custom nodes
- starts/stops ComfyUI server
- uploads inputs
- runs workflows
- downloads outputs

4. `isp_pipeline`
- postprocesses output video
- grain, sharpening, brightness, vignette

## Current Backend <-> Comfy Agent Coupling

The key integration point today is:
- `Comfy_agent/src/telegram_bot/studio_client.py`

The Telegram bot calls:
- `POST /api/v1/pipeline/run`

What it expects from the backend:
- selected video outputs from the parsing pipeline
- especially `platforms[].selected_dir`

Current client behavior:
- chooses source automatically:
  - TikTok -> `tiktok_custom`
  - Instagram -> `apify`
- sends only a minimal payload:
  - `influencer_id`
  - `platforms`
  - optional `hashtags`
  - `limit`

That means the Comfy agent currently assumes the Studio backend is responsible for:
- finding candidate videos
- downloading them
- filtering them
- selecting final usable clips

Then the Comfy agent takes those selected clips and runs generation.

## Comfy Agent Pipeline

Current parse-driven flow:

```text
Telegram /parse
  -> Studio backend /api/v1/pipeline/run
  -> selected_dir of approved source videos
  -> user reviews each video and writes prompt
  -> VastAI GPU is rented once
  -> ComfyUI workflow runs in batch
  -> outputs are postprocessed
  -> results and costs are logged
```

This is a good division of responsibilities:
- Studio backend = discovery and selection
- Comfy agent = generation execution

## Workflow Configuration

The Comfy side is config-driven.

Main files:
- `Comfy_agent/configs/*.yaml`
- `Comfy_agent/workflows/*.json`

The workflow config maps:
- input names
- output nodes
- semantic parameters like `prompt`
- custom nodes
- model download URLs

This means the Studio backend does not need to know Comfy node IDs directly.

The integration boundary should stay at:
- input image
- input video
- prompt
- workflow name

## Telegram Bot Integration Notes

The Telegram bot already has a usable Studio client, but it is intentionally thin.

Current assumptions:
- the Studio API is reachable at `studio_base_url`
- the Studio API returns ready-to-review video files
- the influencer already exists in the Studio backend

Current config for the Telegram side lives in:
- `Comfy_agent/configs/telegram.yaml`

Important fields:
- `studio_base_url`
- `studio_influencer_id`
- `studio_parse_limit`
- `default_workflow`

## Frontend

Location:
- `frontend/`

Status:
- not implemented yet

Planned responsibility:
- replace or complement the Telegram interaction layer for:
  - onboarding
  - running parse pipelines
  - reviewing selected videos
  - launching Comfy generation jobs
  - viewing generated outputs

Recommended frontend boundary:
- call Studio backend APIs directly
- call Comfy-agent-facing orchestration endpoints later if needed

The frontend should not contain parsing or workflow logic.
It should only orchestrate the existing backend and generation services.

## Recommended Final Split

### Studio Backend
- data and business logic
- parsing
- ranking
- Gemini analysis
- onboarding
- content ideas

### Comfy Agent
- GPU orchestration
- Comfy workflow execution
- Telegram automation
- postprocessing

### Frontend
- operator UI
- onboarding forms
- pipeline launch UI
- review queues
- result browser

## Current Practical Guidance

If building next steps:

1. Keep the Studio backend as the source-of-truth API
2. Keep Comfy agent focused on generation execution
3. Build frontend later against the Studio backend first
4. Avoid pushing Comfy-specific logic into the Studio backend
5. Keep the integration contract small:
   - selected input media
   - prompt
   - workflow name
   - output paths / status / cost

## Main Current Gap

The Studio API contract and the higher-level design notes are not fully aligned yet.

Implemented backend contract:
- per-platform config dictionary under `platforms`

Desired future contract:
- simpler top-level structure for easier human and agent use

If the API is simplified later, update:
- Studio backend schemas
- `Comfy_agent/src/telegram_bot/studio_client.py`
- frontend request builders

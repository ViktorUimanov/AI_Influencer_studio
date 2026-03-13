# Frontend Runtime And Flow

This note describes how the current frontend works, not the aspirational product.

## Stack

- React
- Vite
- plain CSS
- no global state library

Main entrypoints:

- [frontend/src/App.jsx](/Users/viktor/data_science/influencer_project/frontend/src/App.jsx)
- [frontend/services/appApi.js](/Users/viktor/data_science/influencer_project/frontend/services/appApi.js)
- [frontend/services/studioApi.js](/Users/viktor/data_science/influencer_project/frontend/services/studioApi.js)
- [frontend/services/mockStudioApi.js](/Users/viktor/data_science/influencer_project/frontend/services/mockStudioApi.js)

## Modes

### Mock

Default mode.

Uses:

- `mockStudioApi`
- local mock runs
- local mock influencers
- local mock assets
- localStorage persistence for frontend changes

Entry:

- `http://127.0.0.1:5173/`

### Live

Enabled by query param:

- `?api=live`

Uses:

- backend influencers
- backend pipeline run manifests
- real parser pipeline calls
- mock Comfy outputs

Entry:

- `http://127.0.0.1:5173/?api=live`

## Live Run Flow

When the user starts a parser run:

1. the run composer modal builds a real `PipelineRunRequest`
2. the selected influencer is synced to backend storage through `PUT /api/v1/influencers/{id}`
3. the selected reference image path is included in that sync
4. the frontend calls `POST /api/v1/pipeline/run`
5. after completion, the frontend loads:
   - `GET /api/v1/pipeline/runs`
   - `GET /api/v1/pipeline/runs/{influencer_id}/{run_id}`
6. parser-selected assets are imported into the frontend workspace
7. one mocked Comfy output is created from the selected assets for display

So:

- parser is real
- run result ingestion is real
- Comfy output is still mocked

## Run Pages

### Runs History

`#/runs`

Contains:

- filters
- runs list
- inline expandable metadata
- arrow action to open a dedicated run page
- `Start parser run` button

### Dedicated Run Page

`#/run/<run-id>`

Contains:

- summary metadata
- pipeline stages
- config summary
- input assets
- outputs

This page is intentionally separate from the runs list.

## Reference Images

Live parser runs require a valid reference image path.

Current UI behavior:

- the run composer forces explicit reference image selection
- if the influencer has no usable reference image, the run should not start

## Current Backend Dependencies

The frontend assumes the backend exposes:

- `GET /api/v1/influencers`
- `GET /api/v1/influencers/{id}`
- `PUT /api/v1/influencers/{id}`
- `POST /api/v1/pipeline/run`
- `GET /api/v1/pipeline/runs`
- `GET /api/v1/pipeline/runs/{influencer_id}/{run_id}`

## Known Constraints

- backend run execution is synchronous
- there is no real async job queue yet
- run status during execution is simulated on the frontend until the response returns
- Comfy is not integrated in the live run path yet
- onboarding upload flow is not fully wired from the current frontend

## Recommended Next Steps

1. add real onboarding upload flow for reference images
2. add async backend run execution and polling
3. replace mocked Comfy output with real Comfy job integration

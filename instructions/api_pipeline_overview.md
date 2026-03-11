# API Pipeline Overview

This note describes the intended API shape for content parsing and generation.

## Short Version

The API should let a client say:

- which influencer to use
- which platforms to use
- whether content discovery should come from the influencer's base hashtags or from platform trends
- what the content goal is
- how strict the pipeline should be

The user should not need to know scraper internals, actor names, or Gemini prompt wiring.

### Main ideas

- `influencer_id`: which influencer profile to use
- `platforms`: where to search
- `mode`: how topics are chosen
  - `base_hashtags`
  - `trending`
- `goal`: what the pipeline should produce
  - `video_selection`
  - `post_generation`
  - `image_ideas`
- `limit`: how many source items to collect

### Recommended top-level request shape

```json
{
  "influencer_id": "mina-main",
  "platforms": ["tiktok", "instagram"],
  "mode": "base_hashtags",
  "goal": "video_selection",
  "topic": "healthy lifestyle",
  "limit": 50,
  "sources": {
    "tiktok": "tiktok_custom",
    "instagram": "apify"
  },
  "search": {
    "hashtags": ["wellness", "fitness", "nutrition"],
    "terms": ["healthy lifestyle", "meal prep"],
    "recent_days": 30
  },
  "processing": {
    "download": true,
    "filter": true,
    "gemini": true,
    "top_k": 15,
    "image_mode": "prefer",
    "output_mode": "selected_only"
  }
}
```

## Parameter Meaning

### Core

- `influencer_id`
  - required
  - loads the influencer profile from the database
  - if onboarding is incomplete, the API should return an onboarding error

- `platforms`
  - list of target platforms
  - examples: `tiktok`, `instagram`, `x`

- `mode`
  - decides how search topics are chosen
  - `base_hashtags`: use the influencer's saved hashtags
  - `trending`: use top platform trends, then filter them for influencer fit

- `goal`
  - tells the system what to produce
  - example goals:
    - `video_selection`
    - `post_generation`
    - `image_ideas`

- `topic`
  - optional higher-level theme
  - example: `healthy lifestyle`

- `limit`
  - total number of source items to collect before filtering

### `sources`

Controls which engine is used for each platform.

Example:

```json
{
  "tiktok": "tiktok_custom",
  "instagram": "apify",
  "x": "official"
}
```

This keeps scraper selection explicit without exposing low-level implementation details in the rest of the request.

### `search`

`search` means topic and query discovery: how the pipeline decides what to look for.

Recommended fields:

- `hashtags`
  - explicit seed hashtags
- `terms`
  - explicit search phrases
- `recent_days`
  - recency window
- `location`
  - useful for X trends

This is intentionally called `search` instead of `discovery` because it is easier to understand from the API side.

### `processing`

`processing` controls what happens after items are found.

Recommended fields:

- `download`
  - whether media should be downloaded locally
- `filter`
  - whether deterministic filtering should run
- `gemini`
  - whether Gemini analysis or generation should run
- `gemini_model`
  - optional model override
- `top_k`
  - how many items continue to the Gemini stage
- `image_mode`
  - `any`
  - `prefer`
  - `required`
- `output_mode`
  - `selected_only`
  - `selected_and_rejected`
  - `metadata_only`
- `min_engagement`
  - optional threshold for likes, reposts, views, or similar metrics

## Slightly More Explicit Version

This section is meant for an LLM or agent that needs a compact but clear contract.

### Input contract

- The caller provides one influencer ID.
- The system loads influencer description, reference image, hashtags, and negative content requirements from the database.
- If any required onboarding fields are missing, the system returns:
  - `onboarding_required`
  - plus the missing fields

### Topic-selection contract

- If `mode=base_hashtags`:
  - use influencer hashtags as the initial topic set
- If `mode=trending`:
  - fetch trending topics from the chosen platform
  - ask Gemini to select only the topics that match the influencer
  - if no topics fit, return a clean error instead of forcing bad results

### Collection contract

- Use platform-specific sources from `sources`
- Apply `search` constraints:
  - hashtags
  - terms
  - recency
  - location if relevant
- Collect up to `limit` raw items

### Processing contract

- Optional local download
- Optional deterministic filtering
- Optional Gemini stage for:
  - summarization
  - ranking
  - suitability
  - generation

### Output contract

The response should contain:

- resolved influencer ID
- final selected topics
- source run metadata
- top collected items
- generated outputs if requested
  - selected videos
  - generated posts
  - image briefs
  - summaries

## Default Behavior

The API should be easy to use with a minimal payload.

Minimal example:

```json
{
  "influencer_id": "mina-main",
  "platforms": ["tiktok"],
  "mode": "base_hashtags",
  "goal": "video_selection",
  "topic": "healthy lifestyle"
}
```

The backend should fill in defaults for:

- source engine per platform
- recency window
- whether Gemini runs
- ranking depth
- output mode

## Suggested Error Style

Use clean product-level errors instead of internal exceptions.

Examples:

```json
{
  "error": "onboarding_required",
  "missing": ["reference_image", "hashtags"]
}
```

```json
{
  "error": "no_matching_trends",
  "detail": "No trending topics matched the influencer profile strongly enough."
}
```

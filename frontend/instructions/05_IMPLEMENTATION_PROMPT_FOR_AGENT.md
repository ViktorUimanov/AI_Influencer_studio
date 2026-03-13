# Implementation Prompt for UI Agent

Design a modern desktop web app UI for a single-user AI influencer platform.

This is an internal product workspace, not a marketing site.
The user creates AI influencers, uploads real reference media for them, discovers trends, launches runs, and views generated outputs.

## The previous design was wrong
Do not repeat these mistakes:
- no oversized left sidebar hero block,
- no giant slogan or marketing copy in navigation,
- no flat generic media grid as the main information structure,
- no weak page hierarchy,
- no generic dashboard cards everywhere,
- no unclear distinction between references, runs, and outputs.

## Use this information architecture
Main navigation in a narrow functional sidebar:
- Dashboard
- Influencers
- Trends
- Runs
- Library
- Settings

The sidebar must be compact and quiet.
Do not place promotional copy or large panels in it.

## Core product model
- Influencer = one persona
- Trend = source idea / hashtag / discovered content direction
- Run = one generation job
- Asset = uploaded or generated media
- Output = result of a run

## Product constraints
- one user only
- multiple influencers
- no teams
- no approvals
- no voice system
- no multiple persona variants
- each influencer has a portfolio of real uploaded photos/videos
- the product is influencer-first

## Global design style
- premium modern AI workspace
- calm dark or neutral palette
- strong spacing and typography
- media-first but structured
- modern SaaS feel similar in maturity to ChatGPT / Claude / Linear / Notion
- do not use flashy gradient-heavy startup aesthetics

## Page-by-page requirements

### Dashboard
Design an operational home page.
Include:
- header with title/subtitle
- compact summary cards
- recent runs list with clear status/progress
- influencer activity section
- recent outputs section
- CTA to create influencer
This is not a landing page.

### Influencers list
Design a list/grid of influencers.
Each influencer card should show:
- image/avatar
- name
- short descriptor
- status
- reference asset count
- run count
- recent activity
- open action
- new run action

### Influencer detail
Design a control center for one influencer.
Include:
- compact hero summary with stats and actions
- tabs: Overview, Portfolio, Runs, Outputs, Settings

Portfolio tab must be first-class and contain uploaded real photos/videos.
This is not generated media.

### Create influencer flow
Design a short guided creation flow.
Steps:
1. basic identity
2. upload reference photos/videos
3. review and create

### Trends page
Design a discovery page with:
- filters
- trend cards
- preview media
- platform labels
- inspect action
- use-in-run action
Prefer a detail drawer for inspecting a selected trend.

### Runs list
Design a dense operational list.
Each row should show:
- run title
- influencer
- type
- status
- progress
- created time
- outputs count
- open action

### Run detail
Design a pipeline/result page.
Include:
- run header
- inputs summary
- progress / stage visualization
- outputs gallery
- failure / running / empty states

### Library
Design a structured asset browser.
It must clearly separate:
- reference media
- source assets
- generated outputs
Use tabs or segmentation, not one mixed gallery.

## Important design rules
- distinguish overview pages from detail pages
- distinguish operational pages from media pages
- one primary CTA per page where possible
- reference media and generated outputs must always feel separate
- use empty states, loading states, and failure states
- design for real product use, not for dribbble-style visuals

## What to optimize for
Optimize for:
- clarity
- object hierarchy
- workflow logic
- calm visual design
- ability to scale with real backend data later

Do not optimize for flashy decoration.

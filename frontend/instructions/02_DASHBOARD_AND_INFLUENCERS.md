# Dashboard and Influencer Pages

## PAGE 1 — Dashboard

## Purpose
The dashboard is the operational home screen.
It should tell the user what is happening across the whole workspace right now.

It is **not** a landing page and **not** a generic analytics board.

The dashboard should answer:
- What happened recently?
- What is currently running?
- Which influencer had recent activity?
- What can I open next?

---

## Layout

Recommended structure:

1. Page header
2. Compact summary strip
3. Active / recent runs section
4. Influencer activity section
5. Recent outputs section

Avoid making the dashboard one giant feed of mixed cards.

---

## Header

### Left side
- Title: `Dashboard`
- Subtitle: `Track recent influencer activity, runs, and generated outputs.`

### Right side
- Primary CTA: `Create influencer`
- Secondary CTA: `New run` only if a user already has at least one influencer

### Optional search
Global search can live here if useful.

---

## Summary strip

Use 3–5 compact summary cards, not giant KPI blocks.

Examples:
- Influencers: total count
- Active runs: currently running or queued
- Outputs generated: recent period
- Failed runs: recent period

These should be small orientation aids, not the focus of the screen.

---

## Section: Active and recent runs

This is the core module of the dashboard.

### Best representation
A structured list or grouped cards with clear status.

### Each run item should show
- run title
- influencer name
- run type
- current status
- progress or stage
- creation time
- output count if completed
- quick action: `Open run`

### Recommended grouping
Either:
- grouped by status, or
- grouped by influencer with a strong visual structure

Since the product is influencer-first, grouping recent runs by influencer is good, but the grouping must be clean and compact.

### What not to do
- Do not make giant visual cards for every run.
- Do not bury progress and status inside decorative layouts.
- Do not overuse thumbnails for list-heavy operational data.

---

## Section: Influencer activity

Show a horizontal row or compact list of influencers with recent activity.

### Each influencer block should show
- avatar
- name
- short descriptor / niche
- current status
- number of recent runs
- latest activity timestamp
- quick action: `Open influencer`

This creates a bridge between the dashboard and influencer management.

---

## Section: Recent outputs

This section should be media-first.

### Show
- latest generated videos/images
- associated influencer
- run reference
- quick preview/open

### Layout
A compact horizontal media strip or a neat 3–4 column grid.

### Important
Keep this section secondary to active runs.
The dashboard should remain an operations page first.

---

## Empty dashboard state

If no influencers exist:
- show a strong onboarding empty state,
- explain that the workflow starts with creating an influencer,
- show one primary CTA: `Create influencer`.

If influencers exist but no runs exist:
- show a lighter empty state in the runs section,
- suggest launching the first run from an influencer or trends page.

---

## PAGE 2 — Influencers list page

## Purpose
This page is the directory of AI personas.
It should feel like the main management surface for influencers.

---

## Layout

Recommended structure:
1. Page header
2. Filter/search row
3. Influencer grid or list

This page should be calm and highly scannable.

---

## Header

### Left side
- Title: `Influencers`
- Subtitle: `Manage personas, references, and generation activity.`

### Right side
- Primary CTA: `Create influencer`

---

## Filter row

Include:
- search by influencer name
- status filter
- niche / category filter if useful
- sort: newest / most active / recently updated

Keep this row compact and useful.

---

## Influencer card design

Each card should feel like a compact identity summary, not a social profile.

### Card structure
Top:
- hero image / avatar
- status chip

Middle:
- influencer name
- short descriptor or niche
- supporting metadata
  - reference asset count
  - total runs
  - latest activity

Bottom:
- primary action: `Open`
- secondary action: `New run`

### Optional card stats
- number of photos/videos in portfolio
- last generated output date

### Visual rules
- Do not use giant cards with excess whitespace.
- Do not overcrowd with too many stat pills.
- Keep the grid consistent.

---

## Empty state

If no influencers exist:
- centered but elegant empty state,
- text explaining that influencers are the foundation of the platform,
- primary CTA: `Create influencer`.

This state must feel polished because first-time users will land here often.

---

## PAGE 3 — Influencer detail page

## Purpose
This page is the control center for one influencer.
It should feel like a real workspace around one persona.

Not a social profile.
Not just a media gallery.
Not just an edit form.

---

## Layout

Recommended structure:
1. Header / hero summary
2. Tab navigation
3. Tab content area

---

## Header / hero summary

### Left side
- larger avatar / hero image
- influencer name
- short description / niche
- status chip
- key summary metadata
  - number of reference assets
  - number of runs
  - number of generated outputs

### Right side actions
- `Edit influencer`
- `Upload reference media`
- `New run`

### Important
This header should be compact and strong.
Do not make it oversized like a social cover page.

---

## Tabs

Recommended tabs:
- Overview
- Portfolio
- Runs
- Outputs
- Settings

### Tab 1 — Overview
This should summarize the influencer.

Include:
- quick identity summary
- most recent runs
- recent generated outputs
- reference portfolio snapshot

Use 3–4 tidy modules.
This should feel like a “home page” for one influencer.

---

### Tab 2 — Portfolio
This is critical.

This tab contains the uploaded **real photos and videos** of the influencer.
These are not generated images.
They are reference media used to define the persona.

#### Portfolio tab should include
- upload area or upload CTA
- photo/video toggle or filter
- media grid
- metadata panel or hover metadata

#### Each asset card should show
- preview thumbnail
- type: photo or video
- title or filename
- upload date
- duration for videos
- optional notes/tag
- actions: preview, replace, delete

#### Why this matters
The portfolio is a core product feature.
It must feel first-class, not like a generic attachment section.

---

### Tab 3 — Runs
Show all runs associated with this influencer.

Best format:
- dense list or table-like cards

Each run row should show:
- run title
- type
- status
- progress
- created date
- outputs count
- open action

This tab must feel clearly connected to the influencer.

---

### Tab 4 — Outputs
This tab shows generated content for this influencer.

Use a media grid with:
- generated image/video preview
- run reference
- created date
- type label
- preview action
- open run action

This tab is for browsing results, not for reference uploads.
It must be visually distinct from the Portfolio tab.

---

### Tab 5 — Settings
Keep this lightweight for now.

Possible fields:
- editable name
- niche / persona summary
- tags
- active/paused state
- simple defaults if they already exist in backend

Do not overdesign advanced controls that do not exist yet.

---

## Create influencer flow

## Purpose
This is the first major flow in the app.
It must be polished and clear.

### Format
Use a modal wizard or a dedicated page flow.
A dedicated page is usually better if uploads are important.

### Steps

#### Step 1 — Basic identity
- influencer name
- short description
- niche / category
- optional tags

#### Step 2 — Reference media upload
- upload photos
- upload videos
- clearly explain these are real reference assets
- show upload progress and previews

#### Step 3 — Review
- summary card
- uploaded media preview strip
- `Create influencer`

### UX notes
- Keep the flow short.
- Do not ask for features that do not exist yet.
- The biggest visual emphasis after name should be media upload.

---

## What not to do on influencer pages

- Do not make the influencer detail page look like Instagram.
- Do not hide Portfolio under a tiny subsection.
- Do not merge reference uploads and generated outputs in one undifferentiated gallery.
- Do not make the influencer list page feel like a contacts app.
- Do not use huge decorative header areas.

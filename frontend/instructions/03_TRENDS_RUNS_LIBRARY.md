# Trends, Runs, and Library Pages

## PAGE 4 — Trends page

## Purpose
The Trends page is the discovery surface.
It helps the user find promising source material and content directions.

The flow should be:
trend -> inspect -> choose influencer -> launch run

It should feel discovery-oriented, but still structured.

---

## Layout

Recommended structure:
1. Header
2. Search/filter row
3. Trend results layout
4. Optional side detail drawer when a trend is selected

---

## Header

### Left side
- Title: `Trends`
- Subtitle: `Browse source ideas and trending content for new generation runs.`

### Right side
- Primary action can be `Refresh trends` or `New run`, depending on product behavior

---

## Search and filters

Support filters such as:
- platform: TikTok / Instagram / X
- hashtag/topic
- media type
- freshness / timeframe
- sort by relevance / popularity / newest

Keep filters usable and compact.
Do not overcomplicate with advanced analytics filters.

---

## Trend results design

A card-based grid works best.

### Each trend card should include
- preview image or video thumbnail
- source platform badge
- trend title or hashtag cluster
- short metadata line
- small reason/context line if available
- actions:
  - `Inspect`
  - `Use in run`

### Card behavior
When the user clicks `Inspect`, open a detail drawer or side panel instead of navigating away immediately.

---

## Trend detail drawer / panel

This is strongly recommended.

### Show
- larger preview
- source metadata
- hashtags/topics
- summary of why the trend matters
- related example assets if available
- influencer selector
- primary CTA: `Create run with this trend`

This keeps the discovery flow fast and modern.

---

## Empty state

If no trends are available:
- explain that trend collection has not produced results yet,
- offer a refresh or retry action,
- keep the tone calm and operational.

---

## PAGE 5 — Runs list page

## Purpose
This is the global run management page.
It gives the user visibility into all generation jobs across influencers.

---

## Layout

Recommended structure:
1. Header
2. Filter/search row
3. Runs list

This page should be denser than gallery pages.
Runs are operational objects.

---

## Header

### Left side
- Title: `Runs`
- Subtitle: `Track queued, running, completed, and failed generation jobs.`

### Right side
- Primary CTA: `New run`

---

## Filter/search row

Filters should include:
- influencer
- status
- run type
- date range if useful
- search by run name or ID

Keep it efficient.
This page should help the user find runs quickly.

---

## Runs list design

Best representation:
- table-like list
- or structured row cards

A dense list is better than a gallery here.

### Each run row should show
- run title
- influencer name
- run type
- status chip
- progress or stage
- created time
- output count
- open action

### Optional secondary metadata
- source platform
- trend label
- duration or item count

### Important
Status and progress must be very easy to scan.
The user should understand the run list in seconds.

---

## PAGE 6 — Run detail page

## Purpose
This page is the execution detail page for one run.
It should feel like a mix of:
- job detail,
- pipeline monitor,
- result viewer.

This is one of the most important screens in the product.

---

## Layout

Recommended structure:
1. Header
2. Main two-column content area or stacked sections
3. Inputs section
4. Progress / pipeline section
5. Outputs section
6. Optional logs or metadata section

---

## Header

### Left side
- run title
- influencer name
- run type
- status chip
- creation timestamp

### Right side
- `Open influencer`
- `Duplicate run` if desired
- `Retry` if failed

Keep actions contextual.
Do not overload.

---

## Section: Inputs

Show the configuration that created the run.

### Include
- influencer used
- selected trend or source asset
- source preview
- prompt/config summary
- any core generation settings already supported

This helps the user understand what happened.

---

## Section: Progress / pipeline

This must be visually strong.

Use one of:
- vertical stepper,
- horizontal pipeline stages,
- stage timeline.

### Example stage model
- Queued
- Fetching source
- Processing source
- Generating output
- Packaging results
- Completed / Failed

### Each stage should show
- stage name
- status
- optional timestamp
- optional duration

### Important
The run detail page should feel alive when a run is running.
This is not just a static detail page.

---

## Section: Outputs

This is a media gallery of generated results.

### Each output card should show
- preview
- type label
- created timestamp
- dimensions / duration if available
- actions: preview, open full, download if available

### Layout
Use a gallery grid.
Videos should have clear play affordances.
Images should support larger preview.

### If no outputs yet
Show a status-aware placeholder such as:
- `Outputs will appear here once generation completes.`

---

## Section: Metadata / logs

Optional for now, but useful if available.

Can include:
- run ID
- source ID
- error summary
- warning state
- raw metadata summary

Keep this lower priority than inputs, progress, and outputs.

---

## Failure state

If a run fails:
- show a clear failure banner,
- identify failed stage if possible,
- provide a `Retry` action,
- show partial outputs only if they exist.

This state must be deliberately designed.

---

## PAGE 7 — Library page

## Purpose
The Library is the structured asset browser for the whole app.
It should let the user browse:
- influencer reference media,
- source assets,
- generated outputs.

It must not feel like an unstructured gallery.

---

## Layout

Recommended structure:
1. Header
2. Filter/search row
3. Asset type segmentation
4. Results grid/list

---

## Header

### Left side
- Title: `Library`
- Subtitle: `Browse reference uploads, source assets, and generated media.`

### Right side
- Primary action: `Upload assets` or `Open influencer`

---

## Segmentation

The library must clearly separate categories.
Use tabs or segmented controls:
- Reference media
- Source assets
- Generated outputs

This is extremely important.
Do not mix all file types into one undifferentiated grid by default.

---

## Filters

Support:
- influencer
- asset category
- media type: image / video
- run association
- source/generated state

---

## Asset card design

### Each card should show
- media preview
- title or filename
- influencer association
- type/category label
- upload/create date
- source run if relevant
- preview/open actions

### Behavior
Preview should open in a modal or side panel.
Do not make the user leave the library for every small inspection.

---

## What makes a good library page

The user should be able to answer:
- Is this a reference asset or a generated output?
- Which influencer does it belong to?
- Which run created it?
- Can I preview it quickly?

If the screen cannot answer those quickly, it is poorly designed.

---

## What not to do on these pages

- Do not make trends page look like a social media feed clone.
- Do not make runs page into a media gallery.
- Do not make run detail page feel like a generic settings form.
- Do not make library the visual center of the whole product.
- Do not mix reference and generated assets without clear segmentation.

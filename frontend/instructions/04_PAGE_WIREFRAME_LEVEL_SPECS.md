# Page Wireframe-Level Specifications

This file describes each major page almost like a low-fidelity design blueprint.
Use it when implementing UI layouts.

---

## 1. Dashboard wireframe

### Row 1: page header
Left:
- title
- subtitle

Right:
- create influencer button
- new run button if applicable

### Row 2: compact stats strip
4 compact cards max:
- total influencers
- active runs
- completed today / recent
- failed runs

### Row 3: main content split
Left large column:
- recent runs module

Right narrower column or lower section:
- influencer activity
- recent outputs snapshot

### Recent runs module structure
- section title
- filter by status if needed
- stacked rows

Each row:
- run title
- influencer
- status chip
- progress bar or stage text
- time
- open action

### Influencer activity module structure
Each item:
- avatar
- name
- descriptor
- recent runs count
- open action

### Recent outputs module structure
- 3–6 latest media previews
- influencer label
- open action

---

## 2. Influencers list wireframe

### Row 1: header
Left:
- title
- subtitle

Right:
- create influencer button

### Row 2: controls
- search input
- status filter
- sort dropdown

### Row 3+: influencer grid
3–4 cards per row on desktop depending on width.

Each card:
- media thumbnail
- status chip at top-right or top-left
- influencer name
- short descriptor
- metadata row
  - reference count
  - runs count
  - latest activity
- footer actions
  - open
  - new run

---

## 3. Influencer detail wireframe

### Row 1: header summary block
Left:
- avatar / image
- name
- descriptor
- status
- key stats

Right:
- edit influencer
- upload reference media
- new run

### Row 2: tabs
- overview
- portfolio
- runs
- outputs
- settings

### Overview tab
Use a 2x2 module arrangement:
- identity summary
- reference portfolio snapshot
- recent runs
- recent outputs

### Portfolio tab
Top controls:
- upload button
- image/video filter
- sort

Below:
- media grid

Each media card:
- preview
- asset name
- type
- upload date / duration
- preview / replace / delete

### Runs tab
Dense list with:
- title
- status
- type
- created date
- outputs
- open action

### Outputs tab
Media grid with generated outputs only.

### Settings tab
Simple form surface.

---

## 4. Create influencer wireframe

### Step layout
Top:
- stepper or progress indicator

Main card:
- current step contents

Bottom:
- back / next / create buttons

### Step 1
- name input
- description input
- niche selector or text input

### Step 2
- upload zone for photos
- upload zone for videos
- uploaded items preview list/grid

### Step 3
- summary block
- preview of uploaded assets
- create influencer CTA

---

## 5. Trends page wireframe

### Row 1: header
Left:
- title
- subtitle

Right:
- refresh or new run

### Row 2: controls
- search
- platform filter
- hashtag/topic filter
- sort

### Row 3+: trend grid
3-column desktop grid.

Each trend card:
- preview
- platform badge
- title / hashtag cluster
- metadata line
- inspect button
- use in run button

### Detail drawer
When one trend is selected:
- large preview
- hashtags
- source details
- influencer selector
- create run CTA

---

## 6. Runs list wireframe

### Row 1: header
- title
- subtitle
- new run button

### Row 2: controls
- search
- influencer filter
- status filter
- type filter

### Row 3+: run table/list
Columns or row sections:
- run title
- influencer
- type
- status
- progress
- created
- outputs
- open

Use clean dividers and restrained row height.

---

## 7. Run detail wireframe

### Row 1: header
Left:
- run title
- influencer
- type
- status
- created time

Right:
- retry / duplicate / open influencer

### Row 2: top information band
Two columns:
- inputs summary
- progress summary

### Row 3: detailed progress section
- stage timeline or stepper

### Row 4: outputs gallery
- section title
- media cards

### Row 5: metadata/log section
- compact technical details if useful

If running, the outputs section may show placeholder cards or an empty in-progress state.

---

## 8. Library wireframe

### Row 1: header
- title
- subtitle
- upload assets button if applicable

### Row 2: segmented category control
- reference media
- source assets
- generated outputs

### Row 3: filters
- influencer
- image/video
- run filter
- search

### Row 4+: results grid
Each card:
- preview
- label/category
- influencer
- date
- run/source metadata
- preview action

---

## Shared implementation rules

### Do not create giant decorative blocks.
Every block must earn its space.

### Do not make every page use the exact same card formula.
List pages, detail pages, discovery pages, and media pages should feel intentionally different.

### Keep top-level actions obvious.
One primary action per page is enough in most cases.

### Use tabs to create clarity.
Do not cram all influencer content into one endless page.

### Separate reference media and generated outputs everywhere.
This distinction is essential to the product.

# AI Influencer Platform — Agent Brief

## What went wrong in the previous design

The previous UI failed because it behaved like a generic mock dashboard instead of a product designed around the real workflow.

Main problems to avoid:

1. The left sidebar was treated like a marketing panel.
   - It was too wide.
   - It contained a giant slogan block.
   - It visually dominated the application.
   - It reduced space for real work.
   - It made the app feel like a landing page instead of a workspace.

2. The page hierarchy was weak.
   - The screen did not clearly communicate where the user was.
   - The main content felt like one flat library grid.
   - There was no strong separation between navigation, page header, filters, and content.

3. The app was not truly influencer-first.
   - The design did not make influencer creation and influencer management feel like the central workflow.
   - The UI did not make it obvious that trends and runs should happen around an influencer.

4. The pages were not designed as real product surfaces.
   - The design used similar card patterns everywhere.
   - There was not enough distinction between overview pages, detail pages, and execution pages.
   - Runs did not feel like a real pipeline or job system.

5. The library page was too generic.
   - It looked like a media grid, not like a structured asset management interface.
   - Uploaded references, source assets, and generated outputs were not clearly separated.

This redesign must fix those issues.

---

## Product objective

Design a modern single-user web app for creating and managing AI influencers.

The user can:
- create multiple influencers,
- upload real reference photos and videos for each influencer,
- browse trends from TikTok / Instagram / X,
- launch runs based on those trends,
- monitor run progress,
- inspect generated image/video outputs.

This is a working product UI, not a marketing site.
Use mock data for now, but the structure must be suitable for real backend integration later.

---

## Product model

The product revolves around five main entities:

### Influencer
A digital persona with identity data and a portfolio of uploaded real photos/videos.

### Trend
A discovered trend, hashtag, topic, or source content candidate.

### Run
A generation job for one influencer, using one source/trend or prompt configuration.

### Asset
A file inside the system, such as:
- influencer reference photo,
- influencer reference video,
- downloaded source media,
- generated image,
- generated video.

### Output
A generated result produced by a run.

---

## Product principles

### 1. Influencer-first
The first meaningful object in the app is always the influencer.
The user should never feel that runs or trends exist independently of influencer management.

### 2. Workspace, not dashboard theater
This should feel like a calm, professional AI workspace.
Do not use oversized promo text, decorative side panels, or fake KPI-heavy layouts.

### 3. Media-first
Images and videos are central.
Previews, thumbnails, hover states, preview drawers, and asset organization must feel polished.

### 4. Clear object hierarchy
Each page must make it obvious whether the user is looking at:
- an overview,
- a list of objects,
- one influencer,
- one run,
- a library filter view.

### 5. Calm modern AI design language
The UI should feel inspired by products like ChatGPT, Claude, Linear, Notion, and high-quality modern SaaS tools:
- restrained color,
- spacious layout,
- clear typography,
- minimal chrome,
- strong hierarchy,
- low visual noise.

### 6. Strong structure over generic beauty
Do not optimize for flashy aesthetics.
Optimize for clarity, usability, and product logic.

---

## Navigation structure

Use a **narrow functional left sidebar**, not a hero panel.

Primary navigation:
- Dashboard
- Influencers
- Trends
- Runs
- Library
- Settings

### Sidebar rules
- Width should be compact.
- It should contain logo/product name at the top.
- Navigation labels should be short and clean.
- Active page should have a subtle highlighted state.
- No giant marketing copy block.
- No giant descriptive paragraph in sidebar.
- No oversized cards inside sidebar.
- Any environment indicator such as "Mock mode" should be small and secondary, preferably near the bottom or in the top bar.

---

## Top bar rules

Every major page should have a page-level header area.

The top bar / page header may include:
- page title,
- concise page subtitle,
- search,
- primary CTA,
- secondary CTA if truly needed.

### Primary CTA rules
There should usually be **one dominant action** per page.
Examples:
- Dashboard: `Create influencer`
- Influencers: `Create influencer`
- Trends: `New run`
- Runs: `New run`
- Library: `Upload assets` or `Open influencer`

Avoid having too many equal-weight buttons in the top right.

---

## Deliverables expected from the agent

The agent must design the app page by page.
Not a single mock collage.
Not one generic page reused everywhere.

The agent must produce clearly differentiated designs for:
1. Dashboard
2. Influencers list
3. Influencer detail
4. Create influencer flow
5. Trends list / discovery
6. Runs list
7. Run detail
8. Library
9. Global patterns / design system

Each page must define:
- layout,
- sections,
- hierarchy,
- cards/rows/modules,
- CTAs,
- empty states,
- loading states,
- status states,
- what not to do.

---

## Non-goals

Do not design for:
- multiple accounts,
- teams,
- approvals,
- publishing pipelines,
- voice management,
- multiple persona variants,
- collaboration,
- billing,
- advanced analytics.

These are future concerns and must not distort the current product design.

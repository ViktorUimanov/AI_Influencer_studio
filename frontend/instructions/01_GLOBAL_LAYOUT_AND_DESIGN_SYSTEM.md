# Global Layout and Design System

## 1. Overall layout structure

Use a three-part shell:

1. **Left sidebar** — compact navigation
2. **Top header area** — page title, search, page actions
3. **Main content area** — page-specific layout

### Recommended proportions
- Sidebar: narrow and stable
- Main content: dominant area
- Top header: modest height, not oversized

The app must feel like the content has room to breathe.
Avoid wasting horizontal space on decorative blocks.

---

## 2. Sidebar design

### What it should contain
- Product name / compact logo
- Main navigation items
- Small settings entry
- Small environment indicator if needed

### What it must not contain
- giant tagline
- long product explanation
- oversized promo panel
- large descriptive copy
- stacked secondary widgets

### Visual behavior
- Quiet, low-contrast background
- Active item: subtle highlight or soft pill
- Hover states: restrained
- Icons optional, but should be minimal

This sidebar should feel closer to Linear / ChatGPT app navigation than to a landing page rail.

---

## 3. Page header pattern

Each page should begin with a proper header block in the main content area.

### Header structure
- Eyebrow label (optional)
- Page title
- One-sentence subtitle
- Right side actions

### Example
For Influencers page:
- Title: `Influencers`
- Subtitle: `Create and manage AI personas, references, and generation activity.`
- Primary CTA: `Create influencer`

This gives each page a clear identity.

---

## 4. Visual style

### Tone
- premium
- calm
- modern
- understated
- product-focused

### Color approach
- neutral or slightly warm/cool dark palette
- restrained accent color
- use color mostly for state and primary actions

### Good uses of color
- active nav state
- primary CTA
- run status
- selection states
- filter chips when active

### Avoid
- rainbow accents
- multiple competing accent colors
- loud gradients everywhere
- saturated panel backgrounds

---

## 5. Typography

### Tone
Use clean, highly readable typography.

### Hierarchy
- Large page title
- Strong section titles
- Compact card titles
- Muted metadata text
- Clear labels

Typography should do real hierarchy work.
Do not rely only on boxes and borders.

---

## 6. Spacing and density

The app should not feel cramped, but it should also not feel empty.

### Desired density
- moderate
- elegant
- media-friendly
- scan-friendly

### Use spacing to separate:
- page header from content
- filter bar from results
- section groups from one another
- primary metadata from secondary metadata

---

## 7. Core reusable UI modules

### A. Status chip
Used for runs, assets, influencers.
Examples:
- Draft
- Active
- Running
- Completed
- Failed
- Processing

Status chips must be clear and consistent.

### B. Filter chip row
Used on list pages.
Should support:
- dropdown filters
- quick chips
- search
- sort

### C. Media card
Used for assets and outputs.
Should include:
- preview thumbnail
- type label
- title
- supporting metadata
- one or two actions max

### D. Table/list row
Used for runs and structured lists.
Should be denser than gallery cards.

### E. Section card / surface
A container with a title and optional action.
Useful for summary sections on overview pages.

### F. Empty state block
Should include:
- clear explanation,
- one primary action,
- minimal illustration or icon if desired.

---

## 8. Interaction rules

### Keep actions focused
Every card should not have 5 equal buttons.
Prefer:
- open
- preview
- secondary overflow menu

### Progressive disclosure
Show details when needed:
- drawers
- modals
- tabs
- expansion panels

Do not overload the default list state.

### Search and filters
Search should be global or page-specific where appropriate.
Filters should feel useful, not decorative.

---

## 9. States the entire system must support

### Empty states
- no influencers yet
- no runs yet
- no trends yet
- no library results
- no outputs yet

### Loading states
- skeleton cards
- skeleton tables
- preview loading placeholders

### Error states
- media unavailable
- run failed
- trend fetch failed
- upload failed

### Status states
- queued
- running
- completed
- failed
- archived

These states must be designed deliberately, not as an afterthought.

---

## 10. Responsive behavior

Primary target is desktop.
Tablet behavior should degrade gracefully.

### Desktop
- sidebar visible
- filters inline
- grids and split views allowed

### Narrow screens
- sidebar can collapse
- filters can stack
- media cards can become 2-column or 1-column

Do not design mobile-first social UI. This is a desktop workspace.

---

## 11. What the overall app should feel like

The user should feel:
- oriented,
- calm,
- in control,
- focused on one workflow at a time,
- supported by the interface rather than distracted by it.

The application should look like a real product that could ship, not like a generic AI mockup.

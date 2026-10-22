---
name: u2-design-system
description: Visual design system for the U2 Live Analytics report — palette, typography, grid, page template, chart rules and accessibility checklist. Use when creating the theme JSON, wireframes or any report page.
---

# U2 design system

Mood: a dark music-magazine infographic (decision by Vini, T-30 feedback 2026-10-21). Informal, not a corporate
dashboard: big conversational headlines and callout numbers, concert photos and tour icons placed inside the data
story, lots of dark space, one warm accent for "what matters", data in light neutrals.

## Editorial infographic style

- **One story per page:** a finding-style headline in conversational English (from a measure), 1–3 huge callout
  numbers, then the supporting charts. Not a grid of equal cards.
- **Images inside the story:** a photo next to or under the number it illustrates (era photo + era numbers, Sphere photo
  + residency numbers); circular era badges as the era picker; tour icons in tables (SVG `Tour Icon` measure), along the
  timeline (`timeline_tours.svg`) and in headers. Photos never sit behind dense charts (tables, heatmaps, maps).
- **No boxes:** visuals have no background, border or gridlines (theme default); separate groups with 40–64 px of
  dark space; hairlines only where a table needs them.
- **Asymmetric layouts:** photos may bleed off the canvas edge; one wide story column + one narrower data column.
- **Hand-feel annotations:** short Segoe UI Semibold italic notes in `accent` with the hand-drawn `arrow_*.svg`
  images; any number in them comes from a measure. Arrows point at stable things (highlighted marks, callouts).
- **Data-story layout** (Vini, after the DataViz World Champs EU 2025 finalists): top tab navigation → headline →
  "First glimpse" paragraph with bold key numbers → KPI tiles (icon, number, delta with ▲/▼) → charts, each with 1–2
  sentences of explanation and an (i) button for definitions. One large anchor per page (photo, map or ticket);
  head-to-head blocks with the difference as a big number; outliers in `accent` with a note; choose-your-axis via
  field parameters.
- **Build:** photo (image visual) → scrim PNG (image visual, scaling Fit) → transparent card/text box. Circular crops are
  pre-made PNGs (no masks in Power BI). Era photo swaps use bookmarks. Tag every element in the wireframes as
  NAT (native), IMG (image visual), SVG (SVG data-URI measure in a table/card), HTML (HTML measure in
  **HTML Content Secure**, the certified edition) or DEN (**Deneb**, certified). Only certified custom visuals.
  Certified visuals cannot load URLs or registered resources: images inside HTML/Deneb are data URIs from the model
  (glyph SVG markup via a SWITCH measure; small 480 px photos ≤ 35 KB as base64 chunks). Every HTML/DEN block has a
  native fallback in the same frame. `docs/design/wireframes.md` §2 has the details and limits.

## Imagery (decision by Vini, 2026-10-21)

- **Licence:** only freely licensed images: Wikimedia Commons files under CC BY, CC BY-SA, CC0 or public domain.
  Never NC/ND licences, press photos, fan-site images, album art or official artwork without such a licence.
- **Credits:** every image used gets a row in `docs/design/images/credits.csv`
  (`file,title,author,licence,source_url,used_on`) and is credited on page 9 "About the data" and in the README.
  CC BY-SA images stay under CC BY-SA; note any changes made (crop, darken, desaturate).
- **Concert photos:** keep them vivid; never darken a whole photo. Text or data on a photo sits on a local scrim
  (`scrim_from_*.png`: `bg` at 92% fading to 0) inside the part where the scrim is ≥ 85% opaque (its first half), or on a
  small `surface` pill. T-29 measured the worst case (white pixel): 92% → text 13.27, muted 6.58, accent 7.78; 85% →
  10.50 / 5.20 / 6.16. Prefer one photo per era or tour so the image reinforces the page's filter context.
  Keep files ≤ 300 KB (JPG, 1280 px wide).
- **Tour icons:** U2 tours have their own logos/icons. Search Wikimedia Commons per tour; use one only if its file
  page shows a free licence or public domain (e.g. `PD-textlogo`). For tours without a free icon, draw a simple
  original monochrome glyph that evokes the tour (not a copy or trace of the official logo) and record it as
  "original, project licence" in `credits.csv`.
- Images live in `docs/design/images/` and are registered in the report under `StaticResources/RegisteredResources/`.

## Palette (contrast validated in T-29, ratios in `docs/design/wireframes.md` §5; final after Vini's T-30 approval)

| Token | Hex | Use |
| --- | --- | --- |
| `bg` | `#0F1115` | page background; visuals sit directly on it; scrim colour |
| `surface` | `#181B21` | small pills behind text on busy photos (visuals themselves have no background) |
| `surface-2` | `#20242C` | tooltips, applied filter cards, totals |
| `border` | `#2A2F38` | hairlines only where a table needs them |
| `text` | `#ECEDEF` | primary text |
| `text-muted` | `#A3A9B3` | labels, axis text (lightened from `#9AA0AA` so it passes over photo overlays) |
| `neutral` | `#6E7581` | non-highlighted marks, "other" categories (≥ 3:1 on `surface`) |
| `accent` | `#F2A93B` | highlight: hero number, selected item, annotations and arrows; one series at most |
| `data-1`…`data-6` | `#6FA8DC` `#93C47D` `#E06666` `#B4A7D6` `#76D7C4` `#F6B26B` | categorical series (eras, continents); never more than 6 |
| `seq-low` → `seq-high` | `#1E2A3A` → `#6FA8DC` | heatmaps (song × year) |

Eras (fixed order, from `seeds/tours.csv`, column `era`; a tour attribute, so shows without a tour have none):
1976-1980 Beginnings · 1980-1985 Boy to Unforgettable Fire · 1986-1990 Joshua Tree years · 1992-1998 Zoo TV and PopMart ·
2001-2006 Elevation and Vertigo · 2009-2011 U2 360 · 2015-2019 Innocence and Experience · 2023-present Sphere and after.
Eight eras > six categorical colours, so eras are never colour-coded: show them as text (slicer, labels, tooltips)
or as two alternating neutral tones.

## Typography

Headlines and callout numbers: **DIN** (in Power BI's font list, renders in Desktop and the service), headline
32–40 pt, callouts 40–56 pt. Body, labels, tables: Segoe UI / Segoe UI Semibold (visual titles 13 pt, standfirst 12 pt,
labels 10 pt, footer 9 pt). Annotations: Segoe UI Semibold italic 12–14 pt in `accent`. Fonts outside Power BI's list
(e.g. hand-written Segoe Print) only render where installed, so they are not used. Sentence case everywhere.

## Grid and page template (1280 × 720)

- 24 px outer margin (photos may bleed to the canvas edge), 8 px grid, 16 px minimum gutter, 40–64 px between groups.
- Headline block top-left (or top-right when the photo is on the left), max 2 lines; standfirst + filters in effect below.
- Page navigation as small text links top right, same place on every page.
- Footer line 700 px: "Data: setlist.fm, MusicBrainz · refreshed <date> · photo credits on page 9".
- Max 6 data visuals per page (photos, scrims, arrows, headline not counted); reading order follows the story,
  headline first, decorative images last in tab order.

## Chart rules

- **Lists vs rankings (T-36, Vini):** tables and matrices that list songs, cities, covers, guests, rarities or tours
  show **all** rows, sorted, with a vertical scrollbar on purpose; the title states the total from a measure
  ("All 384 cities, most shows first"). Bar charts that rank items keep a **strict, tie-safe top N** (rank measure,
  ties broken by name) with no scrollbar, and their title says "top N". Never a Top N that scrolls.
- Visual headers (hover icons) are off on every visual; right-click menus, drill-through and tooltips stay.
- All data visuals on a page filter each other (interaction type DataFilter, not highlight).

- Bars sorted by value; start axes at zero for bars and columns.
- Highlight one thing with `accent`, everything else neutral.
- Label directly instead of legends when there are ≤ 4 series.
- Tooltips: question-relevant fields only, using measure descriptions.
- Maps: bubble size = shows; no filled choropleth for venue data.

## Accessibility checklist (per page)

- [ ] Text contrast ≥ 4.5:1 (check `text`, `text-muted`, `accent` on `bg`, and on every scrim at the text position).
- [ ] No meaning carried by color alone (labels, markers or patterns as second cue).
- [ ] Every data visual has alt text.
- [ ] Tab order set top-left to bottom-right.
- [ ] Readable at 100% zoom on a 1366-px-wide laptop.
- [ ] Slicer and filter state visible in the subtitle.
- [ ] Text and data over photos still pass 4.5:1; every image on the page is in `credits.csv` and has alt text.

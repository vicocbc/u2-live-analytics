# Report wireframes (T-29, revision 3: dark editorial infographic)

Status: **for Vini's approval (T-30)**. Revision 2 followed Vini's T-30 feedback (images inside the data story,
informal magazine tone); revision 3 adds his second direction: the data-story layout of the Power BI DataViz World
Champs EU 2025 finalists (intro paragraph, explanatory text beside each chart, KPI tiles with icons and deltas,
(i) buttons, top tab navigation, head-to-head comparisons, big callout numbers, outlier highlighting, choose-your-axis)
and HTML/SVG measures for infographic blocks. We stay dark.

Preview of all 9 pages and the image set: open `docs/design/preview.html` in a browser on Windows (the
DIN-like Bahnschrift font stands in for Power BI's DIN). The button "Show how each block is built" labels every block.
Theme: `fabric/rpt_u2_live.Report/StaticResources/RegisteredResources/u2-theme.json`. Images: `docs/design/images/`
(licences in `credits.csv`, coverage in `images/README.md`).

Field names are the planned Gold/model names from SPEC-04/SPEC-05; every field is re-checked against the TMDL before a
visual is built (T-32..T-34). **(request)** = not in SPEC-05 yet, see [Requests](#7-requests).

## 1. Style

- **Data story per page.** Top tab navigation → one conversational headline (a finding) → a short "First glimpse"
  paragraph with the key numbers in bold → 1–3 big callouts or KPI tiles (icon, number, delta) → charts, each with
  one or two sentences of explanation beside it and an (i) button for definitions.
- **One large illustrative anchor per page**: a vivid concert photo (with numbers laid over it on a local scrim), the
  venue map, or the setlist ticket. Charts sit beside it, not on top of it.
- **Images inside the story**: era photo + era numbers, Sphere photo + residency numbers, tour icons in tables, along the
  timeline and on tickets, era badges as the era picker, a photo card with a number and caption.
- **Comparisons and outliers**: head-to-head blocks (residency vs. touring) with the difference as a big number
  ("+66 pp"); the outlier in a chart in `accent` with a hand-style note; choose-your-axis via field parameters.
- **No boxes, informal tone**: visuals have no background, border or gridlines; dark space separates groups; short
  italic notes in `accent` with hand-drawn arrows; headlines and numbers in DIN.

## 2. How things are built (Power BI feasibility)

Five building blocks; every element in §4 is tagged with one of them.

| Tag | Building block | Use it for | Limits |
| --- | --- | --- | --- |
| **NAT** | Native visual (card (new), bar, area, scatter, matrix, table, map, page navigator, buttons, bookmarks, field parameters) | All real charts and slicing; headlines (card on a text measure, DIN); tab navigation; (i) buttons (button with tooltip); choose-your-axis (field parameters) | No images inside charts; no gradients on shapes. |
| **IMG** | Image visual with a registered resource (photo, scrim PNG, badge PNG, arrow SVG) | Large photos, scrims, era badges (as image buttons), arrows | Static; one image per visual; swapped only by bookmarks. |
| **SVG** | Measure returning an SVG data URI, data category *Image URL*, in a native table/matrix/card | Tour icons in table rows and cards, small sparklines | Image cell size is capped by the row height; images in a table are not keyboard-readable (alt text on the visual). |
| **HTML** | Measure returning HTML, rendered by **HTML Content Secure** (Daniel Marsh-Patrick; the Microsoft-certified edition on AppSource) | Infographic blocks: "First glimpse" paragraph with bold numbers, KPI tiles with icon + delta, photo + number + caption card, head-to-head comparison, setlist ticket stub | Certified edition = sanitised subset of HTML/CSS/SVG, no scripts, **no external requests**; images must be data URIs. Export to PDF/PowerPoint works for the certified edition. The non-certified "HTML Content" edition is not used. |
| **DEN** | **Deneb** (Vega-Lite; certified on AppSource) | Shows per year with tour icons on the same axis (bars + `path` marks drawn from the glyph paths), so icons stay aligned whatever the filter | Certified build blocks external URLs; image marks need data URIs; glyphs are drawn as SVG paths (no images needed). Specs are JSON in the report, maintained by hand. |

**Decisions**

- Only certified custom visuals (HTML Content Secure, Deneb), so the report works in the service, in exports and on a
  public portfolio without "uncertified visual" warnings. Both must be added from AppSource in Desktop (T-31 by Vini).
- **Images in HTML/Deneb come from the model as base64 data URIs** (the certified visuals cannot load URLs, and they
  cannot read the report's registered resources):
  - Tour glyphs: plain SVG markup, ~0.5 KB each, returned by a DAX `SWITCH` on `tour_name` (measure `Tour Icon SVG`;
    `Tour Icon` = the same as `data:image/svg+xml;utf8,` URI for native tables). No table change needed.
  - Photos inside HTML blocks: small versions only (480 px wide JPG, ≤ 35 KB → ≈ 47,000 base64 characters), at most
    ~10 such photos (≈ 0.5 MB in the model). Stored as chunks in a small table `report_image_chunk(image_id, chunk_no,
    chunk varchar(8000))` (warehouse `varchar` tops out at 8,000 characters), reassembled by
    `CONCATENATEX(..., chunk, "", chunk_no)`. The table is loaded from `docs/design/images/` files by a notebook or seed
    (owner and Gold contract to be agreed with the data-engineer and data-analyst).
  - Large photos (heroes, the Sphere photo) stay native IMG with registered resources; no base64.
- **Spike before building (first step of T-32):** one page with HTML Content Secure showing an `<img src="data:…">`
  and inline SVG, and one Deneb chart with path marks; check Desktop, the service and PDF export. If the sanitiser
  rejects data-URI images, every HTML photo block falls back to IMG + NAT card in the same position (already laid out).
- Fonts: DIN and the Segoe UI family are in Power BI's font list and render everywhere (native visuals). Inside HTML
  Content the font is whatever the viewer has: CSS `font-family: DIN, Bahnschrift, "Segoe UI", sans-serif`.
  Hand-written fonts are not used (render only where installed).

## 3. Page template (all pages)

Canvas 1280 × 720, 8 px grid, 24 px outer margin (photos may bleed to the edge).

| Block | Position | Tag |
| --- | --- | --- |
| Tab navigation (8 pages, current underlined in `accent`) | 40, 12 (or above the text column when the photo is on the left) | NAT page navigator |
| Headline (finding, DIN 34, max 2 lines) | 40, 60, ≤ 640 wide | NAT card on `Headline pNN` |
| "First glimpse" / standfirst paragraph with bold numbers and filters in effect | under the headline, ≤ 640 wide, 2–3 lines | HTML (fallback: NAT card) |
| Chart explanation (1–2 sentences) + (i) | beside or above each chart | NAT text box / card on a text measure; (i) = NAT button with tooltip |
| Footer: "Data: setlist.fm, MusicBrainz · refreshed <date> · photo credits on page 9" | y 700 | NAT card |

Decorative images (photos, scrims, arrows) carry alt text "Decorative: …" with the credit and come last in tab order.
Max 6 data visuals per page (decorative images, headline, paragraphs and footer not counted).

## 4. Pages

Coordinates are x, y, w, h on the 1280 × 720 canvas. Numbers and song names in the sketches are placeholders.

### Page 1 · Overview (`p01_overview`) — Q1, Q2

```
 [Overview|On the road|Songs|Albums|Setlists|Sphere|Shows|About]   ┌ HERO PHOTO (bleeds) ───────┐
 FIFTY YEARS ON THE ROAD, AND THE HITS NEVER LEFT THE SET (DIN)    │ ░scrim  U2 360° claw, or   │
 FIRST GLIMPSE  From Dublin clubs in 1976 to … 1,875 shows …       │ ░       the era's photo    │
 🎫 1,875   ♪ 388   📍 61     ← KPI tiles: icon · number · delta  │░░░░░ bottom scrim ░░░░░░░░ │
 PICK AN ERA (i)  ◯ ◯ ◯ ◯ ◯ ◯ ◯ ◯                                 │ THE TEN SONGS PLAYED MOST  │
  ↙ "1981: 150 shows, from the back of a van"   Each bar is a year…│ 1 Pride ████████ 1,130     │
 ▂▃▅█▆▃ shows per year, era tones, outlier in accent              │ 2 …                        │
 ⊙ ⌁ ▤ ⚑ ♥ ▭ ◠ ≋  tour icons at tour starts (same chart)           │ 10 Elevation ███           │
```

| Element | x, y, w, h | Tag | Fields / content | Q |
| --- | --- | --- | --- | --- |
| Hero photo (default + 8 era heroes, one visible per bookmark) | 640, 0, 640, 392 | IMG + BM | `photo_360_2010_rome.jpg`; era heroes per `credits.csv` | — |
| Scrims | left 640, 0, 300, 392 · bottom 640, 112, 640, 280 · top 640, 0, 640, 96 | IMG | `scrim_from_left/bottom/top.png` | — |
| `p01_nav` | 40, 12, 560, 32 | NAT page navigator | — | — |
| `p01_headline` | 40, 60, 580, 80 | NAT card | `Headline p01` **(request)** | Q1 |
| `p01_first_glimpse` | 40, 142, 560, 72 | HTML | `First Glimpse p01` **(request)**: sentence with `Shows`, `Countries`, top song | Q1, Q2 |
| `p01_kpi_tiles` | 40, 236, 576, 96 | HTML (fallback NAT card (new) with images) | `KPI Tiles p01` **(request)**: icons `icon_kpi_*.svg` inline + `Shows`, `Distinct Songs`, `Countries` + delta vs previous era (`... vs Previous Era` **(request)**) | Q1, Q2 |
| `p01_era_badges` | 40, 362, 520, 72 | IMG buttons → 8 BM (era filter + hero swap); (i) NAT button | `badge_era1_glyph.svg`, `badge_era2..8_*.png` | Q1 |
| `p01_shows_per_year` | 28, 448, 844, 244 | **DEN**: bars by year (era tones, busiest year `accent`) + tour glyph paths at tour start dates under the axis | `dim_date[year]`, `Shows`, `dim_tour[first_show_date]`, `Tour Icon Path` **(request)**, `era_order` | Q1 |
| `p01_busiest_note` + arrow | 228, 440, 300, 40 · arrow 132, 440 | NAT card (italic `accent`) + IMG `arrow_curve_down_left.svg` | `Busiest Year Text` **(request)** | Q1 |
| `p01_chart_note` | 560, 452, 300, 40 | NAT text box + (i) | static explanation (no numbers) | — |
| `p01_top_songs` | 904, 288, 340, 400 | NAT bar chart, Top N 10, rank labels, #1 `accent`; sits on the photo's bottom scrim | `dim_song[song_title]`, `Performances` | Q2 |

Fallback for `p01_shows_per_year` without Deneb: NAT column chart (x-axis fixed 1976–2027) + IMG `timeline_tours.svg`.

### Page 2 · On the road (`p02_on_the_road`) — Q7

Anchor: the venue map (large, dark, no frame).

| Element | x, y, w, h | Tag | Fields | Q |
| --- | --- | --- | --- | --- |
| `p02_headline` + `p02_first_glimpse` | 40, 60, 680, 120 | NAT card + HTML | `Headline p02`, `First Glimpse p02` **(requests)** | Q7 |
| `p02_venues_map` | 24, 192, 744, 504 | NAT Azure map, bubbles = `Shows`, grayscale dark | `dim_venue[latitude]`, `[longitude]`, `[venue_name]`, `Shows` | Q7 |
| Crowd photo card | 800, 0, 480, 216 | HTML photo card (base64 480 px) — fallback IMG + SCR + NAT card | `photo_innocence_experience_2015_antwerp.jpg`; `Top City Text` **(request)** | Q7 |
| `p02_cities_table` | 800, 232, 456, 256 | NAT table, data bars; outlier city `accent` | `dim_venue[city_name]`, `[country_name]`, `Shows`, `First Show Date`, `Last Show Date` | Q7 |
| `p02_continent_decade` | 800, 504, 456, 192 | NAT 100% stacked column, direct labels + explanation text | `dim_date[decade]`, `dim_venue[continent]`, `Shows` | Q7, Q1 |

### Page 3 · The songs (`p03_the_songs`) — Q2, Q3, Q9

Anchor: band photo (JT 2017, Bonnaroo) with the #1 song callout on its scrim.

| Element | x, y, w, h | Tag | Fields | Q |
| --- | --- | --- | --- | --- |
| Band photo + scrim + `p03_top_song_callout` | 0, 0, 520, 280 | IMG + IMG scrim + NAT card | `photo_joshua_tree_2017_manchester_tn.jpg`; `Top Song Text` **(request)** | Q2 |
| `p03_headline` + `p03_first_glimpse` | 552, 60, 704, 112 | NAT card + HTML | `Headline p03`, `First Glimpse p03` **(requests)** | Q2 |
| `p03_explore_scatter` | 552, 184, 704, 280 | NAT scatter with **choose-your-axis**: field parameter X (`first_release_year`, `live_debut_date` year), field parameter Y (`Performances`, `Shows`, `Years Since Last Played`); retired songs hollow (`Is Retired` **(request)**); outliers labelled | `dim_song[song_title]` | Q2, Q3 |
| `p03_song_ranking_table` | 24, 296, 496, 400 | NAT table, data bars, drill-through to p07 | `dim_song[song_title]`, `dim_album[album_title]`, `Performances`, `[live_debut_date]`, `[last_played_date]`, `Years Since Last Played` | Q2, Q3 |
| `p03_rarities` | 552, 480, 336, 216 | NAT table + explanation text | `dim_song[song_title]`, `Performances`, `Last Show Date` (filtered on `Rarities`) | Q2 |
| `p03_covers_guests` | 904, 480, 352, 216 | NAT table | `dim_song[cover_artist]`, `Covers Played`, `fact_performance[guest_artist]`, `Guest Appearances` | Q9 |

### Page 4 · Albums on stage (`p04_albums_on_stage`) — Q4, Q5

```
 [tabs]                                                    ┌ HTML PHOTO CARD (Zoo TV, Kiel) ┐
 THE EIGHTIES NEVER LEFT THE SETLIST (DIN)                 │ ░░ 41%  of Zoo TV performances │
 Every new album gets its moment, then the 1980s … (HTML)  │ ░░ came from Achtung Baby      │
 Share of songs played … (i)    ↘ 2017: the 80s still …   └────────────────────────────────┘
 ███ 100% stacked area, direct labels ███                  How much of each tour promoted … (i)
 Which albums stay (i)   heatmap        Read across a row… ◇ icon · tour · bar · % (ⓐ marker)
```

| Element | x, y, w, h | Tag | Fields | Q |
| --- | --- | --- | --- | --- |
| `p04_headline` | 40, 60, 720, 44 | NAT card | `Headline p04` **(request)** | Q5 |
| `p04_first_glimpse` | 40, 104, 720, 48 | HTML | `First Glimpse p04` **(request)** | Q5 |
| `p04_album_share_area` | 40, 164, 736, 288 | NAT 100% stacked area, direct labels, + (i) | `dim_date[year]`, `dim_album[release_decade_group]` **(request)**, `Album Share %` | Q5 |
| `p04_area_note` | 470, 164, 300, 24 | NAT card (italic `accent`) | `Annotation p04` **(request)** | Q5 |
| `p04_album_decade_matrix` | 40, 470, 500, 220 | NAT matrix heatmap, values as text | `dim_album[album_title]`, `dim_date[decade]`, `Album Share %` | Q5 |
| `p04_matrix_note` | 560, 500, 216, 96 | NAT card (text measure) | `Annotation p04b` **(request)** | Q5 |
| `p04_photo_card` | 808, 0, 472, 272 | **HTML**: base64 photo (480 px) + scrim gradient in CSS + big number + caption — fallback IMG + IMG scrim + NAT card | `photo_zoo_tv_1992_kiel.jpg`; `Promoted Album Share %` (Zoo TV or the selected tour), `Promoted Callout Text` **(request)** | Q4 |
| `p04_promoted_share_table` | 808, 292, 448, 404 | NAT table: `Tour Icon` (**SVG**) · tour · data bar · % ; selected tour `accent`, anniversary tours "ⓐ" + lighter bar | `Tour Icon` **(request)**, `dim_tour[tour_name_display]`, `Promoted Album Share %` | Q4 |

### Page 5 · Setlist evolution (`p05_setlist_evolution`) — Q6, Q8

Anchor: the song × year heatmap (large), with the Elevation heart-stage photo as a small tile beside it.

| Element | x, y, w, h | Tag | Fields | Q |
| --- | --- | --- | --- | --- |
| `p05_headline` + `p05_first_glimpse` (explains how to read the heatmap) | 40, 60, 760, 96 | NAT card + HTML | `Headline p05`, `First Glimpse p05` **(requests)** | Q6 |
| `p05_song_year_heatmap` | 24, 160, 776, 536 | NAT matrix heatmap (cells only, 13 px rows, 9 px year columns), Top N 30 visible, scroll for 40; #1 song label `accent` | `dim_song[song_title]` (Top N 40), `dim_date[year]`, `Performances` | Q6, Q5 |
| Photo tile + scrim | 832, 0, 448, 176 | IMG + IMG scrim | `photo_elevation_2001_philadelphia.jpg` | — |
| `p05_variety_table` | 832, 184, 424, 200 | NAT table: `Tour Icon` (**SVG**) · tour · data bar; Sphere `accent` | `Tour Icon`, `dim_tour[tour_name_display]`, `Setlist Variety` | Q6 |
| `p05_songs_per_show_line` | 832, 400, 424, 128 | NAT line + explanation | `dim_date[year]`, `Avg Songs per Show` | Q8 |
| `p05_openers_closers` | 832, 544, 424, 152 | NAT bar with field parameter toggle "Openers / Closers / Encores" | `Opener Count`, `Closer Count`, `Encore Count` **(requests)** | Q8 |

### Page 6 · Sphere vs. touring (`p06_sphere_vs_touring`) — Q10

```
┌ SPHERE PHOTO, full height ─────┐ [tabs]
│                         ░scrim│ AT THE SPHERE, ONE ALBUM CARRIED THE NIGHT (DIN)
│                         ░░░░░ │ Forty nights in one room … compared with the four 2015–2019 tours ▾ (HTML)
│                         ░░░░░ │ HEAD-TO-HEAD (HTML)      ◎ Residency   ◯ Touring 2015–19   Difference
│░░░░░░░ bottom scrim ░░░░░░░░░ │ Songs a night            ████ 22       █████ 24            −2
│ ◎ RESIDENCY · SPHERE · 2023–24│ Different songs          ██ 49         █████ 112           −63
│ 40 shows  22 songs  78% AB    │ Achtung Baby share       ██████ 78%    █ 12%               +66 pp ↗ note
└───────────────────────────────┘ Every show, one dot (i)  [Songs per show | Rarities | AB songs]  ← choose-your-measure
                                   ■ Sphere squares vs ● touring circles
```

| Element | x, y, w, h | Tag | Fields | Q |
| --- | --- | --- | --- | --- |
| Sphere photo + scrims | 0, 0, 520, 720 · right 360, 0, 160, 720 · bottom 0, 400, 520, 320 | IMG + IMG | `photo_sphere_2023_las_vegas.jpg` | — |
| `p06_residency_callouts` | 32, 572, 470, 120 | NAT card (new), 3 values DIN `accent` + `glyph_sphere.svg` | `Shows`, `Avg Songs per Show`, `Album Share %` (Achtung Baby) with `show_type` = Residency **(request)** | Q10 |
| `p06_nav`, `p06_headline` | 560, 12 · 560, 60, 680, 44 | NAT | `Headline p06` **(request)** | Q10 |
| `p06_first_glimpse` | 560, 104, 680, 48 | HTML; the "▾" is a NAT dropdown slicer styled as text beside it (compare set, default the four 2015–2019 tours) | `First Glimpse p06` **(request)**, `dim_tour[tour_name_display]` | Q10 |
| `p06_head_to_head` | 560, 164, 696, 212 | **HTML**: 3 rows × (residency bar + value, touring bar + value, difference as big number); icons inline (glyph SVG, badge base64) — fallback NAT matrix with data bars | `Avg Songs per Show`, `Distinct Songs`, `Album Share %` by `show_type`, `Difference … (pp)` **(requests)** | Q10 |
| `p06_note` + arrow | 1000, 392, 256, 24 · arrow 1196, 340 | NAT card italic + IMG | `Annotation p06` **(request)** | Q10 |
| `p06_every_show_scatter` | 560, 420, 696, 272 | NAT scatter, **choose-your-measure** field parameter (songs per show / rarities per show / Achtung Baby songs per show); Residency `accent` squares, Touring `neutral` circles; (i) | `dim_date[date]`, field parameter, `dim_tour[show_type]` | Q10, Q8 |

### Page 7 · Song detail (drill-through on `dim_song[song_title]`) (`p07_song_detail`) — Q3

| Element | x, y, w, h | Tag | Fields | Q |
| --- | --- | --- | --- | --- |
| Photo + scrim | 760, 0, 520, 320 | IMG + IMG | `photo_popmart_1997_reggio_emilia.jpg` | — |
| `p07_song_card` | 40, 60, 680, 200 | **HTML**: song title (DIN), album and year, 4 KPI tiles (performances, live debut, last played, years since) with deltas vs. the album's average | `Song Card HTML` **(request)** built from `Selected Song`, `Performances`, `dim_song[live_debut_date]`, `[last_played_date]`, `Years Since Last Played` | Q3 |
| `p07_plays_per_year` | 40, 280, 1216, 184 | **DEN** (same spec as p01, filtered to the song; debut year `accent`) — fallback NAT column | `dim_date[year]`, `Performances`, tour glyph paths | Q3 |
| `p07_tours_table` | 40, 480, 760, 216 | NAT table: `Tour Icon` (**SVG**) · tour · times played · share of tour shows | `Tour Icon`, `dim_tour[tour_name_display]`, `Performances`, `Share of Tour Shows %` **(request)** | Q3 |
| `p07_position_bar` | 832, 480, 424, 216 | NAT 100% stacked bar (opener / main / encore / closer) + explanation | `Opener Count`, `Closer Count`, `Encore Share %` **(requests)** | Q8, Q3 |

### Page 8 · Show detail (drill-through on `dim_show[show_label]`) (`p08_show_detail`) — Q8, Q9

```
 [tabs]  ← back                                                     ┌ War Tour photo, B/W ┐
 ┌ TICKET STUB (HTML) ──────────┬╌╌ SETLIST (HTML, in order) ╌╌╌╌╌╌╌╌╌╌╌╌╌╌┐                     │
 │ ⚑  WAR TOUR                  ╎ MAIN SET  1 Out of Control  …  7 Seconds ★ debut          │
 │ 14 AUG 1983 (DIN)            ╎ ENCORE 1  …     ENCORE 2  … Send in the Clowns  cover     │
 │ Phoenix Park, Dublin         ╎                                 … with guest            │
 │ show 284 of 1,875 · setlist.fm↗╎                                                         │
 └──────────────────────────────┴───────────────────────────────────────┘                     │
 17 songs (tour avg 16.4)   1 live debut ★   2 covers   "a home-town show…"                      │
```

| Element | x, y, w, h | Tag | Fields | Q |
| --- | --- | --- | --- | --- |
| Photo + scrim | 880, 0, 400, 720 | IMG (black-and-white photo) + IMG scrim | `photo_war_1983_dublin.jpg` | — |
| `p08_ticket` | 40, 84, 840, 520 | **HTML** ticket stub: tour glyph (inline SVG), tour, date (DIN), venue, city, country, show number, song and encore counts; perforated edge; setlist in order in two columns with set headings and text markers "★ debut", "cover", "with <guest>", "snippet" | `Ticket HTML` **(request)**: `CONCATENATEX` over `fact_performance` ordered by `setlist_position`, with `set_name`, `song_title`, `is_live_debut`, `is_cover`, `guest_artist`, `is_snippet`; header from `dim_show`, `dim_tour`, `dim_venue` | Q8, Q9 |
| `p08_setlist_link` | inside the stub | NAT button (web URL `dim_show[setlist_url]`) placed over the stub's link | `dim_show[setlist_url]` | — |
| `p08_vs_tour_callouts` | 40, 624, 840, 64 | NAT card (new) + italic note | `Performances` vs `Tour Avg Songs per Show`, `Live Debuts`, `Covers Played`, `Annotation p08` **(requests)** | Q8 |

Fallback without HTML Content: NAT card (header) + NAT table (setlist) in the same frame.

### Page 9 · About the data (`p09_about`)

| Element | x, y, w, h | Tag | Content |
| --- | --- | --- | --- |
| Photo mosaic | 0, 0, 1280, 200 | 8 IMG tiles (160 × 200, one per era; era 1 = glyph tile) + IMG scrims (top 0–72 for the tabs, bottom 80–200 for the headline) | all era photos |
| `p09_nav`, `p09_headline` | 40, 12 · 40, 136, 900, 44 | NAT | "About the data, and the photos" |
| `p09_sources` | 40, 224, 560, 160 | NAT text box | setlist.fm (non-commercial API terms), MusicBrainz (CC0), pipeline in one paragraph |
| `p09_limitations` | 40, 400, 560, 200 | NAT card (new) + (i) + text | `Shows` − `Shows with Setlist`, `Unmapped Song Share %` **(request)**, `Last Refresh Date`; sentence on early shows and snippets |
| `p09_credits` | 632, 224, 624, 400 | NAT text box in 2 columns from `credits.csv` (title, author, licence, link ↗; closing line on crops and original glyphs) | — |
| `p09_icon_strip` | 632, 640, 624, 48 | IMG `timeline_tours.svg` | all tour icons |

### Page 10 · Next tour (`p10_next_tour`) — Q12 (T-51, SPEC-09 §9.8)

Anchor: the predicted setlist as a ticket (same language as the p08 stub). Left: story column (656 px); right: data
column (528 px). Built straight in `scripts/gen_report.py`; Vini reviews the rendered page in T-52.

```
 [Overview|Road|Songs|Albums|Setlists|Sphere|2027|About]         ALL 25 NEW SONGS, BY RELEASE: 8 MAKE THE SETLIST
 OUR GUESS FOR 2027: 24 SONGS A NIGHT, 8 OF THEM NEW (DIN)       Release · Song · Chance ▬▬ · ✓ picked   (scrolls)
 Before the first show, our model picks 6 … 61% vs 48% (HTML)    "Toss-ups: 2 of the 7 album songs tied at 38% …"
 ┌ ⛺ THE GREATEST SHOW ON EARTH TOUR   24   8 new   16 older ┐  +12.7 pp  HOW GOOD IS THIS? replayed since Zoo TV …
 │ MAIN SET  1 Street of Dreams NEW·ALBUM ▬ 86% │ 13 In a Life │  model ███████ 61%  B1 █████ 48%  B3 …  B2 …
 │ …                                           │ ENCORE 23 One│  "On the e+i tour … the model only tied B1: 50% vs 50%"
 │ order is approximate · chances not rescaled · top 24     │  ONCE THE TOUR STARTS (empty-state text)
 └──────────────────────────────────────────────────────────┘  [predicted vs played]  [how the chances move]
```

| Element | x, y, w, h | Tag | Fields | Q |
| --- | --- | --- | --- | --- |
| `p10_nav` | 40, 6, 696, 44 | NAT page navigator | page 10 appears as "2027", before About (T-52: 8 tabs, 9 pt, no cell padding; p07/p08 navs widened to 656; p10 nav 696 because 656 cut "Overview" with a selected tab, right column moved to x 736) | — |
| `p10_headline` | 40, 54, 656, 144 | HTML | `Headline p10`, `First Glimpse p10` (report measures from `Expected Songs per Show`, `New Songs Predicted`, `Catalog Songs Predicted`, `Model/Baseline Precision at N`; **request** to promote to the model) | Q12 |
| `p10_setlist_ticket` | 40, 208, 656, 480 | HTML (anchor) | `Ticket p10`: `fact_setlist_prediction` rows of the latest as-of date with `predicted_in_setlist`, in `predicted_position` order, set header when `predicted_set` changes; per song position, title, NEW · ALBUM/EP tag (`model_part`, `dim_song[release_role_2027]`), chance bar and % (`probability`); band with glyph, tour, as-of date, `Expected Songs per Show`, `New Songs Predicted` (album/EP split), `Catalog Songs Predicted`; footnote: order approximate, chances not rescaled, list = top N | Q12 |
| `p10_new_songs_table` | 736, 16, 520, 216 | NAT table, all 25 rows (vertical scroll on purpose; columns 104/196/92/58 px, no horizontal scroll), data bars, picked songs in `accent` + "✓ picked" | `Release p10`, `dim_song[song_title]`, `Predicted Probability`, `In Setlist p10`; filter `release_role_2027` in (promoted_album, companion_release) | Q12 |
| `p10_ties_note` | 736, 236, 520, 36 | HTML italic `accent` | `Ties Note p10` (tied scores among the last new-song slots, from the data) | Q12 |
| `p10_backtest_intro` | 736, 280, 520, 56 | HTML | `Model vs. Baseline` as the big number, `Selected Baseline` named as the best simple rule | Q12 |
| `p10_backtest_bars` | 736, 340, 520, 112 | HTML labelled bars (T-52: the native bar chart rendered only its placeholder at 92 px) | `Backtest Bars p10`: `Mean Precision at N` per `fact_setlist_backtest[method]` (Model in `accent`; B1 repeat the last album tour, B2 career's most played, B3 latest tour in `neutral`), value labels | Q12 |
| `p10_analog_note` | 736, 456, 520, 36 | HTML italic `accent` | `Closest Analog Note p10` (e+i: model vs B1) | Q12 |
| `p10_tracker_intro` | 736, 500, 520, 44 | HTML | `Tracker Intro p10`: empty-state text until the first show, then shows played and `Hit Rate` | Q12 |
| `p10_hit_rate_line` | 736, 548, 252, 140 | NAT line | `dim_date[date]`, `Hit Rate` (empty before the first show) | Q12 |
| `p10_chance_line` | 1004, 548, 252, 140 | NAT line, legend new/catalog | `dim_date[date]`, `Predicted Probability`, series `model_part`; filters `predicted_in_setlist` = true, `Tour Started p10` > 0 | Q12 |

Interactions: the prediction and the backtest are separate stories, so visuals do **not** filter each other on this
page (clicking a backtest tour or a song would empty the ticket); the one exception is new-songs table → chance chart
(click a new song to follow its chance over the tour). The planned tour has no glyph in the model's `Tour Icon`;
the ticket inlines the original `glyph_greatest_show_2027.svg` (big top tent, `credits.csv`).

## 5. Traceability Q1–Q10, Q12

| Q | Question (short) | Visuals |
| --- | --- | --- |
| Q1 | Shows, songs, countries, cities; activity by year and decade | `p01_first_glimpse`, `p01_kpi_tiles`, `p01_shows_per_year`, `p01_busiest_note`, `p01_era_badges`, `p02_continent_decade` |
| Q2 | Most played songs and rarities | `p01_top_songs`, `p03_top_song_callout`, `p03_song_ranking_table`, `p03_explore_scatter`, `p03_rarities` |
| Q3 | Debut, last played, retired songs | `p03_song_ranking_table`, `p03_explore_scatter`, `p07_song_card`, `p07_plays_per_year`, `p07_tours_table` |
| Q4 | Promoted album vs. older material per tour | `p04_photo_card`, `p04_promoted_share_table` |
| Q5 | Album share in setlists over the decades | `p04_album_share_area`, `p04_album_decade_matrix`, `p05_song_year_heatmap`, `p06_head_to_head` |
| Q6 | Setlist stability/variety within a tour | `p05_variety_table`, `p05_song_year_heatmap` |
| Q7 | Countries, continents, cities, venues, first/last visits | `p02_venues_map`, `p02_cities_table`, `p02_continent_decade`, crowd photo card, `p01_kpi_tiles` |
| Q8 | Show length and structure (openers, encores, closers) | `p05_songs_per_show_line`, `p05_openers_closers`, `p07_position_bar`, `p08_ticket`, `p08_vs_tour_callouts`, `p06_every_show_scatter` |
| Q9 | Covers and guest appearances | `p03_covers_guests`, `p08_ticket` |
| Q10 | Sphere residency vs. touring | `p06_residency_callouts`, `p06_head_to_head`, `p06_every_show_scatter`, `p05_variety_table` (Sphere row) |
| Q12 | 2027 setlist prediction, trilogy share, how close it was | `p10_headline`, `p10_setlist_ticket`, `p10_new_songs_table`, `p10_ties_note`, `p10_backtest_intro`, `p10_backtest_bars`, `p10_analog_note`, `p10_hit_rate_line`, `p10_chance_line` |

## 6. Colour, type and contrast

| Token | Hex | Use |
| --- | --- | --- |
| `bg` | `#0F1115` | page; visuals sit directly on it; scrim colour |
| `surface` | `#181B21` | small pills behind text on busy photos |
| `surface-2` | `#20242C` | tooltips, filter pane, ticket stub (HTML) |
| `border` | `#2A2F38` | hairlines, inactive tab underline |
| `text` | `#ECEDEF` | headlines, numbers, labels |
| `text-muted` | `#A3A9B3` | paragraphs, axis labels |
| `accent` | `#F2A93B` | hero number, outlier/selected mark, annotations, arrows, current tab |
| `neutral` | `#6E7581` | non-highlighted marks, touring side of comparisons |
| `data-1..6` | `#6FA8DC #93C47D #E06666 #B4A7D6 #76D7C4 #F6B26B` | categorical, max 6; `data-2` green = up delta, `data-3` red = down delta (always with ▲/▼ and a sign) |
| `seq-low → seq-high` | `#1E2A3A → #6FA8DC` | heatmaps |

Type: headline DIN 34 · callout numbers DIN 40–56 · KPI tile numbers DIN 52 · paragraphs Segoe UI 12.5 ·
visual titles Segoe UI Semibold 13 · labels 10 · kickers 11 uppercase letter-spaced · annotations Segoe UI Semibold
italic 14 `accent` · footer 9.

Contrast (WCAG 2.x; worst case for photos = text over a pure white pixel):

| Pair | Ratio | Need | Result |
| --- | --- | --- | --- |
| `text` / `text-muted` / `accent` on `bg` | 16.13 / 7.99 / 9.46 | 4.5 | pass |
| same on `surface-2` (ticket) | 13.28 / 6.58 / 7.79 | 4.5 | pass |
| on a scrim where it is 92% opaque (first 45% of its length), worst case | 13.27 / 6.58 / 7.78 | 4.5 | pass |
| on a scrim where it is ≥ 85% opaque (up to ~54% of its length), worst case | ≥ 10.50 / 5.20 / 6.16 | 4.5 | pass |
| `data-2` / `data-3` delta text on `bg` | 9.39 / 5.63 | 4.5 | pass |
| `data-1..6` marks on `bg` | 7.48 · 9.39 · 5.63 · 8.49 · 11.06 · 10.35 | 3.0 | pass |
| `neutral` marks on `bg` | 4.07 | 3.0 | pass |
| `data-1` marks on the 92% scrim (p01 top songs) | 6.15 | 3.0 | pass |

Rules: text and data on a photo only where its scrim is ≥ 85% opaque; photos stay vivid elsewhere. Colour is never the
only cue (deltas carry ▲/▼ and a sign, Sphere vs. touring differ in marker shape, anniversary tours carry "ⓐ").
HTML blocks use the same tokens in inline CSS; their text is checked with the same table.

## 7. Requests

To the **data-analyst** (measures/columns; texts in T-35):

| Name | Kind | Intent | Used on |
| --- | --- | --- | --- |
| `Headline p01` … `Headline p08` | text measures | finding-style headline per page | all |
| `First Glimpse p01` … `p06` | HTML measures | 2–3 sentences, key numbers wrapped in `<b>`, filters in effect at the end | p01–p06 |
| `KPI Tiles p01` | HTML measure | 3 tiles: inline SVG icon, number (`Shows`, `Distinct Songs`, `Countries`), delta vs previous era | p01 |
| `Shows vs Previous Era`, `Distinct Songs vs Previous Era`, `Countries vs Previous Era` | measures | difference to the previous era in `era_order` (blank when all eras) | p01 |
| `Busiest Year Text`, `Top City Text`, `Top Song Text`, `Promoted Callout Text`, `Annotation p04`, `p04b`, `p06`, `p08` | text measures | short annotation sentences, numbers from measures | p01–p08 |
| `Tour Icon SVG`, `Tour Icon`, `Tour Icon Path` | measures | glyph markup per tour (SWITCH on `tour_name`, markup from `docs/design/images/glyph_*.svg`); `Tour Icon` = SVG data URI (data category Image URL); `Tour Icon Path` = path data for Deneb | p01, p04, p05, p07, p08 |
| `Head to Head p06` | HTML measure | the 3-row comparison block | p06 |
| `Difference Songs per Show`, `Difference Distinct Songs`, `Difference Achtung Baby Share (pp)` | measures | residency − touring | p06 |
| `Song Card HTML`, `Ticket HTML` | HTML measures | song drill-through card; show ticket stub with the setlist in order | p07, p08 |
| `Image Data URI` | measure | `data:image/jpeg;base64,` + chunks of the selected image (see §2) | p02, p04, p06 |
| `Years Active`, `Last Refresh Date`, `Filter Context Text`, `Is Busiest Year`, `Era Band Color`, `Is Retired`, `Opener Count`, `Closer Count`, `Encore Count`, `Encore Share %`, `Share of Tour Shows %`, `Tour Avg Songs per Show`, `Unmapped Song Share %`, `Selected Song` | measures | as in revision 1 (unchanged intent) | various |
| `dim_tour[era_order]`, `dim_tour[show_type]`, `dim_album[release_decade_group]` | columns | era sort; "Residency"/"Touring"; album release decade group incl. "Not on a studio album" | various |
| Field parameters `p03 X axis`, `p03 Y axis`, `p05 Setlist position`, `p06 Every show measure` | field parameters | choose-your-axis / measure | p03, p05, p06 |

To the **data-engineer + data-analyst** (Gold contract, needs SPEC-04/05 update): table `report_image_chunk`
(`image_id`, `chunk_no`, `chunk` varchar(8000)) with ≤ 10 small report photos (480 px, ≤ 35 KB each), loaded from
`docs/design/images/` (designer supplies the files and `image_id` list in T-32).

To **Vini** (T-31): add HTML Content **Secure** and **Deneb** from AppSource in Desktop; T-32 starts with the spike in §2.

To the **data-analyst** (T-51, page 10):

| Name | Kind | Intent | Used on |
| --- | --- | --- | --- |
| `Headline p10`, `First Glimpse p10` | text measures | promote the report-level versions (same wording) to the model, folder Text | p10 |
| `Tour Icon SVG` / `Tour Icon` for The Greatest Show on Earth Tour | measure change | add `glyph_greatest_show_2027.svg` (and a row in `glyph_paths.csv` via `scripts/gen_glyph_paths.py`) so tour tables show the planned tour | p10, tour tables |
| `dim_song` release of *Get Back to Now* | data | it has no `album_key` (Unknown); the report shows "Carnaval de luz (bonus)" from the tour's promoted album. A Gold fix (release from `release_track`) would remove the workaround | p10 |
| `method_label` on `fact_setlist_backtest` (or a small method dimension) | column | optional since T-52: the HTML bars carry their own labels | p10 |

## 8. As built (T-32..T-34, 2026-10-21)

Generated by `scripts/gen_report.py` (re-run, then `fab import`). Differences from §4, to revisit after T-36:

- p01 era badges are decorative images; the era filter is a dropdown slicer under them. Bookmark buttons (badge → era + hero photo) are not built yet: easier to wire in Desktop.
- p03 scatter has fixed axes (year first released × times played); the `p03 X/Y axis` field parameters are not used yet.
- p05 openers/closers/encores and p06 "every show" use the model field parameters (`fieldParameters` in the query role); p06 x-axis is a report measure `Show Year Decimal`.
- p07 "where in the night" is a bar of three report measures (opener / encore / closer share); p08 setlist.fm link is a one-cell table with a URL icon.
- Headline, first-glimpse and annotation cards are bound to report-level placeholders `ph <name>` (T-35 replaces them with model measures of the same name, minus `ph `).
- Text cards are HTML Content Secure visuals over wrapper measures `<name> · html` (classic cards could not wrap left-aligned DIN headlines).
- Deneb tour icons use `docs/design/images/glyph_paths.csv` (`path_unit`, inlined in the spec).

## 9. Changes from T-36 round 1 (2026-10-22)

Layout per page now follows `scripts/gen_report.py`; the main differences from §4/§8: p04 album share is a 100% stacked
column chart (not area); p05 heatmap is songs × decade (not × year) and shows openers only (closers are on p07); p06
"every show" shows songs per show for the 2015–2019 and Sphere eras (no measure picker); p07/p08 are hidden drill-through
pages with a Back button and a prompt when nothing is selected; p09 has no icon strip. Details and status per item:
`docs/design/review-t36.md`.

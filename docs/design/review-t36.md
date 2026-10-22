# T-36 review: first render of rpt_u2_live

Source: screenshots Vini took in the Power BI service on 2026-10-22 (pages 1–9, full screen).
Vini's verdict: "a great first version, but lots of adjustment work: small charts, overlapping text, visuals that look odd".

Screenshots (scratchpad, readable with the Read tool):
`C:\Users\vicoc\AppData\Local\Temp\claude\C--Users-vicoc-Desktop-u2-live-analytics-u2-live-analytics\a36bb43d-1a89-4ddc-9516-07250d5cd180\images\`
`4.png` p1 · `5.png` p2 · `6.png` p3 · `7.png` p4 · `8.png` p5 · `9.webp` p6 · `10.png` p7 · `11.webp` p8 · `12.webp` p9

## Every page

1. **Headlines are cut off.** They sit on one line in a box that is too short and too narrow, so the end of the sentence is
   missing (p1 "…and I Will", p4, p5, p6) and the bottom of the letters is clipped (p2, p3). Let headlines wrap to two
   lines, give them enough height, or shorten the text measures (with the data-analyst).
2. **Intro paragraphs are clipped** at the second line (p2, p3, p4, p5, p6).
3. **Stray scrollbars.** Small grey bars appear next to the HTML Content blocks (headline, intro, footer, annotations),
   meaning their content overflows. Size the boxes to the content or hide overflow.
4. **The navigation tabs are truncated** ("Ov…", "On…", "Th…"). Use shorter labels or wider buttons, so every page name is
   readable.
5. **Number format depends on the viewer's locale.** The p1 headline shows "1.874" while the tiles show "1,874", and p6
   shows the year axis as "2,014". Format the numbers inside text measures with an explicit culture
   (`FORMAT(x, "#,0", "en-US")`), and use whole-number years with no thousands separator on axes.
6. **Too many visuals scroll inside small boxes** (tables and matrices with both scrollbars). Fewer, larger visuals per
   page; show the top N rows that fit, and leave the full list to drill-through.

## Per page

**p1 Overview**
- The headline says I Will Follow was played "at 1,004 of them" (shows), while the bar says 1,065 (performances). Either
  use the same measure or write the difference out.
- The large empty band between the intro and the KPI tiles wastes space.
- The "Pick an era" label is clipped. The first era badge is the camera placeholder (no photo).
- The shows-per-year chart: the stacked grey layers look odd. The tour icons under the axis sit on two overlapping rows,
  and one is cut off at the bottom. The "1981: 152 shows" annotation is clipped, and the explanatory text box overlaps
  the chart's right side.
- Top-10 song names are truncated ("Pride (In the Name of Lo…").

**p2 On the road**
- On the map, the Europe and US bubbles merge into one blob. Use a smaller max bubble size and some transparency.
- The photo at the top right is too dark to read as a photo.
- The decade chart is fine; there is a stray "▽" artifact under the legend.

**p3 The songs**
- "Every song" table: the album column is cut and there is a horizontal scroll.
- The scatter has no axis titles. Its x-axis runs to 2030.
- The Rarities table cuts the "Last" column.
- **"Other people's songs" shows only Miss Sarajevo**, which is an original (Passengers). The filter is wrong, and the
  box is one row tall.
- "Guests on stage" is one row tall.

**p4 Albums on stage**
- **The 100% area chart looks broken.** Smoothed curves swoop to zero in years with no shows (around 1999 and 2008).
  Use a 100% stacked column by year (or a stepped area) with no smoothing, and leave gaps for years without shows.
- The "Which albums stay" matrix is cut (the 2020s column) and scrolls; the heatmap colours are faint.
- The 41% photo card text is cut ("…the album it").
- In the tour bar table, the column header is cut ("From the new") and the bars have no values.

**p5 Setlist evolution**
- **The heatmap scrolls horizontally and only shows up to 1993.** Fit all years (narrow columns), or group by era/tour.
- The photo caption is clipped; the photo is very dark.
- "Setlist variety per tour" shows 4 rows, and the "Variety" metric (1.2) is unexplained.
- "Songs per show, by year": a smoothed line with no axes. The "All" dropdown overlaps it.
- "How the night starts and ends" is tiny, with 2 rows visible.

**p6 Sphere vs. touring**
- An "All" slicer dropdown overlaps the intro text, and another one overlaps the "+40 points" annotation.
- **"Every show, one dot" is empty.** It has no dots, and the legend shows False/True instead of Residency/Touring
  (use `dim_tour[show_type]`).
- The "Touring" icon is an odd round image; use the tour glyph style.
- The residency/touring comparison block works well: keep it.

**p7 Song detail (drill-through)**
- Opened without a song, it shows every song combined ("FROM NO STUDIO ALBUM ()", 29,366 performances, "0 years since").
  Show a prompt instead ("Right-click a song on page 3 to see its story") when no single song is in context.
- The large empty band under the KPIs; the photo overlaps the chart area; the tour icons are cut at the bottom.
- "Where in the night it is played": the bars have no labels or legend.

**p8 Show detail (drill-through)**
- The same problem with no show selected: "1 JAN 1976", all setlists merged, "29366 songs", and "," as the venue line.
  Show a prompt when no single show is in context.
- The numbers have no thousands separator ("29366", "1316").
- The ticket-stub design itself works well.

**p9 About**
- The navigation tabs sit on the photo mosaic and are hard to read; the big camera badge overlaps the headline area.
- "0.0% performances not matched": show "< 0.1%" or one more decimal place.
- The tour icon strip at the bottom (icons on vertical lines) looks unfinished.

## Status after round 1 fixes (dashboard-designer, 2026-10-22)

Fixed in `scripts/gen_report.py`, pushed with `fab import` and re-exported to `fabric/`. Checked by exporting every
page to PDF through the Power BI API (p07 with song "Bad", p08 with show "1992-03-17 · Boston · Boston Garden") and
looking at the rendered pages. **Needs Vini** = check in the service or Desktop, the PDF cannot show it.

| # | Item | Status |
| --- | --- | --- |
| E1 | Headlines cut off | **Fixed**: two-line headline box (84 px, DIN 32 px); text clipped at a line, never a scrollbar. Headlines longer than two lines need shortening (analyst, below) |
| E2 | Intro paragraphs clipped | **Fixed**: 68 px box (three lines) |
| E3 | Stray scrollbars | **Fixed**: every HTML block is wrapped in a fixed-height, overflow-hidden div; text boxes have no padding; footers one line. **Needs Vini** to confirm in the service |
| E4 | Navigation tabs truncated | **Fixed**: short page names (Overview, Road, Songs, Albums, Setlists, Sphere, About), 9 pt, no margins; the two drill-through pages (Song, Show) are now hidden from the bar, as drill-through pages usually are, and have a Back button. **Needs Vini** to confirm the labels are whole in the service |
| E5 | Locale-dependent numbers | **Fixed** in all report measures (`FORMAT(..., "en-US")`) and on the p06 year axis. Model text measures: analyst (below) |
| E6 | Small scrolling tables | **Fixed**: tables show a Top N that fits (p02 8 cities, p03 15 songs / 10 rarities / 4 covers / 3 guests, p04 8 albums / 13 tours, p05 22 songs / 6 tours) with fixed column widths; the full lists stay in drill-through |
| p1 | 1,004 vs 1,065 | **Analyst** (below) |
| p1 | Empty band, era label, first badge | **Fixed**: KPI tiles moved up; label unclipped; 1976–80 badge is now a year badge instead of the amp glyph |
| p1 | Shows-per-year chart | **Fixed**: one bar per year (no stacked grey layers), era tones by year, busiest year labelled inside the chart, icons on two rows that fit; the explanation sits above the chart |
| p1 | Top-10 names truncated | **Fixed** (wider category margin) |
| p2 | Map blob | **Improved**: smaller bubbles (radius 2–14 px) with outlines. Power BI's bubble layer has no transparency setting for this visual, so dense Europe/US areas still touch. **Needs Vini** |
| p2 | Dark photo | Kept: the photo itself is a dark arena shot; the gradient was reduced to the lower half. Swap the photo if still too dark |
| p2 | "▽" artifact | **Fixed**: legend at 9 pt fits without paging |
| p3 | Song table cut, scatter axes, rarities, covers, guests | **Fixed**: column widths, axis titles, x-axis 1976–2027, covers filtered on `dim_song[is_original] = false` (no longer Miss Sarajevo), taller boxes |
| p4 | Area chart broken | **Fixed**: 100% stacked **columns** by year on a continuous axis, so years without shows are gaps, no smoothing |
| p4 | Matrix cut and faint | **Fixed**: 8 albums, no subtotal row, brighter cells that keep white text readable (≥ 4.5:1) |
| p4 | 41% card text, tour table header and values | **Fixed** (explicit card height, header "New album", values on the bars) |
| p5 | Heatmap scroll | **Fixed**: songs × decade (6 columns) instead of × year; values shown in the cells |
| p5 | Caption, variety, line, openers | **Fixed**: caption on one line, subtitle explains variety, straight line with axes, slicer removed, openers chart taller. Closers moved to p07 (where in the night) |
| p6 | Slicers over text | **Fixed**: one compare slicer with a label, on its own row |
| p6 | Empty dot chart | **Fixed**: the x value now goes through `fact_show` (it took the date of the whole calendar before), legend uses `dim_tour[show_type]` |
| p6 | Touring icon | **Fixed**: tour glyph instead of the round photo |
| p7 | No song selected | **Fixed**: the song card shows "Nothing selected yet" with how to drill through; chart and table still show all songs until a song is chosen. With a song: album now comes through the song (was "not on a studio album" for Bad), the tour table lists only tours where it was played |
| p7 | Band, photo overlap, icons cut, position bars | **Fixed**: chart moved up and narrowed beside a smaller photo; "where in the night" is now labelled bars (opener, encore, closer) |
| p8 | No show selected; date, venue, thousands separator | **Fixed**: prompt when no single show; date, venue and tour now come through the show's fact row; numbers formatted "#,0" |
| p9 | Tabs on the mosaic, camera badge, 0.0%, icon strip | **Fixed**: mosaic moved below the tabs, a "1976–80 the club years" tile, "< 0.1%" for tiny shares, icon strip removed |

## For the data-analyst

1. **Headline length.** Headlines get two lines of 32 px DIN in ~580–740 px. Keep them under ~65 characters
   (p04 and p05 today run to the second line's end; p06 fits).
2. **Locale-safe FORMAT** in every model text measure (`Headline pNN`, `First Glimpse pNN`, `Annotation pNN`,
   `Top Song Text`, `Busiest Year Text`): add the culture, e.g. `FORMAT ( [Shows], "#,0", "en-US" )`. The p01 headline
   showed "1.874" in Vini's locale.
3. **1,004 vs 1,065 (p01 headline).** The headline counts shows where I Will Follow was played (1,004) while the top-10
   bar counts performances (1,065, some shows had it twice). Either say "played 1,065 times" or write "at 1,004 shows".
4. **"Other people's songs" (p03).** The report now filters `dim_song[is_original] = false`. Please check that
   `is_original` is right for Passengers songs (Miss Sarajevo is an original, it showed as a cover) and that
   `Covers Played` uses the same rule.
5. **No song / no show selected (p07/p08).** The report shows its own prompt; the model measures `Selected Song` and
   `Tour Icon SVG` return blanks then, which is fine. Optional: give `Years Since Last Played` a blank when more than
   one song is in context (it showed "0").
6. **Unmapped share (p09).** Displayed as "< 0.1%" when below 0.1%; no change needed unless you prefer two decimals.

## What works (keep)

The dark theme, the photo cards with big numbers (p3 "I Will Follow · 1,065 times", p4 "41%", p6 left panel), the KPI
tiles on p1, the residency vs. touring block on p6, the ticket stub on p8, and the credits layout on p9.

## Round 2 (Vini's screenshots after the designer's round-1 fixes, 2026-10-22)

Vini: "much better, but not 100%". Screenshots: `13.png` p1 · `14.png` p2 · `15.png` p3 · `16.png` p4 · `17.png` p5 ·
`18.webp` p6 · `19.png` p7 · `20.webp` p8 (show 2015-07-27 MSG) · `21.webp` p9 (same folder as round 1).

**Every page**
- Nav labels are clipped at the bottom (descenders cut: "Songs", "Sphere", "Song") and the active underline overlaps the
  text. "Overv…" / "Over…" is still truncated on most pages, and "Albu…" / "Sph…" on p3 and p6. Song and Show are still
  in the bar (round 1 said they were removed): either remove them or make it intentional.
- Tables still show vertical scrollbars, and some show horizontal ones (p2, p3, p5, p7). Size them to the rows they show,
  or hide the scrollbars.
- p2 and p3: there is a large empty gap between the headline and the intro paragraph.

**p1** The "152 in 1981" label overlaps the bars. "I Still Haven't Found What I'm L…" is truncated in the top 10. The "All"
era dropdown duplicates the era badges. Headline: still 1,004 vs 1,065 (analyst).

**p2** In the cities table the last row (Boston) is cut. The "Dublin · 150" card uses an Antwerp 2015 photo, which is
odd for a Dublin number: use a Dublin photo if a free one exists, or a neutral crowd caption.

**p3** The scatter is too flat (short height) and the dots pile up: give it more height and some transparency.
Rarities: horizontal scrollbar, and song names are truncated. "Other people's songs" shows 3 rows and "Guests on stage"
2: make them taller or merge them.

**p4** The "2017: 70%…" annotation floats above the chart, far from 2017. Matrix: show blank instead of "0.0%" (e.g.
October in the 1990s). In the tour table, the % labels sit on top of the bar ends and are hard to read.

**p5** The headline breaks as "21.7-/song nights": keep the number with its word. The intro still says "each column a
year", but the heatmap is now by decade (text measure, analyst). **"Songs per show, by year" is empty** (placeholder icon
only). In "The most fixed setlists" the labels overlap the bars. The openers list shows 4 rows with a scrollbar. The
heatmap colour scale barely separates 619 from 400: make it stronger.

**p6** The dot chart has no y-axis (songs per show): add one. Otherwise good.

**p7 (no song selected)** Only the card says "Nothing selected yet"; the bar chart ("1,327 in 2001", label overlapping)
and the tour table still show every song combined, and "Where in the night it is played" is empty. Make the whole page
an empty state when no single song is in context (hide or blank the visuals).

**p8 (show selected)** The ticket works. Issues:
- The setlist is grouped by set name, so the two parts of the main set merge (1–11 then 19–23, before "Inside screen"
  12–14). List the songs by position and print a set header each time the set changes.
- "live debuts ★" and "covers" show no number: show 0.
- The "On setlist.fm" link icon is tiny, and a stray scrollbar thumb sits next to "24".
- The left panel has a lot of empty space.

**p9** Good.

### Round 2 status (dashboard-designer, 2026-10-22)

Fixed in `scripts/gen_report.py`, pulled first, pushed with `fab import`, re-exported to `fabric/` (0 semantic
differences). Checked with Power BI PDF exports rendered to PNG; p08 with show 1992-03-17 Boston Garden.
**Needs Vini** = interaction or service-only behaviour the PDF cannot show.

| Item | Status |
| --- | --- |
| Nav labels clipped / truncated; Song and Show in the bar | **Fixed**: navigator 44 px high, 10 pt; Song and Show removed from the bar on purpose (drill-through only, reached by right-click, with a Back button). All 7 labels whole in the export. **Needs Vini** in the service |
| Table scrollbars | **Fixed** where the table is a Top N: heights sized to the rows (p02 8, p03 13/8/3/2, p05 20/5/3). p04 tour table and matrix show everything (20 tours, 15 albums) and fit. Tables now have a dark background so they no longer scroll sideways |
| Top N must say so (26.png) | **Fixed**: titles from report measures with the cut and the total, ignoring the visual's own Top N filter: "Most played: top 13 of 304 songs", "Rarities: the 8 most recent of 93", "Other people's songs: top 3 of 123 covers", "Guests on stage: top 2 of 64 guests", "Most-visited cities: top 8 of 384 cities", "Top openers: 3 of 122", "The 20 most played of 304 songs", "The ten songs played most, of 304". Full lists: song drill-through (p07) |
| p2/p3 gap between headline and intro | **Fixed**: headline and intro are one HTML block, the intro follows the headline directly |
| p1 peak label overlaps; bars merge (23.png) | **Fixed**: one series, one bar per year drawn with explicit start/end (≈30% gap), era tone by colour, bars from zero; peak label above its bar with head-room. Same chart on p07 |
| p1 top-10 truncation | **Fixed** (wider label margin) |
| p1 era badges a real filter, no duplicate dropdown | **Fixed (fallback design)**: a native button slicer on `dim_tour[era]`, single select, click again for all eras, laid transparently over the 8 badge images; selected tile gets an accent ring; the "All" dropdown is gone. The preferred variant (images inside the button slicer from data URIs) rendered blank tiles in the export, so the images are separate image visuals under the buttons. **Needs Vini**: click a badge, check the ring and that the page filters |
| p2 Dublin card with an Antwerp photo | **Fixed**: Croke Park, Dublin 1987 photo (Commons, Damian McDonagh, CC BY-SA 4.0) with the number on a scrim |
| p3 scatter flat | **Improved**: taller; Power BI's scatter has no transparency setting in PBIR (rejected by the schema), dots unchanged |
| p3 long song titles in the photo callout (27.png) | **Fixed**: 28 px on up to two lines; tested length fits "I Still Haven't Found What I'm Looking For · 684 times" in 480 px. **Needs Vini** on click |
| p3 grey blocks when a row is selected (27.png) | **Changed**: tables now have an opaque dark background and explicit dark row colours, so the selection dimming should stay dark. **Needs Vini** (selection cannot be exported) |
| p4 annotation far from 2017 | **Improved**: moved to the chart's title row above the 2010s; the text itself is the analyst's |
| p4 matrix: 0.0%, all 15 albums, release order, 1970s note | **Fixed** except order: all 15 studio albums, no Top N; cells: blank before the album's release decade, "0%" when not played, "< 0.1%" when tiny (report measure `Album Share Cell`, checked: October 1990s "< 0.1%", Pop 1980s blank, Pop 2010s 0.4%); one-line note under the matrix about Boy in the 1970s. **Release order needs the model** (analyst, below) |
| p4 tour table: all tours, album column, chronological | **Fixed**: all 20 tours with a promoted album, columns tour · album · share, sorted by tour (chronological once `tour_name_display` has its sort-by column, see below), all rows fit; bars darker so the % labels read |
| p5 empty "Songs per show, by year" | **Fixed** (the chart needs ≥ 116 px; it renders in the export) |
| p5 heatmap colour scale | **Fixed**: stronger scale (#141A22 → #3A78C0, white text stays readable) |
| p5 variety labels on bars, openers scroll | **Fixed** (darker bars, 3 openers that fit, title states the total) |
| p6 y-axis | **Fixed** (value axis with title) |
| p7 full empty state | **Fixed**: chart and tour table are filtered on a "one song selected" measure, so they are empty until a song is chosen; the Deneb tour icons stay (static row) |
| p8 setlist order, set headers on change | **Fixed**: songs listed by position; a set header is printed each time the set changes (so the main set's two parts show as two headers) |
| p8 live debuts / covers blank | **Fixed**: 0 shown; the counts moved into the stub's left panel with songs and tour average (fills the empty space) |
| p8 tiny link icon, stray scrollbar | **Fixed**: "Open on setlist.fm ↗" button with the show's URL. **Needs Vini** to click it |

### For the data-analyst (round 2)

7. **Sort-by columns are not applied** in the model: `dim_album[album_title]` should sort by `album_order` and
   `dim_tour[tour_name_display]` by `tour_order` (SPEC-05). The p04 matrix and tour table sort by these columns and still
   come out alphabetical.
8. **p5 headline** breaks "21.7-/song nights": use a non-breaking hyphen (U+2011) or rephrase ("31 songs, 21.7 a night").
9. **p5 intro** still says "each column a year": the heatmap is by decade.
10. **Count measures for Top N titles**: the report computes them as report measures today (covers `is_original = false`,
    distinct guests, distinct openers, tours with a promoted album, studio albums). Promote them to the model if you want
    them documented in the data dictionary.
11. **Era badge images**: if the badge images should live inside the button slicer (preferred design), the slicer needs
    image URLs it can load; data URIs from a report measure rendered blank. An option is `report_image` rows for the 8
    badges plus a model measure with data category Image URL, to be tried in Desktop.

### Round 3 status (dashboard-designer, 2026-10-22)

Pulled first, fixed in `scripts/gen_report.py`, pushed with `fab import`, re-exported to `fabric/` (0 semantic
differences). Checked with PDF exports (p02 also with a Dublin report filter) rendered to PNG. **Needs Vini** =
interaction or service-only behaviour.

| Item | Status |
| --- | --- |
| Top N not really top N; tables vs rankings policy | **Fixed** per the new policy (also in the `u2-design-system` skill): song, city, cover, guest, rarity and tour **tables show all rows**, sorted, scrollbar on purpose, titles with the total from a measure ("All 304 songs, most played first · right-click for the story", "All 384 cities, most shows first", "All 93 rarities…", "All 123 other people's songs…", "All 64 guests on stage…", "All 25 tours, most fixed setlist first"). **Ranking bar charts** (p01 top 10, p05 top openers) use a strict, tie-safe Top N: a rank measure with ties broken by name, visual filter rank ≤ N, no scroll. The rank ignores the decade/year columns, so a matrix row is in or out as a whole |
| p05 heatmap 21 rows | **Changed** as Vini asked: all songs, most played first, "All 304 songs by decade, most played first (scroll for more)" |
| p04 matrix lists every release | **Fixed**: rows `dim_album[album_label]` (unique, sorted by release in the model), filtered to `album_type = studio` and `is_studio = true`: the 15 studio albums in release order, Boy → Carnaval de luz; chart above made shorter so all 15 rows fit |
| p04 tour table | Unchanged (all 20 tours, chronological via `tour_name_display` sort-by, album column) |
| p05 openers far right | **Improved**: ranked bar chart with a narrower label area (long titles are truncated to keep bars left); top 3, tie-safe |
| Visual headers | **Off** for all visuals (theme and per visual). Right-click menu, drill-through and tooltips stay. Viewers lose the hover icons: focus mode, "…" menu (export data, show as table, sort, spotlight), pin, copy, filter-icon. Drill-through via right-click still works on p03 (songs) and p06/p03 (shows). **Needs Vini** to right-click once |
| p02 clicking empties the map (both ways) | **Root cause: Gold has no venue coordinates** (`dim_venue.latitude/longitude` are blank for all 932 venues; checked with sqlcmd). The map drew bubbles from blank coordinates and a filtered map had nothing to place. **Fixed in the report**: the map now locates bubbles by `dim_venue[city_name]` (geocoded city), so clicking Dublin shows the Dublin bubble (verified with a Dublin filter). All data visuals on every page now filter each other (`DataFilter`, no highlight). Proper fix belongs to the data side (below) |
| p02 gap, cities table scroll | **Fixed** gap (map moved up); the cities table now scrolls on purpose (all 384 cities) |
| p09 author block | **Added**: "Built by Vinicius Baccarini" with a "LinkedIn ↗" button (web URL), plus "Fan-made portfolio project, not affiliated with U2, their management or their label" in the credits. The button does not appear in PDF exports; **Needs Vini** to see and click it in the service |

### For the data-analyst / data-engineer (round 3)

12. **Venue coordinates are missing in Gold** (`dim_venue.latitude`/`longitude` blank for every venue). setlist.fm
    returns `city.coords` (lat/long) per venue; please carry them through Silver to Gold. With coordinates, the map
    can go back to latitude/longitude (more precise than geocoding city names; ambiguous names such as "Dublin" vs
    Dublin, Ohio are geocoded by name today).
13. Item 7 (sort-by) is resolved by `album_label` for albums; `tour_name_display` already sorts by `tour_order`.

### Data-analyst status (2026-10-22, model `sm_u2_live`; report not edited)

| Item | Status |
| --- | --- |
| 1 Headline length | **Done**: p01 57, p02 49, p03 47, p04 59, p05 62, p06 64 characters (`Headline p05` names the tour, so its length follows the data) |
| 2 Locale-safe FORMAT | **Done**: every model text measure uses `FORMAT ( ..., ..., "en-US" )` (headlines, first glimpses, annotations, `Top Song Text`, `Busiest Year Text`, `Filter Context Text`) |
| 3 1,004 vs 1,065 | **Done**: p01 headline now reads "1,874 shows in 50 years; I Will Follow played 1,065 times" (same count as the top-10 bar) |
| 4 is_original / Covers Played | **Done**: `Covers Played` = `Performances` with `dim_song[is_original] = false` (1,119; the setlist.fm cover flag gave 1,316 because it tags Miss Sarajevo, Your Blue Room, Silver and Gold and North and South of the River, which are originals). Miss Sarajevo is `is_original = 1` in Gold. Satisfaction and ~80 other never-played MusicBrainz works: removed from Silver/Gold by the data-engineer (`dim_song` 594 → 514, rule in SPEC-03) |
| 5 Years Since Last Played | **Done**: blank unless exactly one song is in context |
| 6 "< 0.1%" | **Kept** as the report shows it; the model measure is now `#,0.00%` (0.03%) if a two-decimal value is wanted |
| 7 Sort-by | **Checked**: `dim_tour[tour_name_display]` (and `tour_name`) sort by `tour_order` and `dim_album[album_label]` by `album_order` in the model. `album_title` cannot sort by `album_order` (9 titles are shared by an album and a single), so release order needs `album_label` on the axis/rows: gen_report.py line 587 (`Rows: album_title`) and 1413 still use `album_title`. If the p04 tour table still comes out alphabetical, check that the visual sorts on `tour_name_display` and not on a measure |
| 8 p5 headline break | **Done**: "The Joshua Tree Tour 2017 ran on rails: 31 songs, 21.7 a night" |
| 9 p5 intro | **Done**: "Each row is a song, each column a decade; …" |
| 10 Count measures | **Done** in the model: `Cover Songs` 123, `Guest Artists` 62, `Opener Songs` 119, `Tours with Promoted Album` 20, `Studio Albums` 15. The report's own counts give 64 guests and 122 openers because they include snippets, tapes and unmapped names; switching to the model measures changes those two titles |
| 11 Era badge images | **Open (designer + Vini)**: possible with 8 `report_image` rows (data-engineer seed) and a model measure with data category Image URL like `Image Data URI`; worth trying only if the T-32 spike showed data-URI images render in the button slicer |
| Map (coordinator, 2026-10-22) | **Checked**: `dim_venue[latitude]`/`[longitude]` bound (Double, data categories Latitude/Longitude, summarize none, visible as before); DAX returns values for 932 of 933 venues, covering all 1,874 shows. The map can go back to lat/long |
### Round 4 status (dashboard-designer, 2026-10-22)

Pulled first, `scripts/gen_report.py`, pushed with `fab import`, re-exported (0 semantic differences); checked with PDF
exports rendered to PNG (p06 with Boy Tour, p07 with "Bad", p08 with show 33d6f829, p02 with Dublin).

| Item | Status |
| --- | --- |
| Item 12 (venue coordinates) | **Closed: not a data issue.** My query ran during the data-engineer's rebuild. The p02 map is back on latitude/longitude; a Dublin filter shows the single Dublin bubble; all visuals still filter each other |
| Model count measures in titles | **Done**: `[Cover Songs]` 123, `[Guest Artists]` 62, `[Opener Songs]` 119, `[Tours with Promoted Album]` 20, `[Studio Albums]` 15 |
| `album_title` → `album_label` | **Done** everywhere an album is listed or named (p03 song table, p04 matrix, p07 song card, spike) |
| Analyst's new headlines / p5 intro | **Fit**: all headlines fit two lines; p1 "…; I Will Follow played 1,065 times", p5 intro says decades |
| p6 compare chart empty with Boy Tour | **Fixed**: residency dots always shown, plus the compared tours (default the 2015–2019 tours); x-axis follows the data; dynamic title "Every show, one dot: Sphere (amber) vs Boy Tour (grey) · right-click a dot for its setlist" |
| p6 touring Achtung Baby share blank | **Fixed**: 0% with a zero bar, difference +54 pp (DAX checked: 22.1 vs 10.3 songs, 39 vs 32 songs, 54% vs 0%) |
| Drill-through entry points to Show | **Added**: p07 "Every time it was played: N shows" (latest first, all rows); p02 shows list next to the map, filtered by the clicked city/decade; p06 dots are shows (right-click → Show). p01 not added (no space without dropping a visual; the Road page covers "any show") |
| LinkedIn link not visible | **Fixed**: the author line is now an HTML block under the headline: "Built by Vinicius Baccarini · LinkedIn ↗" (16 px, amber link, nothing overlaps; visible in the PDF). Same technique for p08 "Open this show on setlist.fm ↗" (visible). **Needs Vini** to click both in the service |
| U2 360° icon missing in tour tables | **Fixed**: the model's `Tour Icon` now returns the U2 360° glyph (analyst, item 14); the report-side patch is removed and all tour tables use the model measure |
| p07 "Opener 1%" with no bar | **Fixed**: any non-zero share draws at least a 1% bar; 0% stays empty |
| "Songs per show, by year" x-axis without years | **Accepted as is (Vini)**, no Deneb redo. Earlier note: axis labels still do not render at this size in the export (tried taller box and a continuous axis). Next try: replace with the Deneb year chart. **Needs Vini** to say whether it is acceptable meanwhile |
| Footer "credits on page 9" | **Fixed**: "credits on the About page"; no other page numbers in visible text |
| Visual headers off, drill-through | Unchanged from round 3; **Needs Vini** to right-click once on p02, p03, p06, p07 |

### For the data-analyst (round 4)

14. **Done (analyst)**: `Tour Icon` returns no image for "U2 360°" (the report patches it with `glyph_u2_360.svg`); add that glyph to the
    model measure so the patch can go.
| 14 U2 360° tour icon | **Done** (data-analyst, 2026-10-22): `Tour Icon SVG` / `Tour Icon` return the glyph_u2_360.svg markup for U2 360°; all 25 tours have an icon in the model, so the report patch can go |

# SPEC-06 · Report

Owner: dashboard-designer (design, PBIR) · data-analyst (measure needs, insight text) · Item: `rpt_u2_live` (PBIR)

## Design principles

- One question per visual; page titles are statements of the finding, not labels ("Where the Streets… opened more shows than any other song" beats "Openers").
- Canvas 1280 × 720, 8 px grid, 24 px outer margin; same header band and filter pane position on every page.
- Theme file `fabric/rpt_u2_live.Report/StaticResources/RegisteredResources/u2-theme.json` built from the `u2-design-system` skill. Modern dark look with concert photography
  and tour icons, using only freely licensed images (Wikimedia Commons: CC BY, CC BY-SA, CC0, public domain) listed in
  `docs/design/images/credits.csv` and credited on page 9 "About the data". No copyrighted album art, logos or photos.
- Accessible: text contrast ≥ 4.5:1, never color as the only encoding, alt text on every visual, tab order set.
- No report-level measures (Power BI *Publish to web* rejects reports that have them): every measure a visual uses,
  including presentation helpers (HTML blocks and their `<name> · <visual>` wrappers, titles, colours, Top N ranks),
  lives in `sm_u2_live` and is owned by the data-analyst. The model is the source of their DAX: SPEC-05
  "Report-support measures (Publish to web)". `scripts/gen_report.py` only references them by name and writes no
  `reportExtensions.json`; a new page asks the data-analyst for its measures before the visuals are generated.
- Interactions: slicers for era, tour, decade, continent; cross-highlight on; drill-through to Song and Show pages.

## Pages

| # | Page | Visuals (minimum) | Questions |
| --- | --- | --- | --- |
| 1 | Overview | KPI cards (Shows, Distinct Songs, Countries, Years active), shows per year column chart with era bands, top 10 songs bar | Q1, Q2 |
| 2 | On the road | Map of venues sized by shows, table of most-visited cities, shows by continent over decades | Q7 |
| 3 | The songs | Performances ranking with debut and last-played years, rarities table, scatter "year released vs. performances" | Q2, Q3 |
| 4 | Albums on stage | 100% stacked area: album share of performances by year; promoted-album share per tour bar | Q4, Q5 |
| 5 | Setlist evolution | Heatmap song × year (top 40 songs), setlist variety per tour, openers/closers ranking | Q6, Q8 |
| 6 | Sphere vs. touring | Side-by-side comparison of residency and tours: variety, songs per show, album shares | Q10 |
| 7 | Song detail (drill-through) | Timeline of performances, tours, positions (opener/encore share), first/last show links | Q3 |
| 8 | Show detail (drill-through) | Setlist in order with set names, venue, tour, link to setlist.fm | Q8 |
| 9 | About the data | Sources and credits (data sources and every image: title, author, licence, link), limitations (unrecorded setlists, unmapped songs), refresh date | — |
| 10 | Next tour | Predicted 2027 setlist in order (ticket with chance bars, new vs. older songs, main set/encore), the 25 new songs by release with their chance, backtest precision of the model vs. B1–B3, predicted vs. played per show and how the chances move (empty until the first show); see SPEC-09 §9.8 | Q12 |

## Process

1. Designer writes wireframes in `docs/design/wireframes.md` (ASCII or Mermaid block layout per page) and the theme JSON. Vini approves.
2. Designer builds pages in PBIR against the published semantic model; Vini opens the `.pbip` in Power BI Desktop to check.
3. Analyst writes page titles and annotation text from validated numbers.
4. Vini exports screenshots to `docs/img/` for the README.

## Acceptance criteria

- Every question Q1–Q10 maps to at least one visual (traceability table kept in `docs/design/wireframes.md`).
- Report opens in Power BI Desktop without errors or "fix this" visuals; each page renders in under 5 s on Direct Lake.
- Accessibility checklist in the `u2-design-system` skill completed for every page.
- Every image in the report is in `docs/design/images/credits.csv` with a free licence and credited on page 9.

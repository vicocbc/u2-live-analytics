# SPEC-05 · Semantic model

Owner: data-analyst · Item: `sm_u2_live` (Direct Lake on `wh_gold`, authored as TMDL in PBIP)

## Model

- Storage mode: Direct Lake **on OneLake** (not "on SQL endpoints") over the tables of warehouse `wh_gold` (schema `dbo`). Tables only, no views, so no
  DirectQuery fallback. `bit` columns arrive as Boolean.
- `report_image` and `report_image_chunk` (SPEC-04, presentation assets) are in the model, hidden, with
  `report_image_chunk[image_id]` → `report_image[image_id]` (many-to-one, single direction) and no other relationship.
- `dq_run_log` is in the model (hidden from navigation except on the "About the data" page) for the last refresh status.
- Relationships (single direction, many-to-one, dimension → fact):
  - `fact_performance[date_key]` → `dim_date`, `[song_key]` → `dim_song`, `[tour_key]` → `dim_tour`, `[venue_key]` → `dim_venue`, `[show_key]` → `dim_show`
  - `fact_show[date_key|tour_key|venue_key|show_key]` → the same dimensions
  - No fact-to-fact relationship: both facts meet only through shared dimensions, which avoids ambiguous filter paths. The show drill-through page filters on `dim_show`.
  - `fact_setlist_prediction[as_of_date_key]` → `dim_date[date_key]`, `[tour_key]` → `dim_tour`, `[song_key]` →
    `dim_song`; `fact_setlist_backtest[tour_key]` and `fact_setlist_model_coef[tour_key]` → `dim_tour` (T-50, SPEC-09).
    The three facts are leaves like the others (no fact-to-fact relationship, single direction), so no ambiguous path.
  - `dim_song[album_key]` → `dim_album[album_key]` (active)
  - No relationship on `dim_tour[album_promoted_key]` (an inactive one was removed after the BPA run on 2026-10-22,
    `docs/model-bpa.md` #9): `Promoted Album Share %` applies the promoted album with `TREATAS`.
- Best-practice analysis: Tabular Editor 2 with Microsoft's `BPARules.json` (2026-10-22), 22 rules fired; each one is
  fixed or justified in `docs/model-bpa.md`.
- Hide all key columns and technical flags from report view; expose friendly names via display names where needed.
- Sort-by columns: `month_name` by `month`, `day_name` by `day_of_week`, `tour_name_display` and `tour_name` by
  `tour_order`, `album_label` by `album_order`. `album_title` cannot be sorted by `album_order` because 9 titles are
  shared by an album and a single (e.g. Rattle and Hum, One, Pride): visuals use `album_label` (SPEC-04, unique).
  `dim_show[show_label]` must be unique for drill-through (SPEC-04).
- Mark `dim_date` as date table.
- Data categories on `dim_venue`: latitude, longitude, city, country.

## Measures (display folder in brackets)

| Measure | Definition (intent) | Question |
| --- | --- | --- |
| `Shows` [Shows] | count of `fact_show` | Q1 |
| `Shows with Setlist` [Shows] | shows where `has_setlist` | Q1 |
| `Countries`, `Cities`, `Venues` [Places] | distinct counts over shows | Q1, Q7 |
| `Performances` [Songs] | rows of `fact_performance` excluding snippets, tapes and fragments (`is_snippet`, `is_tape`, `is_fragment` all false) | Q2 |
| `Distinct Songs` [Songs] | distinct `song_key` over `Performances` | Q2, Q6 |
| `Avg Songs per Show` [Songs] | `Performances / Shows with Setlist` | Q8 |
| `Live Debuts` [Songs] | `Performances` rows with `is_live_debut` (fragment debut excluded) | Q3 |
| `Rarities` [Songs] | songs with ≤ 2 full performances in context | Q2 |
| `Years Since Last Played` [Songs] | current year − last played year | Q3 |
| `Promoted Album Share %` [Albums] | performances whose song album = tour's promoted album ÷ performances (uses `USERELATIONSHIP` / `TREATAS`) | Q4 |
| `Album Share %` [Albums] | performances of the album ÷ all performances in context | Q5 |
| `Setlist Variety` [Tours] | `Distinct Songs / Avg Songs per Show` per tour | Q6 |
| `Covers Played`, `Guest Appearances` [Songs] | | Q9 |
| `First Show Date`, `Last Show Date` [Shows] | min/max date in context | Q3, Q7 |
| `Predicted Probability` [Prediction] | model probability, latest as-of date in context (mean above song level) | Q12 |
| `Predicted Songs` [Prediction] | count of `predicted_in_setlist` rows, latest as-of date (never a sum of probabilities) | Q12 |
| `Hit Rate` [Prediction] | predicted songs played in full at a show ÷ predicted songs, mean over shows played; blank before the first show | Q12 |
| `Model vs. Baseline` [Prediction\Backtest] | model − selected baseline (default B1) on mean `precision_at_n`, album tours from Elevation on | Q12 |

Every measure has: a format string, a description (shown in tooltips), and a display folder.

Default exclusion (consistent with SPEC-04 `fact_show.song_count`): every song-level measure builds on
`Performances`, so snippets, tapes and fragments (`fact_performance[is_fragment]`, e.g. The Cry as a lead-in to The
Electric Co.) are out by default. Only measures whose name says so include them (`All Performances incl. Snippets,
Tapes and Fragments` [Songs\Data quality], used on the About page to reconcile with Silver row counts).

```dax
Performances =
CALCULATE (
    COUNTROWS ( fact_performance ),
    KEEPFILTERS ( fact_performance[is_snippet] = FALSE () ),
    KEEPFILTERS ( fact_performance[is_tape] = FALSE () ),
    KEEPFILTERS ( fact_performance[is_fragment] = FALSE () )
)
```

Check (T-28): `Performances` at grand total = `SUM(fact_show.song_count)` in T-SQL, and = Silver performances with
`is_tape = 0 AND is_snippet = 0` minus the fragment's performances minus `ignore`-mapped rows. On Silver run
`20261021T154532Z`: 29,730 − 364 (The Cry) − 0 = **29,366** expected.

Gold facts the measures rely on (checked in T-21, `sql/review/gold_validation.sql`, Gold run `20261021T155954Z`):

- `dim_date` has no Unknown row (1976-01-01..2027-12-31, 18,993 gap-free days) so it can be marked as the date table;
  every fact `date_key` exists in it.
- `fact_performance[is_live_debut]` and `dim_song[full_performances]` / `[live_debut_date]` are song-level and also set
  for the fragment (The Cry: debut 1980-09-12, 364). `Live Debuts` therefore counts `is_live_debut` rows **inside
  `Performances`** (fragment excluded, 304 on the full model), and `dim_song[full_performances]` is used only as a
  sort-by helper, never summed in a visual (its total 29,720 includes the fragment and excludes Unknown).
- `dim_tour` holds `(No tour)` (172 shows) as a regular member; `Unknown` has `tour_order` 999999 and no facts.
- Counting rule vs setlist.fm: setlist.fm's song stats count every non-tape entry including snippets; `Performances`
  also drops snippets and fragments. Top 6 match setlist.fm exactly on the setlist.fm rule (I Will Follow 1,065,
  Pride 1,026, Sunday Bloody Sunday 949, Streets 944, With or Without You 881, One 835); on `Performances` Sunday Bloody
  Sunday is 939 (10 snippets) and ranks 4th behind Streets. Report text that compares with setlist.fm says so.

## Built in T-28 (state of `sm_u2_live`)

- Measures: the table above plus `Shows Played`, `First/Last Played Date`, `Is Retired` (no full performance for 10+
  calendar years), `Rare Songs Played`, `Achtung Baby Share %`, `Achtung Baby Performances`, `Opener/Closer/Encore Count`,
  `Encore Share %`, `Share of Tour Shows %`, `Tour Avg Songs per Show`, `Unmapped Song Share %`, `Years Active`,
  `Busiest Year`, `Busiest Year Shows`, `Is Busiest Year`, `Shows/Distinct Songs/Countries vs Previous Era` (previous era
  by the year prefix of `era`, so no `era_order` column is needed), residency vs. touring measures and differences
  (touring default = era "2015-2019 Innocence and Experience", or the tours selected), `Tour Icon SVG`, `Tour Icon`,
  `Image Data URI`, `Image Credit`, `Selected Song`, `Filter Context Text`, `Last Refresh Date`. Tests: `tests/dax/*.dax`.
- Field parameters (calculated tables): `p03 X axis`, `p03 Y axis`, `p05 Setlist position`, `p06 Every show measure`.
- `Shows` counts `fact_show`, so with a song or album on the visual use `Shows Played`; `First/Last Show Date` switch to
  played dates automatically when `dim_song` is cross-filtered.
- Not built in T-28 (wording is T-35's job): `Headline p01`–`p08`, `First Glimpse p01`–`p06`, `KPI Tiles p01`,
  `Head to Head p06`, `Song Card HTML`, `Ticket HTML`, `Busiest Year Text`, `Top City Text`, `Top Song Text`,
  `Promoted Callout Text`, `Annotation p04/p04b/p06/p08`, `Era Band Color` (needs the designer's era palette).
  `Tour Icon Path` (Deneb path data) is not derivable from the glyph files (they use rect/circle/ellipse): the designer
  supplies path-only glyphs if Deneb needs them. `U2 360°` has no glyph (logo image), so `Tour Icon` is blank for it.
- Waiting on Gold (SPEC-04): `dim_album[album_label]` (sort-by), `dim_show[show_label]` uniqueness,
  `dim_tour[show_type]`, `dim_album[release_decade_group]`.

## Setlist prediction (T-50, SPEC-09 §9.7)

- Tables (Direct Lake on OneLake, entity partitions on `wh_gold` like the other facts): `fact_setlist_prediction`
  (281 rows for as-of 2027-02-22), `fact_setlist_backtest` (147), `fact_setlist_model_coef` (104). Keys, `probability`,
  `value`, `model_version` and `_built_at` are hidden (use the measures). New columns: `dim_tour[tour_type]`,
  `dim_tour[is_planned]`, `dim_song[release_role_2027]`, `dim_song[is_single]`. `dim_tour[tour_order]` already sorts
  the planned tour (25) before (No tour) (26); `Tour Icon` is blank for the planned tour until the designer adds a glyph.
- Measure names follow the Title Case convention (`Predicted Probability`, `Predicted Songs`, `Hit Rate`,
  `Model vs. Baseline`).
- Folder `Prediction` (home `fact_setlist_prediction`): every measure reads only the latest `as_of_date_key` in context
  (`Prediction As-Of Date Key`, hidden), so in-tour updates replace the pre-tour prediction without a page filter.
  `Predicted Probability`, `Predicted Songs`, `New Songs Predicted` (8), `Catalog Songs Predicted` (16),
  `Expected Songs per Show` (= N = 24, ignores song/album filters; SPEC-09 §9.11: catalog probabilities are calibrated
  on `is_core` and sum to ≈ 20 for 24 slots, so the page uses N, not a sum of probabilities), `Candidate Songs` (281),
  `Shows Observed`, `Prediction As-Of Date`, `Hit Rate`.
- `Hit Rate`: for each show with a setlist in context (tour of the prediction), the share of the songs predicted by the
  latest prediction made on or before the show date that were performed in full there (`Distinct Songs` with
  `TREATAS` on show and songs); mean over the shows. Blank while the planned tour has no show, and for played tours
  (they have no prediction row).
- Folder `Prediction\Backtest` (home `fact_setlist_backtest`): `Backtest Mean` averages `value` over tours for the
  method and metric in context, using the backtest tours in the `dim_tour` filter if any, else the album tours from
  Elevation (2001) on (SPEC-09 §9.9 scope; a page filtered to the planned tour falls back to it).
  `Mean Precision at N`, `Mean Jaccard First Show`, `Mean Brier Score`, `Model Precision at N`,
  `Selected Baseline` (the one baseline B1/B2/B3 in context, else B1), `Baseline Precision at N`, `Model vs. Baseline`.
- Tests: `tests/dax/Predicted_Songs.dax`, `Predicted_Probability.dax`, `Hit_Rate.dax`, `Model_vs_Baseline.dax`;
  T-SQL cross-checks in `sql/review/measure_checks.sql` (sections "T-50"). Values on Gold 2026-10-26 06:48:10 UTC:
  24 predicted (6 promoted_album + 2 companion_release + 16 catalog; 22 main + 2 encore), Street of Dreams opens at
  0.860; mean `precision_at_n` from Elevation: model 0.6091, B1 0.4818, B2 0.4470, B3 0.4485 (model vs. B1 +12.7 pp);
  Jaccard model 0.4366 vs. B1 0.2903.

## Report presentation layer (T-29 requests)

The report's text, HTML and icon measures (wireframes §7: headlines, "First glimpse", KPI tiles, annotations,
`Tour Icon SVG`/`Tour Icon`/`Tour Icon Path`, `Head to Head p06`, `Song Card HTML`, `Ticket HTML`,
`Image Data URI`, era deltas, residency − touring differences, field parameters) are accepted with these rules:

- They live on the table they read most (`fact_show` or `fact_performance`; image measures on `report_image`) in
  display folders `Report\Text`, `Report\HTML`, `Report\Icons`, `Report\Images`; analytic measures stay in the folders above.
- Every number shown in a text/HTML measure comes from a base measure in the same evaluation (`FORMAT ( [Shows], "#,0" )`),
  never a typed literal, so headlines stay true after a refresh; T-35 validates them against `wh_gold`.
- Glyph SVG markup is held in DAX (`SWITCH` on `dim_tour[tour_name]`, ≤ 1 KB each): no table needed.
- Photos for HTML blocks come from `report_image` / `report_image_chunk` (SPEC-04): `Image Data URI` =
  `"data:" & mime_type & ";base64," & CONCATENATEX ( chunks of the image, [chunk], "", [chunk_no], ASC )`, and
  `Image Credit` returns the CC attribution shown under each photo. The image tables have no relationship to the star
  schema and are hidden from report view.
- If the T-32 spike shows HTML Content Secure rejects data-URI images or long measure strings, `Image Data URI` is
  dropped and the native IMG fallback is used; the image tables can then be removed (SPEC-04 + SPEC-05 together).

## Report-support measures (Publish to web)

Power BI *Publish to web* does not support reports that contain report-level DAX measures, so `rpt_u2_live` keeps
none: the 92 measures that `scripts/gen_report.py` used to write to `reportExtensions.json` live in the model
(2026-10-26), with the same names, DAX, home tables and descriptions.

- Display folder per report page: `Report\p00 Spike`, `Report\p01 Overview`, `Report\p02 On the Road`,
  `Report\p03 The Songs`, `Report\p04 Albums on Stage`, `Report\p05 Setlist Evolution`, `Report\p06 Sphere vs Touring`,
  `Report\p07 Song Detail`, `Report\p08 Show Detail`, `Report\p09 About`, `Report\p10 2027`. Every one of them is used
  by one page only, so there is no shared folder.
- Home table `fact_show` for all of them except `Album Share (no zeros)` and `Album Share Cell` (`fact_performance`).
- They are presentation helpers: HTML blocks and their `<name> · <visual>` clipping/typography wrappers, visual
  titles, colour measures for conditional formatting, exact Top N ranks (`Rank 1 song_title by Performances`,
  `Rank 2 song_title by Opener Count`), page/visual filter flags (`Is One Song`, `Has Promoted Album`), p06 scatter
  axes (`Show Year Decimal`, `Songs in Show p06`) and the page 10 text (`Headline p10`, `First Glimpse p10`, ...).
  Numbers in them still come from the base measures in the same evaluation (rule above).
- Visible (like `Report\Text`); integer helpers use `#,0`, `Show Year Decimal` `0`, `Album Share (no zeros)` `0.0%`,
  text measures have no format string.
- The report references them as ordinary model fields (`SourceRef` entity = home table, no `Schema: "extension"`);
  `reportExtensions.json` must stay empty or absent. A new presentation measure is added here, not in the report.
- Validation: each measure was evaluated in the model and as the original query-scoped definition in the same
  contexts (no filter, Zoo TV Tour, Pride, one show, by tour, by song, plus a show sample and the e+i tours for p06/p08
  and decade × album for p04/p05): identical results, strings compared exactly.

## Acceptance criteria

- Best-practice analysis (Power BI Authoring MCP or Tabular Editor BPA rules) shows no errors.
- Each measure has a DAX query in `tests/dax/` with its expected value for one fixed filter context, checked against a T-SQL query on `wh_gold` (run with `sqlcmd`) and recorded in the task notes.
- Totals reconcile with SPEC-04 acceptance numbers.

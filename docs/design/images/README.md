# Report images

Every file here is either freely licensed on Wikimedia Commons or an original drawing made for this project.
`credits.csv` has one row per file (title, author, licence, source page, pages that use it, tour, changes made).
The licence was checked on each file page on 2026-10-21 (licence template, no deletion or copyright-violation tag).
The report credits them on page 9 "About the data"; the README must do the same.

## Rules (from the `u2-design-system` skill)

- Only CC BY, CC BY-SA, CC0 or public domain. CC BY-SA files stay CC BY-SA; changes are listed in `credits.csv`.
- Photos are shown under a `bg` (#0F1115) overlay: at least 70% opacity everywhere, at least 85% under any text.
- JPG, at most 1280 px wide and 300 KB. Glyphs are 48 × 48 SVG, 2.5 px stroke in `text` (#ECEDEF).

## Tour coverage (24 tours + "(No tour)")

| Era (seeds/tours.csv) | Tour (`tour_name`) | Concert photo | Icon |
| --- | --- | --- | --- |
| 1976-1980 Beginnings | Early Days | none found | original glyph |
| | U2-3 | none found | original glyph |
| | 11 O'Clock Tick Tock | none found | original glyph |
| 1980-1985 Boy to Unforgettable Fire | Boy | `photo_boy_1981_toronto.jpg` | original glyph |
| | October Tour | none found | original glyph |
| | Pre-War Tour | none found | original glyph |
| | War | `photo_war_1983_dublin.jpg` | original glyph |
| | The Unforgettable Fire | `photo_unforgettable_fire_1984_sydney.jpg` | original glyph |
| 1986-1990 Joshua Tree years | A Conspiracy of Hope | none found | original glyph |
| | Joshua Tree Promo Tour | none found | original glyph |
| | The Joshua Tree | `photo_joshua_tree_1987_dublin.jpg` | original glyph |
| | Lovetown | `photo_lovetown_1990_rotterdam.jpg` (500 px only) | original glyph |
| 1992-1998 Zoo TV and PopMart | Zoo TV | `photo_zoo_tv_1992_kiel.jpg`, `photo_zoo_tv_1992_foxborough_wide.jpg` | original glyph |
| | Popmart Tour | `photo_popmart_1997_reggio_emilia.jpg` | original glyph |
| 2001-2006 Elevation and Vertigo | Elevation | `photo_elevation_2001_philadelphia.jpg` | original glyph |
| | How to Dismantle an Atomic Bomb Promo Tour | none found | original glyph |
| | Vertigo | `photo_vertigo_2005_new_york.jpg` | original glyph |
| 2009-2011 U2 360 | U2 360° | `photo_360_2010_rome.jpg` | **free official logo** `icon_360_tour_logo.png` (PD-textlogo) |
| 2015-2019 Innocence and Experience | iNNOCENCE + eXPERIENCE Tour | `photo_innocence_experience_2015_antwerp.jpg` | original glyph |
| | The Joshua Tree Tour 2017 | `photo_joshua_tree_2017_manchester_tn.jpg` | original glyph |
| | eXPERIENCE + iNNOCENCE Tour | `photo_experience_innocence_2018_newark.jpg` | original glyph |
| | The Joshua Tree Tour 2019 | `photo_joshua_tree_2019_singapore.jpg` (stage before the show) | original glyph |
| 2023-present Sphere and after | U2:UV Achtung Baby Live at Sphere | `photo_sphere_2023_las_vegas.jpg`, `photo_sphere_2023_las_vegas_bow.jpg` | original glyph |
| | Carnival De Luz Promo | none found | original glyph |
| — | (No tour) | — | original glyph (`glyph_no_tour.svg`) |

Totals: photos for 15 of 24 tours (7 of 8 eras; none for 1976-1980), free official icon for 1 tour (U2 360°),
original glyphs for 23 tours plus "(No tour)".

## Decisions and rejected candidates

- `File:U2-IE-Logo2015wborder.png` (Innocence + Experience logo) is tagged CC BY-SA 4.0 as the uploader's "own work",
  but its description calls it the tour's official logo. A user cannot licence someone else's logo, so the claim is
  doubtful; not used. Original glyph instead.
- `File:U2.svg` (band wordmark, PD-textlogo) is free but is the band's logo, not a tour icon; not used, to avoid
  implying endorsement.
- `File:U2 Joshua Tree Tour 2017 in Dallas on May 26, 2017.jpg` is free, but the stage screen shows the tour's
  tree artwork full frame; the Bonnaroo photo of the band was chosen instead to keep official artwork out of the report.
- Sphere exterior photos with the "U2 UV Achtung Baby" branding were skipped for the same reason.
- No free photos or logos were found for the 1976-1980 club years, October Tour, Pre-War Tour, A Conspiracy of Hope,
  the promo shows and Carnival De Luz Promo (searches: Commons categories "Concert tours of U2 (musical group)" and
  each tour category, plus full-text searches by tour name, year and "logo").

## Derived and original assets (revision 2–3)

- `badge_era1_glyph.svg`, `badge_era2..8_*.png`: era picker badges (circular crops of the era photos; credits follow
  the source photo).
- `scrim_from_left/right/top/bottom.png`: gradients (`bg` 92% → 0) placed behind text on photos.
- `arrow_*.svg`: hand-drawn style annotation arrows (accent). `timeline_tours.svg`: tour icons at tour start years.
- `icon_kpi_shows/songs/countries.svg`: KPI tile icons.
- Redrawn in revision 2: the three Joshua Tree glyphs (spiky leaf clusters instead of a fork shape) and PopMart
  (lemon with a leaf); the U2 360° logo now has a transparent background.

## Using them in the report

- Static images (page header bands, About mosaic) are registered resources in the report
  (`fabric/rpt_u2_live.Report/StaticResources/RegisteredResources/`), added in T-32..T-34.
- Tour glyphs in tables and cards need an image per row: the data-analyst can expose them as SVG data URIs
  (request in `docs/design/wireframes.md`).

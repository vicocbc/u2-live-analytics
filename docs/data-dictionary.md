# Data dictionary

Generated in T-38 from the TMDL copy `fabric/sm_u2_live.SemanticModel/` (descriptions set through the
Power BI modeling MCP) and the column types of warehouse `wh_gold` (`INFORMATION_SCHEMA.COLUMNS`). Specs:
`docs/specs/SPEC-04-gold.md` (tables, rules) and `docs/specs/SPEC-05-semantic-model.md` (model, measures).
Row counts are from Gold as of 2026-10-22. Regenerate after any model change.

Conventions: `*_key` surrogate keys (SHA2_256 of the natural id, `-1` = Unknown member), `*_id` natural ids,
`_built_at` build timestamp (UTC). Hidden = hidden in the report field list (still usable in measures).
Default exclusion: every song-level measure counts *full* performances only (no snippets, tapes or fragments).

## Tables

| Table | Rows | Hidden | Description |
| --- | --- | --- | --- |
| `fact_performance` | 31079 |  | One row per song performed at a show (setlist.fm), snippets, tapes and fragments included and flagged. |
| `fact_show` | 1874 |  | One row per real show (cancelled and duplicate setlists excluded). |
| `dim_show` | 1875 |  | One row per show with label, setlist.fm link and notes (drill-through target). |
| `dim_song` | 514 |  | Songs: MusicBrainz works by U2, U2 songs without a work, and covers. |
| `dim_album` | 187 |  | MusicBrainz release groups with an official release. |
| `dim_tour` | 26 |  | setlist.fm tours with display names, era, promoted album and residency flag (seeds/tours.csv), plus (No tour). |
| `dim_venue` | 933 |  | Venues with city, country, continent and coordinates. |
| `dim_date` | 18993 |  | Calendar 1976-01-01 to 31 December of next year; marked as date table. |
| `dq_run_log` | 694 | yes | Data quality checks of every run (all layers); shown only on the About page. |
| `report_image` | 3 | yes | Small report photos for HTML Content Secure blocks (presentation asset, not analytic data). |
| `report_image_chunk` | 11 | yes | 8,000-character base64 slices of report_image, reassembled by the Image Data URI measure. |
| `p03 X axis` | — | | Field parameter (calculated table) for a report choose-your-axis/measure control. |
| `p03 Y axis` | — | | Field parameter (calculated table) for a report choose-your-axis/measure control. |
| `p05 Setlist position` | — | | Field parameter (calculated table) for a report choose-your-axis/measure control. |
| `p06 Every show measure` | — | | Field parameter (calculated table) for a report choose-your-axis/measure control. |

Relationships (single direction, many-to-one): `fact_performance` and `fact_show` → `dim_date` (`date_key`),
`dim_tour` (`tour_key`), `dim_venue` (`venue_key`), `dim_show` (`show_key`); `fact_performance` → `dim_song`
(`song_key`); `dim_song` → `dim_album` (`album_key`). `dim_tour[album_promoted_key]` has no relationship:
`Promoted Album Share %` applies it with `TREATAS`;
`report_image_chunk` → `report_image` (`image_id`).

## Columns

### `fact_performance`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `show_key` | bigint | yes | Foreign key to dim_show. |
| `date_key` | int | yes | Foreign key to dim_date (yyyyMMdd). |
| `song_key` | bigint | yes | Foreign key to dim_song (-1 = unmapped setlist name). |
| `tour_key` | bigint | yes | Foreign key to dim_tour. |
| `venue_key` | bigint | yes | Foreign key to dim_venue. |
| `setlist_position` | int |  | 1-based position of the song in the show (tapes included). |
| `set_name` | varchar(50) |  | Main set, Encore 1, Encore 2, or the set name from setlist.fm. |
| `is_encore` | bit |  | True when the song was played in an encore. |
| `is_opener` | bit |  | True for the first non-tape song of the show. |
| `is_closer` | bit |  | True for the last non-tape song of the show. |
| `is_snippet` | bit | yes | Song played only in part (excluded by default). |
| `is_tape` | bit | yes | Recorded intro/outro, not played live (excluded by default). |
| `is_fragment` | bit | yes | Lead-in fragment such as The Cry (excluded by default). |
| `is_cover` | bit |  | setlist.fm flags the song as a cover. |
| `has_guest` | bit |  | A guest artist joined the band for the song. |
| `guest_artist` | varchar(200) |  | Guest artist as written on setlist.fm. |
| `is_live_debut` | bit | yes | First full performance of the song (same-day ties broken by setlist id). |
| `is_only_performance` | bit | yes | The song has exactly one full performance. |
| `_built_at` | datetime2(6) | yes | Build timestamp (UTC). |

### `fact_show`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `show_key` | bigint | yes | Foreign key to dim_show (one row per show, so also the grain key). |
| `date_key` | int | yes | Foreign key to dim_date (yyyyMMdd). |
| `tour_key` | bigint | yes | Foreign key to dim_tour ((No tour) for shows outside a tour). |
| `venue_key` | bigint | yes | Foreign key to dim_venue. |
| `song_count` | int | yes | Full performances at the show (no tapes, snippets or fragments). |
| `has_setlist` | bit | yes | True when setlist.fm lists at least one song. |
| `_built_at` | datetime2(6) | yes | Build timestamp (UTC). |

### `dim_show`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `show_key` | bigint | yes | Surrogate key (SHA2_256 of setlist_id); -1 = Unknown. |
| `setlist_id` | varchar(20) | yes | setlist.fm setlist id. |
| `show_label` | varchar(300) |  | Date, city and venue of the show, e.g. 1987-09-11 · Philadelphia · JFK Stadium. |
| `setlist_url` | varchar(400) |  | Link to the show's page on setlist.fm. (data category WebUrl) |
| `show_info` | varchar(2000) |  | Show notes from setlist.fm, as written there. |
| `_built_at` | datetime2(6) | yes | Build timestamp (UTC). |

### `dim_song`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `song_key` | bigint | yes | Surrogate key (SHA2_256 of song_id); -1 = Unknown (unmapped setlist names). |
| `song_id` | varchar(200) | yes | MusicBrainz work id, or u2:<key> for U2 songs without a work, or cover:<song>:<artist> for covers. |
| `song_title` | varchar(200) |  | Song title (MusicBrainz work title, else the most frequent setlist.fm name). |
| `album_key` | bigint | yes | First album with a recording of the song (studio first). |
| `first_release_year` | int |  | Year of the first release with a recording of the song (re-recordings excluded). |
| `is_original` | bit |  | False for songs written by other artists (setlist.fm cover flag); Passengers, Silver and Gold and North and South of the River count as originals. |
| `cover_artist` | varchar(200) |  | Original artist for covers. |
| `live_debut_date` | date |  | Date of the first full performance. |
| `last_played_date` | date |  | Date of the last full performance. |
| `full_performances` | int | yes | Sort helper only (includes the fragment The Cry); never sum it, use the Performances measure. |
| `_built_at` | datetime2(6) | yes | Build timestamp (UTC). |

### `dim_album`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `album_key` | bigint | yes | Surrogate key (SHA2_256 of the MusicBrainz release group id); -1 = Unknown. |
| `album_id` | varchar(50) | yes | MusicBrainz release group id. |
| `album_title` | varchar(200) |  | Release group title as in MusicBrainz (singles can share a title with an album; use album_type to tell them apart). |
| `release_date` | date |  | First release date of the release group. |
| `release_year` | int |  | Year of the first release. |
| `album_type` | varchar(20) |  | studio, live, compilation, re-recording, ep or single (SPEC-03 rule plus seeds/album_overrides.csv). |
| `is_studio` | bit |  | True for the 15 studio albums, Boy (1980) to Carnaval de luz (2026). |
| `album_order` | int | yes | Chronological sort order. |
| `_built_at` | datetime2(6) | yes | Build timestamp (UTC). |
| `album_label` | varchar(300) |  | Unique display name: album title for studio albums, else title with type and year (e.g. One (single, 1992)); sorted chronologically. (sorted by `album_order`) |
| `release_decade_group` | varchar(30) |  | Release decade of the song's studio album (e.g. 1980s albums), else Not on a studio album; legend of the album share area chart. Q5. |

### `dim_tour`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `tour_key` | bigint | yes | Surrogate key; -1 = Unknown. |
| `tour_name` | varchar(100) | yes | Tour name exactly as on setlist.fm, or (No tour). (sorted by `tour_order`) |
| `tour_name_display` | varchar(100) |  | Tour name for display (seeds/tours.csv). (sorted by `tour_order`) |
| `album_promoted_key` | bigint | yes | Album the tour promoted (inactive relationship to dim_album, used with USERELATIONSHIP). |
| `is_residency` | bit |  | True only for U2:UV Achtung Baby Live at Sphere (2023-24). |
| `era` | varchar(100) |  | Career era (seeds/tours.csv); labels start with the years so they sort chronologically. Blank for (No tour). |
| `first_show_date` | date |  | First show of the tour. |
| `last_show_date` | date |  | Last show of the tour. |
| `tour_order` | int | yes | Chronological sort order. |
| `_built_at` | datetime2(6) | yes | Build timestamp (UTC). |
| `show_type` | varchar(20) |  | Residency (Sphere) or Touring. Q10. |

### `dim_venue`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `venue_key` | bigint | yes | Surrogate key; -1 = Unknown. |
| `venue_id` | varchar(20) | yes | setlist.fm venue id. |
| `venue_name` | varchar(200) |  | Venue name from setlist.fm. |
| `city_name` | varchar(100) |  | City. (data category City) |
| `state_code` | varchar(20) |  | State or province code where setlist.fm has one. (data category StateOrProvince) |
| `country_code` | varchar(10) |  | ISO country code. (data category Country) |
| `country_name` | varchar(100) |  | Country. (data category Country) |
| `continent` | varchar(30) |  | Continent from the country code (u2lib). (data category Continent) |
| `latitude` | decimal(9,6) |  | Latitude of the city (setlist.fm). (data category Latitude) |
| `longitude` | decimal(9,6) |  | Longitude of the city (setlist.fm). (data category Longitude) |
| `_built_at` | datetime2(6) | yes | Build timestamp (UTC). |

### `dim_date`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `date_key` | int | yes | yyyyMMdd. |
| `date` | date |  | Calendar day, 1976-01-01 to 31 December of next year. |
| `year` | int |  | Calendar year. |
| `decade` | varchar(10) |  | Decade label, e.g. 1980s. |
| `quarter` | int |  | Calendar quarter 1-4. |
| `month` | int | yes | Month number 1-12 (sort helper). |
| `month_name` | varchar(20) |  | Month name. (sorted by `month`) |
| `day_of_week` | int | yes | Day of week number (sort helper). |
| `day_name` | varchar(20) |  | Day name. (sorted by `day_of_week`) |
| `_built_at` | datetime2(6) | yes | Build timestamp (UTC). |

### `dq_run_log`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `run_id` | varchar(100) |  | Run id (UTC yyyyMMddTHHmmssZ) of the notebook or Gold build. |
| `layer` | varchar(20) |  | bronze, silver or gold. |
| `check_name` | varchar(200) |  | Name of the data quality check. |
| `value` | varchar(200) |  | Measured value as text. |
| `status` | varchar(10) |  | pass, warning or fail. |
| `checked_at` | datetime2(6) |  | UTC time of the check. |

### `report_image`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `image_id` | varchar(100) | yes | Photo id used to pick the photo in a visual filter, e.g. photo_zoo_tv_1992_kiel. |
| `file_name` | varchar(200) |  | Source file in docs/design/images/report/. |
| `mime_type` | varchar(50) |  | image/jpeg or image/png. |
| `bytes` | int |  | File size in bytes. |
| `base64_length` | int |  | Length of the base64 text (sum of chunk lengths). |
| `chunk_count` | int |  | Number of 8,000-character chunks. |
| `credit_text` | varchar(400) |  | Attribution shown with the photo (author, licence, source). |
| `license` | varchar(50) |  | Licence, e.g. CC BY-SA 4.0. |
| `source_url` | varchar(400) |  | Wikimedia Commons file page. |
| `_built_at` | datetime2(6) | yes | Build timestamp (UTC). |

### `report_image_chunk`

| Column | Warehouse type | Hidden | Description |
| --- | --- | --- | --- |
| `image_id` | varchar(100) | yes | Photo id (report_image). |
| `chunk_no` | int |  | 1-based chunk order. |
| `chunk` | varchar(8000) |  | Up to 8,000 characters of the photo's base64 text. |
| `_built_at` | datetime2(6) | yes | Build timestamp (UTC). |

## Measures

### Albums

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `'Promoted Album Share %' =` | `fact_performance` | `#,0.0%` | Share of full performances whose song's first album is the album the tour promoted, over tours that promoted one. Q4. |
| `Achtung Baby Performances` | `fact_performance` | `#,0` | Full performances of songs from Achtung Baby (per show on the p06 scatter). Q10. |
| `Achtung Baby Share %` | `fact_performance` | `#,0.0%` | Share of full performances from Achtung Baby (the album played in full at the Sphere). Q10. |
| `Album Share %` | `fact_performance` | `#,0.0%` | Share of full performances in context that come from the album(s) in context (by the song's first album). Q5. |
| `Studio Albums` | `fact_show` | `#,0` | Studio albums in the catalog (15: Boy to Carnaval de luz; Songs of Surrender is a re-recording). Q5. |

### Places

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `'Countries vs Previous Era' =` | `fact_show` | `+#,0;-#,0;0` | Countries in the one era in context minus the previous era; blank when no single era is selected. Q1, Q7. |
| `Cities` | `fact_show` | `#,0` | Distinct cities (city name within country) with at least one show in context. Q1, Q7. |
| `Countries` | `fact_show` | `#,0` | Distinct countries with at least one show in context. Q1, Q7. |
| `Venues` | `fact_show` | `#,0` | Distinct venues with at least one show in context. Q1, Q7. |

### Report / Icons

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `'Tour Icon SVG' =` | `fact_show` | | SVG markup of the tour's glyph (docs/design/images/glyph_*.svg) for one tour in context, for HTML Content Secure; blank for U2 360 (official logo used as image) and for several tours. |
| `'Tour Icon' =` | `fact_show` | | Tour glyph as an SVG data URI (data category Image URL) for native tables and cards. |

### Report / Images

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `'Image Data URI' =` | `fact_show` | | Base64 data URI of the one report photo in context (filter report_image[image_id] on the visual); blank when none or several. |
| `Image Credit` | `fact_show` | | Attribution (author, licence, source) of the one report photo in context, shown under the photo. |

### Report / Text

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `'Busiest Year Text' =` | `fact_show` | | Annotation for the shows-per-year chart, e.g. 1981: 152 shows, the busiest year. Q1. |
| `'Filter Context Text' =` | `fact_show` | | Plain sentence of the filters in effect (era, tour, years), appended to 'First glimpse' paragraphs. |
| `'First Glimpse p02' =` | `fact_show` | | HTML standfirst of page 2 (Q7): countries, continents, top country with its share, home city span. |
| `'First Glimpse p03' =` | `fact_show` | | HTML standfirst of page 3 (Q2, Q3): songs played, staples, one-offs and retired songs. |
| `'First Glimpse p04' =` | `fact_show` | | HTML standfirst of page 4 (Q4, Q5): overall 1980s share, promoted-album share, Zoo TV example. |
| `'First Glimpse p05' =` | `fact_show` | | HTML standfirst of page 5 (Q6, Q8): how to read the heatmap, songs per night and songs per tour on the tours with 40+ shows since 1992. |
| `'First Glimpse p06' =` | `fact_show` | | HTML standfirst of page 6 (Q10): residency nights, songs per night and song pool vs. the compared tours. |
| `'Headline p01' =` | `fact_show` | | Finding-style headline of page 1 (Q1, Q2): shows, span in years and how often the top song was played (≤ 65 characters). |
| `'Headline p02' =` | `fact_show` | | Finding-style headline of page 2 (Q7): the city with the most shows. |
| `'Headline p04' =` | `fact_show` | | Finding-style headline of page 4 (Q5): share of 1980s-album songs in the 2015-2019 setlists (≤ 65 characters). |
| `'Headline p05' =` | `fact_show` | | Finding-style headline of page 5 (Q6): the tour (40+ shows) with the most fixed setlist (≤ 65 characters). |
| `'Is Busiest Year' =` | `fact_show` | `0` | 1 for the year with the most shows among the years shown in the visual (for the accent bar), else 0. Q1. |
| `'Top Song Name' =` | `fact_show` | | Most-performed song in context (ties: alphabetical first). Helper for text measures. Q2. |
| `'Top Song Text' =` | `fact_show` | | Most-performed song and its count, e.g. I Will Follow · 1,065 times. Q2. |
| `Annotation p04` | `fact_show` | | Chart annotation on page 4 (Q5): 1980s-album share on the 2017 Joshua Tree anniversary tour. |
| `Annotation p06` | `fact_show` | | Annotation on page 6 (Q10): Achtung Baby share difference, residency minus touring, in points. |
| `First Glimpse p01` | `fact_show` | | HTML standfirst of page 1 (Q1, Q2) with the key numbers in bold and the filters in effect. |
| `Headline p03` | `fact_show` | | Finding-style headline of page 3 (Q2): concentration of the setlist in ten songs. |
| `Headline p06` | `fact_show` | | Finding-style headline of page 6 (Q10): Achtung Baby share at the Sphere vs. the compared tours (≤ 65 characters). |
| `Last Refresh Date` | `fact_show` | `yyyy-mm-dd hh:nn` | UTC time the Gold tables were last rebuilt (About page). |
| `Selected Song` | `fact_performance` | | Title of the one song in context (drill-through header), else blank. |

### Shows

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `'Busiest Year Shows' =` | `fact_show` | `#,0` | Shows in the busiest year in context. Q1. |
| `'Busiest Year' =` | `fact_show` | `0` | Calendar year with the most shows in context (earliest year on ties). Q1. |
| `'First Show Date' =` | `fact_show` | `yyyy-mm-dd` | First show in context; with a song or album filter, the first show where it was performed in full. Q3, Q7. |
| `'Last Show Date' =` | `fact_show` | `yyyy-mm-dd` | Last show in context; with a song or album filter, the last show where it was performed in full. Q3, Q7. |
| `'Shows vs Previous Era' =` | `fact_show` | `+#,0;-#,0;0` | Shows in the one era in context minus shows in the previous era (eras sort by their year prefix); blank when no single era is selected. Q1. |
| `Shows` | `fact_show` | `#,0` | Number of real shows (cancelled and duplicate setlists excluded in Silver). Q1. |
| `Shows with Setlist` | `fact_show` | `#,0` | Shows where setlist.fm lists at least one song; denominator for per-show averages. Q1, Q8. |
| `Years Active` | `fact_show` | `#,0` | Distinct calendar years with at least one show in context. Q1. |

### Songs

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `'Distinct Songs vs Previous Era' =` | `fact_performance` | `+#,0;-#,0;0` | Distinct songs in the one era in context minus the previous era; blank when no single era is selected. Q1. |
| `'Is Retired' =` | `fact_performance` | `0` | 1 when the song has not been performed in full for 10 or more calendar years (the report's definition of retired), else 0. Q3. |
| `'Top 10 Songs Share %' =` | `fact_show` | `#,0.0%` | Share of full performances taken by the ten most-performed songs in context. Q2. |
| `'Years Since Last Played' =` | `fact_performance` | `#,0` | Current year minus the year of the last full performance; blank unless exactly one song is in context. Q3. |
| `Avg Songs per Show` | `fact_performance` | `#,0.0` | Full performances per show with a setlist. Q8. |
| `Cover Songs` | `fact_performance` | `#,0` | Different songs by other artists performed in full in context (is_original = false). Q9. |
| `Covers Played` | `fact_performance` | `#,0` | Full performances of songs written by other artists (dim_song[is_original] = false, so Passengers songs, Silver and Gold and North and South of the River count as originals). Q9. |
| `Distinct Songs` | `fact_performance` | `#,0` | Different songs performed in full in context (unmapped setlist names excluded). Q2, Q6. |
| `First Played Date` | `fact_performance` | `yyyy-mm-dd` | Date of the first full performance in context. Q3. |
| `Guest Appearances` | `fact_performance` | `#,0` | Full performances with a guest artist on stage. Q9. |
| `Guest Artists` | `fact_performance` | `#,0` | Different guest artists (as written on setlist.fm) on full performances in context. Q9. |
| `Last Played Date` | `fact_performance` | `yyyy-mm-dd` | Date of the last full performance in context. Q3. |
| `Live Debuts` | `fact_performance` | `#,0` | First full performances of songs in context (the fragment's debut is excluded with it). Q3. |
| `Performances =` | `fact_performance` | `#,0` | Songs performed in full: snippets, tapes and fragments (The Cry) excluded; base measure for every song-level number. Q2. |
| `Rare Songs Played` | `fact_performance` | `#,0` | Full performances of songs that have at most two full performances in the whole history (career rarities), e.g. per show. Q2, Q10. |
| `Rarities =` | `fact_performance` | `#,0` | Songs with only one or two full performances in context. Q2. |
| `Shows Played` | `fact_performance` | `#,0` | Shows where the songs in context were performed in full (use instead of Shows when a song or album filters the visual). Q2, Q3. |

### Songs / Data quality

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `All Performances incl. Snippets, Tapes and Fragments` | `fact_performance` | `#,0` | Every setlist entry with a name, for reconciling with Silver on the About page; not for analysis. |
| `Unmapped Song Share %` | `fact_performance` | `#,0.00%` | Share of full performances whose setlist.fm name could not be matched to a song (About page). |

### Songs / Show structure

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `Closer Count` | `fact_performance` | `#,0` | Times the song closed a show (last non-tape song). Q8. |
| `Encore Count` | `fact_performance` | `#,0` | Full performances played in an encore. Q8. |
| `Encore Share %` | `fact_performance` | `#,0.0%` | Share of full performances played in an encore. Q8. |
| `Opener Count` | `fact_performance` | `#,0` | Times the song opened a show (first non-tape song). Q8. |
| `Opener Songs` | `fact_performance` | `#,0` | Different songs that opened at least one show in context. Q8. |

### Tours

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `'Tour Avg Songs per Show' =` | `fact_performance` | `#,0.0` | Average songs per show of the tour(s) of the shows in context, e.g. to compare one show with its tour. Q8. |
| `Setlist Variety` | `fact_performance` | `#,0.0` | Distinct songs divided by songs per show: 1 means the same setlist every night, higher means more rotation. Q6. |
| `Share of Tour Shows %` | `fact_performance` | `#,0.0%` | Share of shows with a setlist (in the tour or period in context) where the song was performed in full. Q3. |
| `Tours with Promoted Album` | `fact_show` | `#,0` | Tours in context that promoted an album (seeds/tours.csv). Q4. |

### Tours / Residency vs touring

| Measure | Home table | Format | Description |
| --- | --- | --- | --- |
| `'Touring Achtung Baby Share %' =` | `fact_performance` | `#,0.0%` | Share of full performances from Achtung Baby on the compared tours (default: the four 2015-2019 tours). Q10. |
| `'Touring Distinct Songs' =` | `fact_performance` | `#,0` | Different songs played on the compared tours (default: the four 2015-2019 tours). Q10. |
| `'Touring Songs per Show' =` | `fact_performance` | `#,0.0` | Songs per show on the compared tours: the tours selected (residency excluded), by default the four 2015-2019 tours. Q10. |
| `Difference Achtung Baby Share (pp)` | `fact_performance` | `+#,0.0;-#,0.0;0.0` | Residency minus touring Achtung Baby share, in percentage points. Q10. |
| `Difference Distinct Songs` | `fact_performance` | `+#,0;-#,0;0` | Residency minus touring distinct songs. Q10. |
| `Difference Songs per Show` | `fact_performance` | `+#,0.0;-#,0.0;0.0` | Residency minus touring songs per show. Q10. |
| `Residency Achtung Baby Share %` | `fact_performance` | `#,0.0%` | Share of full performances from Achtung Baby at the Sphere residency. Q10. |
| `Residency Distinct Songs` | `fact_performance` | `#,0` | Different songs played at the Sphere residency. Q10. |
| `Residency Songs per Show` | `fact_performance` | `#,0.0` | Songs per show at the Sphere residency, whatever tour is selected. Q10. |

## Measure definitions (DAX)

Long markup measures (`Tour Icon SVG`) are shortened here; the full text is in the TMDL copy.

**'Promoted Album Share %' =**

```dax
VAR Tours =
    ADDCOLUMNS (
        KEEPFILTERS ( VALUES ( dim_tour[tour_key] ) ),
        "@Album", CALCULATE ( MAX ( dim_tour[album_promoted_key] ) )
    )
VAR ToursWithAlbum = FILTER ( Tours, [@Album] <> -1 )
VAR FromPromoted =
    SUMX ( ToursWithAlbum, CALCULATE ( [Performances], TREATAS ( { [@Album] }, dim_album[album_key] ) ) )
VAR AllPerformances =
    SUMX ( ToursWithAlbum, CALCULATE ( [Performances] ) )
RETURN DIVIDE ( FromPromoted, AllPerformances )
```

**Achtung Baby Performances**

```dax
CALCULATE ( [Performances], KEEPFILTERS ( dim_album[album_title] = "Achtung Baby" ), KEEPFILTERS ( dim_album[is_studio] = TRUE () ) )
```

**Achtung Baby Share %**

```dax
DIVIDE ( CALCULATE ( [Performances], KEEPFILTERS ( dim_album[album_title] = "Achtung Baby" ), KEEPFILTERS ( dim_album[is_studio] = TRUE () ) ), [Performances] )
```

**Album Share %**

```dax
DIVIDE ( [Performances], CALCULATE ( [Performances], REMOVEFILTERS ( dim_album ) ) )
```

**Studio Albums**

```dax
CALCULATE ( COUNTROWS ( dim_album ), KEEPFILTERS ( dim_album[is_studio] = TRUE () ) )
```

**'Countries vs Previous Era' =**

```dax
VAR CurrentEra = SELECTEDVALUE ( dim_tour[era] )
VAR PreviousEra = CALCULATE ( MAX ( dim_tour[era] ), REMOVEFILTERS ( dim_tour ), dim_tour[era] < CurrentEra, NOT ISBLANK ( dim_tour[era] ) )
RETURN IF ( NOT ISBLANK ( CurrentEra ) && NOT ISBLANK ( PreviousEra ), [Countries] - CALCULATE ( [Countries], REMOVEFILTERS ( dim_tour ), dim_tour[era] = PreviousEra ) )
```

**Cities**

```dax
COUNTROWS ( CALCULATETABLE ( SUMMARIZE ( fact_show, dim_venue[country_code], dim_venue[city_name] ) ) )
```

**Countries**

```dax
CALCULATE ( DISTINCTCOUNT ( dim_venue[country_code] ), fact_show )
```

**Venues**

```dax
DISTINCTCOUNT ( fact_show[venue_key] )
```

**'Tour Icon SVG' =**

```dax
SWITCH (
    SELECTEDVALUE ( dim_tour[tour_name] ),
    "Early Days", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48' width='48' height='48' role='img' aria-label='Early Days: practice amp'><title>Early Days: practice amp</title><g fill='none' stroke='#ECEDEF' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><rect x='9' y='12' width='30' height='26' rx='3'/><circle cx
    -- ... (shortened, see TMDL)
```

**'Tour Icon' =**

```dax
VAR Svg = [Tour Icon SVG]
RETURN IF ( NOT ISBLANK ( Svg ), "data:image/svg+xml;utf8," & SUBSTITUTE ( Svg, "#", "%23" ) )
```

**'Image Data URI' =**

```dax
VAR Chunks = COUNTROWS ( report_image_chunk )
RETURN
    IF (
        HASONEVALUE ( report_image[image_id] ) && Chunks > 0,
        "data:" & SELECTEDVALUE ( report_image[mime_type] ) & ";base64,"
            & CONCATENATEX ( report_image_chunk, report_image_chunk[chunk], "", report_image_chunk[chunk_no], ASC )
    )
```

**Image Credit**

```dax
SELECTEDVALUE ( report_image[credit_text] )
```

**'Busiest Year Text' =**

```dax
VAR Y = [Busiest Year]
RETURN IF ( NOT ISBLANK ( Y ), FORMAT ( Y, "0", "en-US" ) & ": " & FORMAT ( [Busiest Year Shows], "#,0", "en-US" ) & " shows, the busiest year" )
```

**'Filter Context Text' =**

```dax
VAR OneEra = SELECTEDVALUE ( dim_tour[era] )
VAR OneTour = SELECTEDVALUE ( dim_tour[tour_name_display] )
VAR EraText = IF ( NOT ISBLANK ( OneEra ), "Era " & OneEra )
VAR TourText = IF ( NOT ISBLANK ( OneTour ), "Tour: " & OneTour )
VAR FirstYear = YEAR ( CALCULATE ( MIN ( dim_date[date] ), fact_show ) )
VAR LastYear = YEAR ( CALCULATE ( MAX ( dim_date[date] ), fact_show ) )
VAR YearText = IF ( NOT ISBLANK ( FirstYear ), IF ( FirstYear = LastYear, FORMAT ( FirstYear, "0", "en-US" ), FORMAT ( FirstYear, "0", "en-US" ) & "-" & FORMAT ( LastYear, "0", "en-US" ) ) )
VAR Parts = { EraText, TourText, YearText }
RETURN
    IF (
        NOT ISFILTERED ( dim_tour ) && NOT ISFILTERED ( dim_date ) && NOT ISFILTERED ( dim_venue ),
        "All shows, " & YearText,
        CONCATENATEX ( FILTER ( Parts, NOT ISBLANK ( [Value] ) ), [Value], ", " )
    )
```

**'First Glimpse p02' =**

```dax
VAR Countries = ADDCOLUMNS ( CALCULATETABLE ( VALUES ( dim_venue[country_name] ), fact_show ), "@S", [Shows] )
VAR TopS = MAXX ( Countries, [@S] )
VAR Country = MINX ( FILTER ( Countries, [@S] = TopS ), dim_venue[country_name] )
VAR Continents = CALCULATE ( DISTINCTCOUNT ( dim_venue[continent] ), fact_show )
RETURN
    "<b>" & FORMAT ( [Shows], "#,0", "en-US" ) & " shows</b> in <b>" & FORMAT ( [Countries], "#,0", "en-US" ) & " countries</b> on <b>" & FORMAT ( Continents, "0", "en-US" ) & " continents</b>. <b>" & Country & "</b> alone had <b>" & FORMAT ( TopS, "#,0", "en-US" ) & "</b> (" & FORMAT ( DIVIDE ( TopS, [Shows] ), "0%", "en-US" ) & "), in <b>" & FORMAT ( CALCULATE ( [Cities], dim_venue[country_name] = Country ), "#,0", "en-US" ) & " cities</b>. <span style='color:#A3A9B3'>(" & [Filter Context Text] & ")</span>"
```

**'First Glimpse p03' =**

```dax
VAR Songs = ADDCOLUMNS ( FILTER ( CALCULATETABLE ( VALUES ( dim_song[song_key] ), fact_performance ), dim_song[song_key] <> -1 ), "@P", [Performances], "@R", [Is Retired] )
VAR Played = COUNTROWS ( FILTER ( Songs, [@P] > 0 ) )
VAR Staples = COUNTROWS ( FILTER ( Songs, [@P] >= 50 ) )
VAR Once = COUNTROWS ( FILTER ( Songs, [@P] = 1 ) )
VAR Retired = COUNTROWS ( FILTER ( Songs, [@P] > 0 && [@R] = 1 ) )
RETURN
    "<b>" & FORMAT ( Played, "#,0", "en-US" ) & " songs</b> were played in full: <b>" & FORMAT ( Staples, "#,0", "en-US" ) & "</b> of them 50 times or more, <b>" & FORMAT ( Once, "#,0", "en-US" ) & "</b> only once. <b>" & FORMAT ( Retired, "#,0", "en-US" ) & "</b> have not been played for ten years or more. <span style='color:#A3A9B3'>(" & [Filter Context Text] & ")</span>"
```

**'First Glimpse p04' =**

```dax
VAR Eighties = CALCULATE ( [Album Share %], dim_album[release_decade_group] = "1980s albums" )
VAR Promoted = [Promoted Album Share %]
VAR Zoo = CALCULATE ( [Promoted Album Share %], REMOVEFILTERS ( dim_tour ), dim_tour[tour_name] = "Zoo TV" )
RETURN
    "Every new album gets its moment: on tours that promoted one, <b>" & FORMAT ( Promoted, "0%", "en-US" ) & "</b> of the songs came from it (<b>" & FORMAT ( Zoo, "0%", "en-US" ) & "</b> Achtung Baby on Zoo TV). Over the whole career, <b>" & FORMAT ( Eighties, "0%", "en-US" ) & "</b> of all songs played come from the 1980s albums. <span style='color:#A3A9B3'>(" & [Filter Context Text] & ")</span>"
```

**'First Glimpse p05' =**

```dax
VAR BigTours = FILTER ( ALL ( dim_tour[tour_name_display], dim_tour[first_show_date] ), CALCULATE ( [Shows] ) >= 40 && YEAR ( dim_tour[first_show_date] ) >= 1992 )
VAR SongsPerNight = CALCULATE ( [Avg Songs per Show], REMOVEFILTERS ( dim_tour ), BigTours )
VAR MinPool = MINX ( BigTours, CALCULATE ( [Distinct Songs] ) )
VAR MaxPool = MAXX ( BigTours, CALCULATE ( [Distinct Songs] ) )
RETURN
    "Each row is a song, each column a decade; brighter means played more. Since 1992 a big tour night held about <b>" & FORMAT ( SongsPerNight, "0", "en-US" ) & " songs</b>, drawn from <b>" & FORMAT ( MinPool, "0", "en-US" ) & " to " & FORMAT ( MaxPool, "0", "en-US" ) & " songs</b> per tour. <span style='color:#A3A9B3'>(" & [Filter Context Text] & ")</span>"
```

**'First Glimpse p06' =**

```dax
VAR ResShows = CALCULATE ( [Shows], REMOVEFILTERS ( dim_tour ), dim_tour[is_residency] = TRUE () )
VAR Compare = IF ( ISFILTERED ( dim_tour[tour_name_display] ), "the selected tours", "the four 2015-2019 tours" )
RETURN
    "<b>" & FORMAT ( ResShows, "0", "en-US" ) & " nights</b> in one room: <b>" & FORMAT ( [Residency Songs per Show], "0.0", "en-US" ) & " songs</b> a night from a pool of <b>" & FORMAT ( [Residency Distinct Songs], "0", "en-US" ) & "</b>, against <b>" & FORMAT ( [Touring Songs per Show], "0.0", "en-US" ) & "</b> from <b>" & FORMAT ( [Touring Distinct Songs], "0", "en-US" ) & "</b> on " & Compare & "."
```

**'Headline p01' =**

```dax
VAR Y1 = YEAR ( [First Show Date] )
VAR Y2 = YEAR ( [Last Show Date] )
VAR Song = [Top Song Name]
VAR Times = CALCULATE ( [Performances], dim_song[song_title] = Song )
RETURN
    FORMAT ( [Shows], "#,0", "en-US" ) & " shows in " & FORMAT ( Y2 - Y1, "0", "en-US" ) & " years; " & Song
        & " played " & FORMAT ( Times, "#,0", "en-US" ) & " times"
```

**'Headline p02' =**

```dax
VAR Cities = ADDCOLUMNS ( CALCULATETABLE ( SUMMARIZE ( fact_show, dim_venue[country_name], dim_venue[city_name] ) ), "@S", [Shows] )
VAR TopS = MAXX ( Cities, [@S] )
VAR City = MINX ( FILTER ( Cities, [@S] = TopS ), dim_venue[city_name] )
RETURN City & " hosted " & FORMAT ( TopS, "#,0", "en-US" ) & " shows, more than any other city"
```

**'Headline p04' =**

```dax
VAR Share = CALCULATE ( [Album Share %], REMOVEFILTERS ( dim_tour ), dim_tour[era] = "2015-2019 Innocence and Experience", dim_album[release_decade_group] = "1980s albums" )
RETURN "The 1980s albums still filled " & FORMAT ( Share, "0%", "en-US" ) & " of the 2015-2019 setlists"
```

**'Headline p05' =**

```dax
VAR Tours = ADDCOLUMNS ( FILTER ( ALL ( dim_tour[tour_name_display] ), CALCULATE ( [Shows] ) >= 40 ), "@V", CALCULATE ( [Setlist Variety] ) )
VAR MinV = MINX ( Tours, [@V] )
VAR Tour = MINX ( FILTER ( Tours, [@V] = MinV ), dim_tour[tour_name_display] )
RETURN
    Tour & " ran on rails: " & FORMAT ( CALCULATE ( [Distinct Songs], REMOVEFILTERS ( dim_tour ), dim_tour[tour_name_display] = Tour ), "0", "en-US" ) & " songs, " & FORMAT ( CALCULATE ( [Avg Songs per Show], REMOVEFILTERS ( dim_tour ), dim_tour[tour_name_display] = Tour ), "0.0", "en-US" ) & " a night"
```

**'Is Busiest Year' =**

```dax
VAR ThisYear = [Shows]
VAR MaxYear = MAXX ( ALLSELECTED ( dim_date[year] ), [Shows] )
RETURN IF ( NOT ISBLANK ( ThisYear ), IF ( ThisYear = MaxYear, 1, 0 ) )
```

**'Top Song Name' =**

```dax
VAR Songs = ADDCOLUMNS ( FILTER ( CALCULATETABLE ( VALUES ( dim_song[song_title] ), fact_performance ), NOT ISBLANK ( dim_song[song_title] ) ), "@P", [Performances] )
VAR TopP = MAXX ( Songs, [@P] )
RETURN MINX ( FILTER ( Songs, [@P] = TopP && TopP > 0 ), dim_song[song_title] )
```

**'Top Song Text' =**

```dax
VAR Song = [Top Song Name]
RETURN IF ( NOT ISBLANK ( Song ), Song & " · " & FORMAT ( CALCULATE ( [Performances], dim_song[song_title] = Song ), "#,0", "en-US" ) & " times" )
```

**Annotation p04**

```dax
"2017: " & FORMAT ( CALCULATE ( [Album Share %], REMOVEFILTERS ( dim_tour ), dim_tour[tour_name] = "The Joshua Tree Tour 2017", dim_album[release_decade_group] = "1980s albums" ), "0%", "en-US" ) & " of the set came from the 1980s albums"
```

**Annotation p06**

```dax
FORMAT ( [Difference Achtung Baby Share (pp)], "+0;-0", "en-US" ) & " points of Achtung Baby compared with touring"
```

**First Glimpse p01**

```dax
"From <b>" & FORMAT ( YEAR ( [First Show Date] ), "0", "en-US" ) & "</b> to <b>" & FORMAT ( YEAR ( [Last Show Date] ), "0", "en-US" ) & "</b>: <b>" & FORMAT ( [Shows], "#,0", "en-US" ) & " shows</b> in <b>" & FORMAT ( [Countries], "#,0", "en-US" ) & " countries</b> and <b>" & FORMAT ( [Cities], "#,0", "en-US" ) & " cities</b>, with <b>" & FORMAT ( [Distinct Songs], "#,0", "en-US" ) & " different songs</b>. The busiest year was <b>" & FORMAT ( [Busiest Year], "0", "en-US" ) & "</b>, with <b>" & FORMAT ( [Busiest Year Shows], "#,0", "en-US" ) & " shows</b>. <span style='color:#A3A9B3'>(" & [Filter Context Text] & ")</span>"
```

**Headline p03**

```dax
"Ten songs make up " & FORMAT ( [Top 10 Songs Share %], "0%", "en-US" ) & " of everything they played"
```

**Headline p06**

```dax
"At the Sphere, Achtung Baby was " & FORMAT ( [Residency Achtung Baby Share %], "0%", "en-US" ) & " of each night vs " & FORMAT ( [Touring Achtung Baby Share %], "0%", "en-US" ) & " touring"
```

**Last Refresh Date**

```dax
MAX ( fact_show[_built_at] )
```

**Selected Song**

```dax
SELECTEDVALUE ( dim_song[song_title] )
```

**'Busiest Year Shows' =**

```dax
VAR Y = [Busiest Year]
RETURN IF ( NOT ISBLANK ( Y ), CALCULATE ( [Shows], dim_date[year] = Y ) )
```

**'Busiest Year' =**

```dax
VAR Years = ADDCOLUMNS ( CALCULATETABLE ( VALUES ( dim_date[year] ), fact_show ), "@Shows", [Shows] )
RETURN MINX ( TOPN ( 1, Years, [@Shows], DESC ), dim_date[year] )
```

**'First Show Date' =**

```dax
IF (
    ISCROSSFILTERED ( dim_song ),
    [First Played Date],
    CALCULATE ( MIN ( dim_date[date] ), fact_show )
)
```

**'Last Show Date' =**

```dax
IF (
    ISCROSSFILTERED ( dim_song ),
    [Last Played Date],
    CALCULATE ( MAX ( dim_date[date] ), fact_show )
)
```

**'Shows vs Previous Era' =**

```dax
VAR CurrentEra = SELECTEDVALUE ( dim_tour[era] )
VAR PreviousEra = CALCULATE ( MAX ( dim_tour[era] ), REMOVEFILTERS ( dim_tour ), dim_tour[era] < CurrentEra, NOT ISBLANK ( dim_tour[era] ) )
RETURN IF ( NOT ISBLANK ( CurrentEra ) && NOT ISBLANK ( PreviousEra ), [Shows] - CALCULATE ( [Shows], REMOVEFILTERS ( dim_tour ), dim_tour[era] = PreviousEra ) )
```

**Shows**

```dax
COUNTROWS ( fact_show )
```

**Shows with Setlist**

```dax
CALCULATE ( [Shows], KEEPFILTERS ( fact_show[has_setlist] = TRUE () ) )
```

**Years Active**

```dax
CALCULATE ( DISTINCTCOUNT ( dim_date[year] ), fact_show )
```

**'Distinct Songs vs Previous Era' =**

```dax
VAR CurrentEra = SELECTEDVALUE ( dim_tour[era] )
VAR PreviousEra = CALCULATE ( MAX ( dim_tour[era] ), REMOVEFILTERS ( dim_tour ), dim_tour[era] < CurrentEra, NOT ISBLANK ( dim_tour[era] ) )
RETURN IF ( NOT ISBLANK ( CurrentEra ) && NOT ISBLANK ( PreviousEra ), [Distinct Songs] - CALCULATE ( [Distinct Songs], REMOVEFILTERS ( dim_tour ), dim_tour[era] = PreviousEra ) )
```

**'Is Retired' =**

```dax
VAR Years = [Years Since Last Played]
RETURN IF ( NOT ISBLANK ( Years ), IF ( Years >= 10, 1, 0 ) )
```

**'Top 10 Songs Share %' =**

```dax
VAR Songs = ADDCOLUMNS ( FILTER ( CALCULATETABLE ( VALUES ( dim_song[song_key] ), fact_performance ), dim_song[song_key] <> -1 ), "@P", [Performances] )
RETURN DIVIDE ( SUMX ( TOPN ( 10, Songs, [@P], DESC ), [@P] ), [Performances] )
```

**'Years Since Last Played' =**

```dax
VAR LastPlayed = [Last Played Date]
RETURN IF ( HASONEVALUE ( dim_song[song_key] ) && NOT ISBLANK ( LastPlayed ), YEAR ( TODAY () ) - YEAR ( LastPlayed ) )
```

**Avg Songs per Show**

```dax
DIVIDE ( [Performances], [Shows with Setlist] )
```

**Cover Songs**

```dax
CALCULATE ( [Distinct Songs], KEEPFILTERS ( dim_song[is_original] = FALSE () ) )
```

**Covers Played**

```dax
CALCULATE ( [Performances], KEEPFILTERS ( dim_song[is_original] = FALSE () ) )
```

**Distinct Songs**

```dax
CALCULATE ( DISTINCTCOUNT ( fact_performance[song_key] ), KEEPFILTERS ( fact_performance[is_snippet] = FALSE () ), KEEPFILTERS ( fact_performance[is_tape] = FALSE () ), KEEPFILTERS ( fact_performance[is_fragment] = FALSE () ), KEEPFILTERS ( fact_performance[song_key] <> -1 ) )
```

**First Played Date**

```dax
CALCULATE ( MIN ( dim_date[date] ), CALCULATETABLE ( fact_performance, KEEPFILTERS ( fact_performance[is_snippet] = FALSE () ), KEEPFILTERS ( fact_performance[is_tape] = FALSE () ), KEEPFILTERS ( fact_performance[is_fragment] = FALSE () ) ) )
```

**Guest Appearances**

```dax
CALCULATE ( [Performances], KEEPFILTERS ( fact_performance[has_guest] = TRUE () ) )
```

**Guest Artists**

```dax
CALCULATE ( DISTINCTCOUNT ( fact_performance[guest_artist] ), KEEPFILTERS ( fact_performance[has_guest] = TRUE () ), KEEPFILTERS ( fact_performance[is_snippet] = FALSE () ), KEEPFILTERS ( fact_performance[is_tape] = FALSE () ), KEEPFILTERS ( fact_performance[is_fragment] = FALSE () ) )
```

**Last Played Date**

```dax
CALCULATE ( MAX ( dim_date[date] ), CALCULATETABLE ( fact_performance, KEEPFILTERS ( fact_performance[is_snippet] = FALSE () ), KEEPFILTERS ( fact_performance[is_tape] = FALSE () ), KEEPFILTERS ( fact_performance[is_fragment] = FALSE () ) ) )
```

**Live Debuts**

```dax
CALCULATE ( [Performances], KEEPFILTERS ( fact_performance[is_live_debut] = TRUE () ) )
```

**Performances =**

```dax
CALCULATE (
    COUNTROWS ( fact_performance ),
    KEEPFILTERS ( fact_performance[is_snippet] = FALSE () ),
    KEEPFILTERS ( fact_performance[is_tape] = FALSE () ),
    KEEPFILTERS ( fact_performance[is_fragment] = FALSE () )
)
```

**Rare Songs Played**

```dax
CALCULATE ( [Performances], KEEPFILTERS ( dim_song[full_performances] <= 2 ), KEEPFILTERS ( dim_song[song_key] <> -1 ) )
```

**Rarities =**

```dax
VAR SongsInContext =
    ADDCOLUMNS ( KEEPFILTERS ( VALUES ( dim_song[song_key] ) ), "@Performances", [Performances] )
RETURN
    COUNTROWS ( FILTER ( SongsInContext, dim_song[song_key] <> -1 && [@Performances] >= 1 && [@Performances] <= 2 ) )
```

**Shows Played**

```dax
CALCULATE ( DISTINCTCOUNT ( fact_performance[show_key] ), KEEPFILTERS ( fact_performance[is_snippet] = FALSE () ), KEEPFILTERS ( fact_performance[is_tape] = FALSE () ), KEEPFILTERS ( fact_performance[is_fragment] = FALSE () ) )
```

**All Performances incl. Snippets, Tapes and Fragments**

```dax
COUNTROWS ( fact_performance )
```

**Unmapped Song Share %**

```dax
DIVIDE ( CALCULATE ( [Performances], KEEPFILTERS ( fact_performance[song_key] = -1 ) ), [Performances] )
```

**Closer Count**

```dax
CALCULATE ( [Performances], KEEPFILTERS ( fact_performance[is_closer] = TRUE () ) )
```

**Encore Count**

```dax
CALCULATE ( [Performances], KEEPFILTERS ( fact_performance[is_encore] = TRUE () ) )
```

**Encore Share %**

```dax
DIVIDE ( [Encore Count], [Performances] )
```

**Opener Count**

```dax
CALCULATE ( [Performances], KEEPFILTERS ( fact_performance[is_opener] = TRUE () ) )
```

**Opener Songs**

```dax
CALCULATE ( [Distinct Songs], KEEPFILTERS ( fact_performance[is_opener] = TRUE () ) )
```

**'Tour Avg Songs per Show' =**

```dax
VAR ToursOfShows = CALCULATETABLE ( VALUES ( fact_show[tour_key] ) )
RETURN
    CALCULATE (
        [Avg Songs per Show],
        REMOVEFILTERS ( dim_show ), REMOVEFILTERS ( dim_date ), REMOVEFILTERS ( dim_venue ),
        REMOVEFILTERS ( dim_song ), REMOVEFILTERS ( dim_album ), REMOVEFILTERS ( dim_tour ),
        TREATAS ( ToursOfShows, dim_tour[tour_key] )
    )
```

**Setlist Variety**

```dax
DIVIDE ( [Distinct Songs], [Avg Songs per Show] )
```

**Share of Tour Shows %**

```dax
DIVIDE ( [Shows Played], [Shows with Setlist] )
```

**Tours with Promoted Album**

```dax
COUNTROWS ( FILTER ( CALCULATETABLE ( VALUES ( dim_tour[tour_key] ), fact_show ), CALCULATE ( MAX ( dim_tour[album_promoted_key] ) ) <> -1 ) )
```

**'Touring Achtung Baby Share %' =**

```dax
IF (
    ISFILTERED ( dim_tour[tour_name_display] ),
    CALCULATE ( [Achtung Baby Share %], KEEPFILTERS ( dim_tour[is_residency] = FALSE () ) ),
    CALCULATE ( [Achtung Baby Share %], REMOVEFILTERS ( dim_tour ), dim_tour[era] = "2015-2019 Innocence and Experience" )
)
```

**'Touring Distinct Songs' =**

```dax
IF (
    ISFILTERED ( dim_tour[tour_name_display] ),
    CALCULATE ( [Distinct Songs], KEEPFILTERS ( dim_tour[is_residency] = FALSE () ) ),
    CALCULATE ( [Distinct Songs], REMOVEFILTERS ( dim_tour ), dim_tour[era] = "2015-2019 Innocence and Experience" )
)
```

**'Touring Songs per Show' =**

```dax
IF (
    ISFILTERED ( dim_tour[tour_name_display] ),
    CALCULATE ( [Avg Songs per Show], KEEPFILTERS ( dim_tour[is_residency] = FALSE () ) ),
    CALCULATE ( [Avg Songs per Show], REMOVEFILTERS ( dim_tour ), dim_tour[era] = "2015-2019 Innocence and Experience" )
)
```

**Difference Achtung Baby Share (pp)**

```dax
( [Residency Achtung Baby Share %] - [Touring Achtung Baby Share %] ) * 100
```

**Difference Distinct Songs**

```dax
[Residency Distinct Songs] - [Touring Distinct Songs]
```

**Difference Songs per Show**

```dax
[Residency Songs per Show] - [Touring Songs per Show]
```

**Residency Achtung Baby Share %**

```dax
CALCULATE ( [Achtung Baby Share %], REMOVEFILTERS ( dim_tour ), dim_tour[is_residency] = TRUE () )
```

**Residency Distinct Songs**

```dax
CALCULATE ( [Distinct Songs], REMOVEFILTERS ( dim_tour ), dim_tour[is_residency] = TRUE () )
```

**Residency Songs per Show**

```dax
CALCULATE ( [Avg Songs per Show], REMOVEFILTERS ( dim_tour ), dim_tour[is_residency] = TRUE () )
```

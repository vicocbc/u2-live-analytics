# SPEC-04 · Gold star schema

Owner: data-engineer (build) · data-analyst (contract owner, validation) · Warehouse: `wh_gold` (schema `dbo`) ·
Source: `sql/wh_gold/` · Entry point: `dbo.usp_build_gold @run_id`

This schema is the contract with the semantic model (SPEC-05). Renames need both specs updated together.

## Build

| File in `sql/wh_gold/` | Content |
| --- | --- |
| `tables/*.sql` | One `CREATE TABLE` per Gold table with the types below (idempotent: create only if missing). Adding a column = `ALTER TABLE` script, never drop and recreate (the semantic model binds to the table). |
| `procedures/usp_build_dimensions.sql` | Dimensions from `lk_silver.dbo.*` (cross-database read of the SQL analytics endpoint), each with its Unknown row. |
| `procedures/usp_build_facts.sql` | Facts joined to the freshly built dimensions; unmatched FKs → `-1`. |
| `procedures/usp_dq_gold.sql` | Gold checks from SPEC-07, returned as a JSON array in an `OUTPUT` variable (`@dq_json`). Not a `#dq` temp table: in Fabric Warehouse temp-table rows written inside the transaction are undone by `ROLLBACK`, and a temp table can neither be filled from nor copied into user tables (Msg 15816); a variable survives the rollback (T-20). `@force_fail = 1` adds a failing check (rollback test). |
| `procedures/usp_build_gold.sql` | `BEGIN TRANSACTION` → `DELETE` + `INSERT` every Gold table (dimensions, facts) → `usp_dq_gold` → on a hard failure `ROLLBACK`, else `COMMIT` → append the checks to `dq_run_log` (also after a rollback or error; one `checked_at` per attempt). It does **not** `THROW`: an error raised inside the procedure undoes the whole `EXEC`, including the log rows. |
| `procedures/usp_assert_gold.sql` | `THROW`s when the latest Gold attempt of `@run_id` logged a hard failure (read-only, so nothing is lost). Run as a separate statement right after `usp_build_gold`; the pipeline does the same (SPEC-07). |
| `deploy.txt` | Order in which `sqlcmd` applies the files (tables, then procedures). |

## Rules

- Integer surrogate keys (`*_key`) generated deterministically so keys stay stable between runs:
  `CAST(HASHBYTES('SHA2_256', CAST(<natural_id> AS varchar(400))) AS bigint)` (last 8 bytes of the hash).
  A hard check asserts every key is unique and none equals `-1`.
- Every dimension has an Unknown member with key `-1`; facts never hold null foreign keys. Exception: `dim_date` has
  no Unknown row, because SPEC-05 marks it as the date table (unique, contiguous, non-blank dates); every show has a
  date and a hard check asserts every fact `date_key` exists in `dim_date` (T-19).
- `dim_date` covers 1976-01-01 to 31 December of the current year + 1, at day grain. Generate the days with a
  numbers CTE (cross join of `VALUES` lists); Fabric Warehouse has no recursive CTEs.
- Warehouse types: `bigint`, `int`, `bit` (booleans), `date`, `float` (coordinates), `varchar(n)` (text, UTF-8
  collation; there is no `nvarchar`), `datetime2(6)` (timestamps). Every table also has `_built_at datetime2(6)`.
- One transaction per build: Direct Lake reframes only on the committed state, so the report never sees a partial Gold.
- Tables only, no views in the model's path (views force DirectQuery fallback).

## Facts

### `fact_performance` · one row per song performed at a show (snippets and tapes included, flagged)

| Column | Type | Notes |
| --- | --- | --- |
| `show_key` | bigint | → `dim_show` |
| `date_key` | int | `yyyyMMdd` → `dim_date` |
| `song_key` | bigint | → `dim_song` |
| `tour_key` | bigint | → `dim_tour` |
| `venue_key` | bigint | → `dim_venue` |
| `setlist_position` | int | 1-based position in the show |
| `set_name` | varchar(50) | Main set / Encore 1 / … |
| `is_encore`, `is_opener`, `is_closer` | bit | |
| `is_snippet`, `is_tape` | bit | excluded by default in measures |
| `is_fragment` | bit | copy of `lk_silver.dbo.song.is_fragment` for the mapped song (e.g. The Cry, a lead-in); excluded by default in measures like snippets (Vini, 2026-10-21; SPEC-05 `Performances` filters it) |
| `is_cover` | bit | |
| `has_guest` | bit | `with_artist` not null |
| `guest_artist` | varchar(200) | |
| `is_live_debut` | bit | first full performance of the song across all shows |
| `is_only_performance` | bit | song has exactly one full performance ever |

### `fact_show` · one row per real show

| Column | Type | Notes |
| --- | --- | --- |
| `show_key` | bigint | → `dim_show` (one row per show, so this is also the fact's grain key) |
| `date_key`, `tour_key`, `venue_key` | int, bigint, bigint | FKs |
| `song_count` | int | full performances (no tapes, no snippets, no fragments) |
| `has_setlist` | bit | |

### `dq_run_log` · one row per data quality check per run (all layers; appended, never rebuilt)

| Column | Type | Notes |
| --- | --- | --- |
| `run_id` | varchar(100) | pipeline run id |
| `layer` | varchar(20) | `bronze` / `silver` / `gold` |
| `check_name` | varchar(200) | check name (not `check`: reserved word in T-SQL) |
| `value` | varchar(200) | measured value as text |
| `status` | varchar(10) | `pass` / `warning` / `fail` |
| `checked_at` | datetime2(6) | UTC |

Bronze and Silver notebooks append through `u2lib.quality.Results.write` (Spark connector for Warehouse);
`usp_build_gold` inserts the Gold rows. `usp_build_gold` never deletes from this table.

## Dimensions

| Table | Columns |
| --- | --- |
| `dim_show` | `show_key`, `setlist_id`, `show_label` (e.g. "1987-09-11 · Philadelphia · JFK Stadium"; unique: when several shows share date and venue, append `' · show ' + n` numbered by `setlist_id`, T-27 found 8 such pairs), `setlist_url` (link to setlist.fm), `show_info` |
| `dim_song` | `song_key`, `song_id`, `song_title`, `album_key` (first album), `first_release_year`, `is_original`, `cover_artist`, `live_debut_date`, `last_played_date`, `full_performances` (precomputed for sorting) |
| `dim_album` | `album_key`, `album_id`, `album_title`, `album_label` (unique display name, T-27: `album_title` for studio albums; otherwise `album_title + ' (' + album_type + ', ' + release_year + ')'`; if still not unique, append `' #' + n` by `album_order`), `release_date`, `release_year`, `album_type`, `is_studio`, `album_order` (chronological sort), `release_decade_group` (T-28, for the p04 area chart: `'1980s albums'` … `'2020s albums'` from `release_year` when `is_studio`, else `'Not on a studio album'`; Unknown row too) |
| `dim_tour` | `tour_key`, `tour_name`, `tour_name_display`, `album_promoted_key`, `is_residency`, `show_type` (T-28: `'Residency'` when `is_residency`, else `'Touring'`; legend of the p06 scatter), `era`, `first_show_date`, `last_show_date`, `tour_order` |
| `dim_venue` | `venue_key`, `venue_id`, `venue_name`, `city_name`, `state_code`, `country_code`, `country_name`, `continent`, `latitude`, `longitude` |
| `dim_date` | `date_key`, `date`, `year`, `decade` (e.g. "1980s"), `quarter`, `month`, `month_name`, `day_of_week`, `day_name` |

## Report presentation assets (accepted 2026-10-21 for T-29 wireframes §2/§7)

Small photos for HTML Content Secure blocks, which accept images only as data URIs. Not part of the star schema:
no keys, no relationship to facts or dimensions, hidden in the model, never used in analytic measures.

| Table | Grain | Columns |
| --- | --- | --- |
| `report_image` | one photo | `image_id` varchar(100) (e.g. `photo_zoo_tv_1992_kiel`), `file_name` varchar(200), `mime_type` varchar(50) (`image/jpeg`, `image/png`), `bytes` int, `base64_length` int, `chunk_count` int, `credit_text` varchar(400) (author, licence, source, as in `docs/design/images/credits.csv`), `license` varchar(50), `source_url` varchar(400), `_built_at` |
| `report_image_chunk` | 8,000-character slice of one photo's base64 | `image_id` varchar(100), `chunk_no` int (1-based), `chunk` varchar(8000), `_built_at` |

Load path (same medallion route as every other table; Gold stays a SQL rebuild from Silver):
1. Dashboard-designer: small versions (480 px wide, ≤ 35 KB) in `docs/design/images/report/` and one row each in
   `seeds/report_images.csv` (`image_id`, `file_name`, `mime_type`, `credit_text`, `license`, `source_url`, `note`).
   Only images listed with a CC/PD licence in `credits.csv`. At most 12 images.
2. Data-engineer: `fab cp` the files to `lk_bronze/Files/seeds/report_images/`; `nb_bronze_seeds` reads the manifest,
   base64-encodes each file (lossless, so allowed in Bronze) and writes `bronze_seed_report_image` (manifest + `bytes`,
   `base64_length`) and `bronze_seed_report_image_chunk` (chunks of ≤ 8,000 characters). Hard checks: every manifest
   file exists; reassembled chunks decode to the original bytes.
3. `nb_silver_catalog` copies both tables to `lk_silver.dbo.report_image` / `report_image_chunk` unchanged.
4. `usp_build_dimensions` rebuilds both Gold tables from Silver inside the build transaction.

Gold checks (`usp_dq_gold`): hard — `chunk_no` runs 1..`chunk_count` with no gaps per image, every chunk length ≤ 8,000,
`SUM(LEN(chunk))` = `base64_length`; warning — 0 images (normal until T-32 delivers them), total `base64_length` > 600,000.
T-19 creates both tables (empty until the images arrive). If the T-32 spike rejects data-URI images, both tables are
dropped from SPEC-04/05 together.

Relationship note for SPEC-05: `dim_album` relates to `dim_song` (snowflake via `album_key`) and is used by
`dim_tour.album_promoted_key` through an inactive relationship activated in measures with `USERELATIONSHIP`.

Column types not listed: `*_key` bigint (except `date_key` int), `*_id` and text columns `varchar(n)` sized to the
longest Silver value with margin, `*_date` date, `*_year`/`*_order`/counts int, `latitude`/`longitude` decimal(9,6) (was float until 2026-10-22, model BPA #2; `alter_002`).

## Acceptance criteria

- `sql/wh_gold/` applied from scratch with `sqlcmd` on an empty `wh_gold` creates every object; applying it twice changes nothing.
- Row counts reconcile with Silver: `fact_show` = `dim_show` (minus Unknown) = `lk_silver.dbo.show`; `fact_performance` = `lk_silver.dbo.performance` minus `ignore`-mapped songs.
- A forced hard failure inside `usp_build_gold` leaves the previous Gold rows intact (rollback) and logs the failure in `dq_run_log`.
- No null foreign keys; Unknown members referenced by < 1% of fact rows (log the share).
- Validation queries (run by data-analyst) reproduce three known facts by hand-checking setlist.fm pages: total shows of one tour, the most-played song, and the first show date.

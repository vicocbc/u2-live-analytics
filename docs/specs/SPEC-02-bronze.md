# SPEC-02 · Bronze ingestion

Owner: data-engineer · Lakehouse: `lk_bronze`

## Common rules

These follow the setlist.fm notebook that is already in production (§2.1); new Bronze notebooks copy its patterns.

- One notebook per source. Parameters cell first (tagged `parameters`).
- Save every API response page to `Files/bronze/<source>/u2/<run_id>/page_NNNN.json` before parsing.
- Table names: `bronze_<source>_<entity>` (e.g. `bronze_setlistfm_show`, `bronze_musicbrainz_work`, `bronze_seed_tours`).
- Tables are full snapshots written with `mode("overwrite")` and `overwriteSchema=true`.
- Every table gets `_run_id` (UTC, `yyyyMMddTHHmmssZ`) and `_ingested_at` (timestamp).
- Light typing is allowed in Bronze when it is lossless: `event_date` as `date`, `last_updated` as `timestamp`,
  coordinates as `double`. Everything else stays as delivered.
- API keys come from Azure Key Vault `https://kv-vini-u2.vault.azure.net/` (`API_KEY_SOURCE = "keyvault"`, the
  default); `"inline"` is for quick manual tests only and never saved filled in.
- End each notebook with quality checks that print counts and raise on hard failures (see SPEC-07).

## 2.1 setlist.fm · `nb_u2_load_bronze` (in production)

Loaded for the first time by Vini on 2026-10-21 (run `20261021T114228Z`). Default lakehouse `lk_bronze`.

Source: `GET /rest/1.0/artist/{mbid}/setlists?p=N`, U2 MBID `a3cb23fc-acd3-4ce0-8f36-1e5aa6a18432` (validated
against `GET /artist/{mbid}` before loading), headers `x-api-key`, `Accept: application/json`, `Accept-Language: en`.
1,876 setlists in 94 pages of 20; 0.6 s between calls, backoff on 429/5xx honouring `Retry-After`.

Parameters: `API_KEY_SOURCE`, `KEY_VAULT_URL`, `SECRET_NAME` (`setlistfm-api-key`), `API_KEY_INLINE`, `ARTIST_NAME`,
`ARTIST_MBID`, `MAX_PAGES` (`None` = all), `SLEEP_SECONDS`, `MAX_RETRIES`, `RAW_FOLDER` (`Files/bronze/setlistfm/u2`),
`TABLE_PREFIX` (`bronze_setlistfm`).

| Table | Grain | Columns |
| --- | --- | --- |
| `bronze_setlistfm_setlist_raw` | setlist | `setlist_id`, `version_id`, `event_date` (date), `last_updated` (timestamp), `json_raw` |
| `bronze_setlistfm_show` | setlist | `setlist_id`, `version_id`, `event_date` (date), `last_updated` (timestamp), `artist_mbid`, `tour_name`, `venue_id`, `venue_name`, `city_id`, `city_name`, `state`, `state_code`, `country_code`, `country_name`, `latitude`, `longitude` (double), `show_info`, `setlist_url`, `song_count` (int: non-tape songs with a name) |
| `bronze_setlistfm_performance` | song played at a show | `setlist_id`, `event_date` (date), `set_index`, `set_name` (set name, else `Encore N`, else `Main set`), `encore_number`, `set_position`, `setlist_position` (1-based across the show), `song_name` (trimmed), `song_info`, `is_tape` (boolean), `cover_artist`, `cover_mbid`, `with_artist` |
| `bronze_setlistfm_distinct_song` | song name × cover artist | `song_name`, `cover_artist`, `performances`, `first_played`, `last_played`, `times_as_tape` (input for `song_map` review) |

All four also carry `_run_id` and `_ingested_at`, except `bronze_setlistfm_distinct_song` (derived summary).

Still to do on this notebook (T-22): write its checks to `dq_run_log` with `u2lib.quality` and make the count
check raise instead of only printing; exit with `notebookutils.notebook.exit(json)` for the pipeline (SPEC-07).

## 2.2 MusicBrainz · `nb_bronze_musicbrainz` (new)

Source: `https://musicbrainz.org/ws/2/`, JSON (`fmt=json`), no key, header
`User-Agent: U2LiveAnalytics/0.1 ( <contact e-mail, later the GitHub URL> )` (contact set as a notebook parameter), max 1 request/second, retry with backoff on 503.

Steps:
1. Browse release groups: `release-group?artist=<U2 mbid>&type=album|single|ep&limit=100` (paginate with `offset`).
2. For each release group, browse releases (`release?release-group=<id>&status=official`) and keep the earliest official release.
3. For each kept release: `release/<id>?inc=recordings+recording-level-rels+work-rels+artist-credits` to get tracks, recordings and the works they perform.
4. Browse U2 works directly as a fallback: `work?artist=<U2 mbid>&limit=100`.

| Table | Grain | Key columns |
| --- | --- | --- |
| `bronze_musicbrainz_release_group` | release group | `release_group_id`, `title`, `primary_type`, `secondary_types` (comma list), `first_release_date` |
| `bronze_musicbrainz_release` | kept release | `release_id`, `release_group_id`, `title`, `date`, `country`, `status` |
| `bronze_musicbrainz_track` | track on kept release | `release_id`, `medium_position`, `track_position`, `recording_id`, `recording_title`, `length_ms` |
| `bronze_musicbrainz_recording_work` | recording ↔ work | `recording_id`, `work_id`, `work_title` |
| `bronze_musicbrainz_work` | work | `work_id`, `title`, `type`, `language`, `disambiguation` |

Raw JSON in `Files/bronze/musicbrainz/u2/<run_id>/`.

Expected order of magnitude: a few hundred API calls; at 1 call/s the notebook runs well under an hour.

## 2.3 Seeds · `nb_bronze_seeds` (new)

Copies `seeds/*.csv` (uploaded to `Files/seeds/` with `fab cp` or the portal) into tables `bronze_seed_<file>` as strings.

| Seed | Owner | Columns |
| --- | --- | --- |
| `seeds/tours.csv` | data-analyst | `tour_name` (exact setlist.fm value), `tour_name_display`, `album_promoted` (release group title or blank), `is_residency`, `era` |
| `seeds/song_alias_overrides.csv` | data-analyst | `song_name` (as in setlist.fm), `work_id` (MusicBrainz), `original` or `ignore`, `note`, `is_fragment` (`true` or blank, SPEC-03 §3.2) |
| `seeds/report_images.csv` | dashboard-designer | `image_id`, `file_name` (in `Files/seeds/report_images/`), `mime_type`, `credit_text`, `license`, `source_url`, `note`; loaded with the files as base64 chunks into `bronze_seed_report_image` / `bronze_seed_report_image_chunk` (SPEC-04 "Report presentation assets") |
| `seeds/show_exclusions.csv` | data-analyst | `setlist_id`, `event_date`, `reason` (`cancelled`, `postponed`, `duplicate`), `note` (SPEC-03 §3.1) |
| `seeds/album_overrides.csv` | data-analyst | `release_group_id` (MusicBrainz), `title` (for readability only), `album_type` (SPEC-03 values), `note` |

All seeds also carry a free-text `note` column. Seeds are UTF-8 without BOM (tour and album names contain `°` and `’`).

## Acceptance criteria

- `bronze_setlistfm_show` count equals the API `total` for the run; no duplicate `setlist_id`
  (first run: 1,876 = 1,876, 0 duplicates).
- `bronze_musicbrainz_release_group` contains every U2 studio album from *Boy* (1980) onward; the data-analyst checks the list against the band's discography. Bronze keeps the MusicBrainz types as delivered: *Songs of Surrender* (re-recordings) arrives as a plain `Album` with no secondary type and *Rattle and Hum* as `Album` + `Soundtrack`; Silver classifies both through `seeds/album_overrides.csv` (SPEC-03 §3.2), not through API types.
- Re-running a notebook with the same inputs produces identical row counts.
- Raw JSON for the run exists under `Files/bronze/<source>/u2/<run_id>/`.

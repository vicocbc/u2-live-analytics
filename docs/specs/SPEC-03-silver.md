# SPEC-03 · Silver

Owner: data-engineer (build) · data-analyst (rules review, seeds, mapping review) · Lakehouse: `lk_silver`

## 3.1 Shows · `nb_silver_shows`

| Table | Grain | Columns and rules |
| --- | --- | --- |
| `show` | real show (cancelled removed) | `setlist_id` (PK), `event_date`, `tour_name`, `venue_id`, `venue_name`, `city_name`, `state_code`, `country_code`, `country_name`, `continent` (from country code mapping in `u2lib`), `latitude`, `longitude`, `song_count`, `has_setlist` (`song_count > 0`), `show_info`, `setlist_url` (for Gold `dim_show`, T-19) |
| `show_excluded` | setlist removed | `setlist_id`, `event_date`, `reason` (`cancelled`, `postponed`, `duplicate`) |
| `performance` | song played at a show | `setlist_id`, `event_date`, `set_name`, `is_encore`, `encore_number`, `setlist_position`, `song_name_raw`, `song_key` (`u2lib.songs.normalize_title`), `song_info`, `is_tape`, `is_snippet`, `is_cover`, `cover_artist`, `with_artist`, `is_opener` (first non-tape position, so a tape intro is not the opener), `is_closer` (last non-tape position) |

Rules:
- Drop performances with empty `song_name_raw`; log the count.
- `is_snippet` from `u2lib.songs.is_snippet(song_info)`; snippets stay in the table but are excluded from default measures.
  A snippet is a song played only in part: info segments starting with snippet, partial, short/shortened (also the typo
  "shorted"), cut short, abbreviated, fragment, excerpt, tease, aborted or "first verse". A bare "snippet" segment right
  after a "with …" segment ("with "Teenage Kicks", snippet") or after an intro note ("with US Mix intro / snippet")
  describes the other song, not this one (T-18).
- Shortened versions are snippets (flagged, excluded from default counts) (Vini, 2026-10-21).
- Cancelled/postponed detection via `u2lib.shows.is_cancelled(show_info)`; review every match once by hand and record edge cases in tests.
- Manual exclusions from `bronze_seed_show_exclusions` (`seeds/show_exclusions.csv`: `setlist_id`, `event_date`,
  `reason` in `cancelled`/`postponed`/`duplicate`, `note`) take precedence over the info-text rule and also apply to the
  tour statistics in `nb_silver_catalog`. First row: `3d6f14f` (1979-02-03, "happened a week earlier") → `duplicate`
  (Vini, 2026-10-21); `show` 1,874 + `show_excluded` 2 = 1,876.

## 3.2 Catalog · `nb_silver_catalog`

| Table | Grain | Columns and rules |
| --- | --- | --- |
| `album` | release group kept for analysis | `album_id` (= release group id), `title`, `release_date`, `release_year`, `album_type` (`studio`, `live`, `compilation`, `re-recording`, `ep`, `single`), `is_studio` |
| `song` | MusicBrainz work by U2 | `song_id` (= work id), `title`, `first_album_id` (earliest studio album with a recording of the work, else earliest any album, else null), `first_release_year` (earliest year of any non-re-recording album with a recording of the work), `is_original` (true), `cover_artist` (null; set on cover rows), `is_fragment` (see Fragments) |
| `tour` | tour name from setlist.fm | `tour_name` (PK), `tour_name_display`, `album_promoted_id` (from `bronze_seed_tours`), `is_residency`, `era`, `first_show_date`, `last_show_date`, `shows` |

Album rules:
- Keep a release group only when it has a kept official release in `bronze_musicbrainz_release` (drops ~1,000 bootleg-only groups).
- `album_type`, first rule that applies: (1) `bronze_seed_album_overrides` by `release_group_id`; (2) secondary types contain
  `Live` → `live`; (3) contain `Compilation` → `compilation`; (4) primary `EP` → `ep`; (5) primary `Single` → `single`;
  (6) primary `Album` with no secondary type → `studio`; (7) anything else (`Soundtrack`, `Remix`, …) → `compilation`.
  `is_studio = album_type = 'studio'`. Expected studio list (T-13): Boy, October, War, The Unforgettable Fire, The Joshua
  Tree, Rattle and Hum (override), Achtung Baby, Zooropa, Pop, All That You Can’t Leave Behind, How to Dismantle an
  Atomic Bomb, No Line on the Horizon, Songs of Innocence, Songs of Experience, Carnaval de luz (2026) = 15;
  Songs of Surrender is `re-recording` (override).

Tour rules:
- `album_promoted_id`: match `bronze_seed_tours.album_promoted` to `album.title` with `u2lib.songs.normalize_title` on both
  sides; on several hits prefer `is_studio`, then the earliest `release_date` (e.g. *The Unforgettable Fire* album vs. single).
  A non-blank title that resolves to nothing is a hard failure.
- Shows with null `tour_name` get `tour_name = '(No tour)'` in `show`, and `tour` has one regular row for it
  (`tour_name_display` `(No tour)`, no promoted album, `is_residency` false, `era` blank). 174 of 1,876 Bronze shows (9%),
  too many for the Gold Unknown member (< 1% rule in SPEC-04), so it is a real member (Vini, 2026-10-21).

Covers: songs by other artists played live get a synthetic `song_id = "cover:" + normalize_title(name) + ":" + normalize_title(cover_artist)`, `is_original = false`, no album.

Original vs. cover for MusicBrainz works (T-17): the U2 work list also holds songs U2 recorded but did not write
(Satellite of Love, Stand by Me, Help!, …). `song.is_original = false` for a work when at least one `song_map` row
pointing to it has a `cover_artist` (setlist.fm flags the performance as a cover), and `song.cover_artist` = the most
frequent of those artists. Exceptions, kept `is_original = true` (U2 or members wrote them although setlist.fm tags
another act): Miss Sarajevo `a5a40c84-5e06-3249-ac20-360fac47dfc0` and Your Blue Room
`4004dfec-990d-35e8-899a-32d76450e96c` (Passengers: the four members with Brian Eno), Silver and Gold
`c2f945b8-c4a3-3044-b55e-95aab187644d` (Bono's song, first on Sun City), North and South of the River
`69985e91-92dd-3af4-81d0-f4f7ea259982` (written with Christy Moore). Expected on run `20261021T151020Z` data:
63 works become `is_original = false`.

Works kept in `song` (2026-10-22, T-36 review): a MusicBrainz work is kept only when `song_map` points at it (any
performance, including snippets, tapes and fragments) or it has a recording on a kept release. The artist browse also
returns works U2 never played or recorded (e.g. (I Can't Get No) Satisfaction, Billie Jean), which would otherwise show
as `is_original = true` with no album; 80 were dropped on Gold `2026-10-22 09:33:21 UTC` (`song` 594 → 514 in Gold).

U2 originals without a MusicBrainz work (T-17): an override row with `work_id = original` creates
`song_id = "u2:" + song_key`, `title` = the most frequent setlist.fm name, `is_original = true`. Its `first_album_id`
is the earliest album (studio first, same rule as works) with a track whose `normalize_title(recording_title)` equals the
`song_key`, else null (e.g. Atomic City → single *Atomic City*; Street of Dreams, Silencio, Glorify → *Carnaval de luz*).

Fragments (Vini, 2026-10-21): a song that setlist.fm lists separately but that is only a short lead-in or excerpt
(The Cry, played into The Electric Co.) keeps its own `song_id` and is mapped as usual, but `song.is_fragment = true`.
Driven by the `is_fragment` column (`true`/blank) of `seeds/song_alias_overrides.csv`: the flag goes to the row's target
song (`u2:<song key>` for `original`, else the work id). Default counts (Gold `song_count`, SPEC-05 measures) exclude
fragments exactly like snippets; SPEC-04 carries it as `fact_performance.is_fragment`.

## 3.3 Song mapping · `nb_silver_song_map`

Maps every distinct `song_key` in `performance` to a `song_id`.

Order of resolution (first hit wins), recorded in `match_method`:
1. `override`: `bronze_seed_song_alias_overrides`, matched on `normalize_title(song_name)` = `song_key` for every
   cover artist. `work_id` is a MusicBrainz work id, `original` (synthetic U2 song, §3.2) or `ignore` (`ignore` rows are
   dropped from analysis and listed in the README).
2. `exact`: normalised setlist name = normalised work title.
3. `fuzzy`: `u2lib.matching.best_match` with threshold 92 against work titles.
4. `cover`: performance has `cover_artist` → synthetic cover id.
5. `unmapped`: everything else.

| Table | Columns |
| --- | --- |
| `song_map` | grain (`song_key`, `cover_artist`): `song_key`, `cover_artist` (null for non-covers; Gold joins `performance` on `song_key` and `ISNULL(cover_artist, '')`), `song_name_example`, `song_id`, `match_method` (`override`, `ignore`, `exact`, `fuzzy`, `cover`, `unmapped`), `match_score`, `matched_title`, `match_candidates` (U2 works sharing the title; tie-break: has a first album, earliest year, id), `performances`, `full_performances` (non-tape, non-snippet) |
| Review | `sql/review/song_map_review.sql` (sqlcmd on `wh_gold`): fuzzy matches, unmapped keys ≥ 3, ambiguous titles, covers matched to works, overrides, plus T-18 queries on `show_excluded` and snippets |

The data-analyst reviews every `fuzzy` match and every `unmapped` key with ≥ 3 performances, and adds rows to
`seeds/song_alias_overrides.csv` until the targets below are met.

## Acceptance criteria

- `show` + `show_excluded` = Bronze `bronze_setlistfm_show` (no setlist lost silently).
- Share of non-tape, non-snippet performances mapped to a `song_id` ≥ 98%; unmapped keys listed in a review query.
- No `fuzzy` match below threshold; every fuzzy match reviewed (comment in the overrides file or accepted list).
- `album` has exactly the 15 studio albums listed in §3.2 with `is_studio` true, and Songs of Surrender as `re-recording`.
- `tour` has one row per distinct setlist.fm tour name plus `(No tour)`; every tour with ≥ 20 shows has `album_promoted_id` or an explicit blank with a note in the seed.

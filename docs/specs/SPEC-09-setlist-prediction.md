# SPEC-09 · Setlist prediction for the 2027 tour

Owner: data-scientist (features, model, backtest notebooks) · data-analyst (seeds, independent validation, measures) ·
data-engineer (Silver catalog, Gold tables, pipeline) · dashboard-designer (page) ·
Lakehouse: `lk_silver` · Warehouse: `wh_gold` · Charter question: **Q12** (new, see §9.8)

Predict the setlist of *Carnaval de Luz presents: The Greatest Show on Earth World Tour* (stadiums, first show
2027-02-23 in Mexico City) before it starts, then update the prediction after every show it plays.
Facts below were researched on 2026-10-25 (sources in §9.10).

## 9.1 Context that shapes the model

- **The tour promotes a new album.** *Carnaval de Luz* (16th studio album, 12 tracks + 1 iTunes bonus) comes out
  2026-11-13, about 3 months before the first show. The band says the setlist "draws from across the entire catalogue".
- **The album closes a trilogy.** Two surprise EPs came out earlier in 2026 and are conceptually linked to it:
  *Days of Ash* (2026-02-18, Ash Wednesday) and *Easter Lily* (2026-04-03, Good Friday). This spec first assumed
  a deluxe album carrying both EPs; MusicBrainz lists no deluxe edition as of 2026-10-25 (§9.3). New material =
  25 tracks, listed in `seeds/release_2026_tracks.csv` with release, single flag and date.
- **Singles so far:** Song of the Future (2026-02-18, the only single from either EP), Street of Dreams (2026-07-07),
  Silencio (2026-09-24), The Greatest Show on Earth (2026-10-15, also the tour name).
- **Already played live in 2026** (from setlist.fm, not from the seed): the *Carnival De Luz Promo* sets in Mexico City
  (2026-05-12, already in `seeds/tours.csv`) and the surprise 50th-anniversary show at Mount Temple, Dublin
  (2026-09-25, live debut of Silencio).
- **Not every tour is a comparable tour.** *The Joshua Tree Tour 2017/2019* were anniversary tours playing a 1987
  album in full, and *U2:UV Achtung Baby Live at Sphere* was a residency playing a 1991 album in full. Their setlists
  say little about how U2 tours a new album, so they are not used as training examples (§9.3). They still count for
  "how recently was this song played".
- **Closest analog for the trilogy:** the paired albums *Songs of Innocence* (i+e Tour 2015) and *Songs of
  Experience* (e+i Tour 2018). On the e+i tour the companion album from three years earlier was still played; that is
  the best history we have for how much of the two EPs survives next to the new album.

## 9.2 Inputs

| Input | Change |
| --- | --- |
| `seeds/release_2026_tracks.csv` (new, data-analyst) | `track_title`, `release_title` (the release as the band titles it, for readability), `release_group_id` (MusicBrainz release-group MBID, filled on every row: MusicBrainz titles the EPs *Days of Ash EP* and *Easter Lily EP*, so a title match alone fails), `release_type` (`ep`/`studio`, SPEC-03 values), `release_date`, `track_number`, `is_single`, `single_date`, `single_order` (chronological across the trilogy), `featured_artist` (`;`-separated), `is_spoken_word`, `is_bonus_track`, `note`. Loaded by `nb_bronze_seeds` as `bronze_seed_release_2026_tracks` (25 rows). Rows change only by hand when facts change (a new single, a corrected title). Out of scope by Vini's decision: the 2026 non-album singles *Fireflies* (Martin Garrix & U2, 2026-07-24) and *Yeah, Yeah, Yeah, Yeah, Yeah* (2026-08-28); they are not seed rows and get no new-material features. |
| `seeds/tours.csv` (new column) | `tour_type`: `album` (tour promoting a new studio album), `anniversary`, `residency`, `promo`, `benefit`, `early` (club years before Boy). Expected: `album` for Boy, October, War, The Unforgettable Fire, The Joshua Tree (1987), Lovetown, Zoo TV, PopMart, Elevation, Vertigo, U2 360°, i+e, e+i; `anniversary` for The Joshua Tree Tour 2017 and 2019; `residency` for Sphere; `promo` for the four promo tours (incl. Carnival De Luz Promo); `benefit` for A Conspiracy of Hope; `early` for Early Days, U2-3, 11 O'Clock Tick Tock. `is_residency` stays for SPEC-04/05 compatibility (= `tour_type = 'residency'`). |
| `seeds/tours.csv` (planned tour row) | One row for the 2027 tour with `tour_type` `album`, `album_promoted` `Carnaval de luz` and a new column `is_planned` = `true` (blank on every other row). Its `tour_name` must equal the setlist.fm tour name once the first show is published; until then use `Carnaval De Luz Presents: The Greatest Show On Earth World Tour` and correct it then (task T-53). |
| Singles history for past albums | From MusicBrainz in Silver: `album_type = 'single'` release groups whose normalised title equals a song's normalised title, with the single's first release date. Gives `is_single`/`single_order` for every past studio-album track, so the backtest can use the same features as the 2027 prediction. |

## 9.3 Silver · `nb_silver_catalog` additions

| Table / column | Rule |
| --- | --- |
| `tour.tour_type`, `tour.is_planned` | Copied from the seed. A planned tour has no shows: `first_show_date`, `last_show_date` null, `shows` 0. SPEC-03 acceptance changes to "one row per distinct setlist.fm tour name, plus `(No tour)`, plus planned tours". |
| `release_track` (new) | Grain: track of a release in `release_2026_tracks` (25 rows). Columns: the seed columns + `song_id` + `album_id`. `album_id` resolves by `release_group_id` first (the seed MBID equals `album.album_id`), then by `normalize_title(release_title)` against `album.title` for a row whose id is blank or not in `album`; a row that resolves to nothing is a hard failure. |
| `song` rows for new tracks | Every seed track resolves to a `song_id`: a MusicBrainz work by `normalize_title`, else a synthetic `u2:<song_key>` (same rule as SPEC-03 §3.2 originals). So a new song exists in `dim_song` even before it is played. |
| Release of a new song | Taken from `release_track`, not from `song.first_album_id`, so a later deluxe edition carrying the EP recordings cannot move EP songs to the album through the studio-first rule. T-46 finding (MusicBrainz as of 2026-10-25): *Carnaval de luz* (`09f9581c-52b0-4d2b-bb1b-d5902830b8c1`, Album, 2026-11-13) has one official release with 12 tracks, no deluxe edition, no EP tracks and no bonus *Get Back to Now*, so the concern does not arise today; the release is still taken from the seed. |

## 9.4 Features · `nb_silver_setlist_features`

One row per (song, target tour) in `lk_silver.dbo.setlist_feature`. Target tours = every `album` tour from Zoo TV on
(for the backtest) plus the planned tour. Candidate songs = every original song released before the target tour's first
show, plus covers played in the previous album tour. Every feature uses only shows dated before the target tour's first
show (no leakage). "Played" means a full performance (no tapes, snippets or fragments), as in SPEC-05.

| Feature | Definition |
| --- | --- |
| `prev_album_tour_rate` | Share of shows of the previous `album` tour in which the song was played |
| `last_tour_rate` | Same for the latest tour of any type with ≥ 10 shows (Sphere, for 2027), plus `last_tour_type` |
| `tours_played_share` | Share of `album` tours since the song's release in which it was played at least once |
| `career_rate` | Share of all shows since its release in which it was played |
| `tours_since_last_played` | Number of tours (any type, ≥ 10 shows) since it was last played; null if never played |
| `played_pre_tour` | Number of shows between its release (or the previous tour's end) and the target tour, e.g. promo sets |
| `is_new_material` | Song is on the promoted album or, for 2027, on one of the two EPs |
| `release_role` | `promoted_album`, `companion_release` (the EPs for 2027; *Songs of Innocence* for e+i), `catalog` |
| `days_release_to_tour` | Days from the song's release to the tour's first show (2027: ~102 album, ~321 Easter Lily, ~370 Days of Ash) |
| `is_single`, `single_order` | From §9.2 |
| `is_title_track` | Song title matches the tour or album name (The Greatest Show on Earth; Go (Carnaval de Luz)) |
| `has_featured_artist`, `is_spoken_word`, `is_bonus_track` | From the seed (new material only; false for history) |
| `prev_avg_position`, `prev_encore_rate`, `prev_opener_rate` | Relative position (0 = first, 1 = last), encore and opener shares in the previous album tour |

Targets (backtest tours only): `play_rate` = share of the target tour's shows that played the song; `is_core` =
`play_rate ≥ 0.5`; `in_first_show` = played at the tour's first show.

**Rules fixed in T-47** (code: `u2lib.features`, `u2lib.setlist`; unit-tested):

- *Target tours.* Every `album` tour that has a previous album tour (October … e+i) plus the planned tour. October …
  Lovetown are **training-only** rows: without them Zoo TV, the first backtest tour, would have nothing to train on.
  Anniversary tours and the residency are never targets (checked in the notebook).
- *Shows and "played".* Only shows with a setlist (`show.has_setlist`) count, in rates and in history. A play is a
  `performance` row that is not a tape or a snippet, maps through `song_map` to a `song_id`, and whose song is not a
  fragment; a song played twice in a show counts once (first position). Relative position = rank among the show's
  played songs / (played songs − 1); the opener is the first played song.
- *Planned tour cutoff.* Silver has no date for a planned tour; the notebooks take the announced first show from a
  parameter (`PLANNED_FIRST_SHOW`, 2027-02-23).
- *Candidates.* Original, non-fragment songs released before the cutoff or already played before it; **every** song of
  the promoted album or a companion release, even if released after the first show (The Unforgettable Fire came out a
  month into its tour); covers played on the previous album tour.
- *Release of a song.* 2026 trilogy tracks take release and date from `release_track` (T-46: *Get Back to Now* has no
  `song.first_album_id`); other songs take `first_album_id`'s release date, else 1 January of `first_release_year`.
- *Singles, as of the cutoff* (T-46 findings 1, 2 and 4):
  - a single released more than 12 months after its album is a reissue and never counts (drops exactly *Running to
    Stand Still* 2009 and *Red Hill Mining Town* 2017);
  - a 1 January `single_date` is a year-only MusicBrainz date: an earlier year counts, a later year does not, and the
    same year counts only if the album itself was out before the cutoff. This keeps *The Unforgettable Fire*
    (stored 1984-01-01, really 1985) out of the 1984 tour, and keeps *Discothèque* (1997-01-01) in for PopMart;
    *New Year's Day* (1983-01-01, a real 1 January release) is wrongly left out of the War tour, a training-only tour;
  - `is_single`/`single_order` in `setlist_feature` are **as known before the cutoff**: a single released after the
    tour started is not a single for that tour (e.g. *Even Better Than the Real Thing* for Zoo TV). `single_order` is
    re-ranked per album among the singles that count, by stored date, title key, id; ties of a 1 January date are not
    corrected (no seed override needed: the only wrong order, The Unforgettable Fire before Pride, never applies,
    because by the time both count the songs are catalog). For 2026 this gives per-release orders (Days of Ash: Song
    of the Future 1; Carnaval de luz: Street of Dreams 1, Silencio 2, The Greatest Show on Earth 3), consistent with the
    per-album orders of the history; the seed's trilogy-wide `single_order` stays in `release_track` and `song`.
- *Previous and last tour* (T-46 finding 5). `prev_album_tour_*` = latest `album` tour that started before the cutoff;
  `last_tour_*` = the qualifying tour (any type except `(No tour)`, ≥ 10 shows with a setlist before the cutoff) with
  the latest last show: Sphere for 2027, so B3 shows the residency trap.
- *Other definitions.* `tours_played_share`: album tours before the cutoff whose last show is on or after the song's
  start (earlier of release and first play). `career_rate`: shows since that start. `tours_since_last_played`:
  qualifying tours whose first show is after the song's last play. `played_pre_tour`: shows after the last show of the
  last qualifying tour and before the cutoff (Carnival De Luz Promo and the Mount Temple / Bewley's sets for 2027).
  `is_new_material`: `promoted_album`, or `companion_release` whose album no earlier tour promoted (the 2026 EPs yes,
  *Songs of Innocence* on e+i no). `is_title_track` (promoted album or companion only): song key equals or contains the
  album key, or appears word-bounded in the tour name.
- *Extra columns* (for the model, ordering and checks): `is_planned_tour`, `song_title`, `album_id`, `release_date`,
  `is_original`, `prev_album_tour_name`, `last_tour_name`, `career_shows_played`, `career_avg_position`,
  `history_shows`, `history_max_date`.
- *No leakage.* `build_features` keeps only shows before the cutoff and asserts it per song; the notebook re-checks from
  the written table that `history_max_date` < cutoff and that `history_shows` equals the count of shows with a setlist
  before the cutoff (hard checks).

## 9.5 Model · `nb_silver_setlist_prediction`

Two parts, kept simple on purpose: there are only about ten comparable tours, so anything heavier overfits.

1. **Catalog songs:** logistic regression on `is_core` (fit in `u2lib`, cross-checked against the Fabric runtime's
   scikit-learn, whose version the notebook records; see the T-48 rules below), trained on every earlier album tour. Report the coefficients so the result can be
   explained on the report page.
2. **New material:**
   - *How many:* expected number of new songs per show = median `is_new_material` share per show on the previous
     album tours × expected songs per show, with the e+i tour as the reference for how much a companion release keeps.
   - *Which:* a ranked score: single (earlier `single_order` first), played live before the tour, title track, album
     over companion release; penalties for featured artist, spoken word and bonus track. Calibrate the weights on past
     album tours, where singles and pre-tour plays are known.
3. **Predicted setlist:** pick the expected number of songs per show (median of the last three album tours), with the
   predicted new-song count filled from the new-material ranking and the rest from the catalog probabilities. Order by
   predicted relative position; opener = highest `prev_opener_rate`-weighted new single (album tours since Elevation
   tend to open with new material; confirm with the data before relying on it).
4. **In-tour update** (from 2027-02-23): after each show, each song's probability becomes a Beta-binomial posterior.
   The prior mean is the pre-tour probability with strength `m` = 5 shows; the evidence is how many of the tour's shows
   so far played it. A prediction is recomputed for every `as_of_date` (the day before each show), so the history is
   reproducible from Silver and nothing has to be appended.

Output `lk_silver.dbo.setlist_prediction`: `target_tour_name`, `as_of_date`, `song_id`, `probability`,
`predicted_in_setlist`, `predicted_position`, `predicted_set` (`main`/`encore`), `model_part` (`catalog`/`new`),
`model_version`.

**Rules fixed in T-48** (code: `u2lib.prediction`, `u2lib.setlist`; all fixed before the first backtest, none tuned on
a test tour):

- *Logistic regression in `u2lib`, scikit-learn as a cross-check.* The fit is a pure-Python Newton solver of the
  objective scikit-learn's `LogisticRegression(C = 1/L2)` minimises (L2 penalty, intercept not penalised) on
  standardised features, `L2 = 1`. It is deterministic (no random state) and testable in CI, where scikit-learn is not
  installed. The notebook refits every model with the runtime's scikit-learn and logs the largest coefficient
  difference (warning above 1e-3) and `scikit_learn` in the exit value's `versions` (the version of the Fabric
  Runtime 2.0 is recorded from the first run, not assumed here). `setlist_model_coef` keeps the coefficients
  (standardised and per original unit) of every model for the report.
- *Catalog features* (rows with `is_new_material` false): `prev_album_tour_rate`, `last_tour_rate`, `career_rate`,
  `tours_played_share`, recency = 1 / (1 + `tours_since_last_played`) (0 if never played), played before the tour
  (`played_pre_tour` > 0), `is_single`. Training = feature rows of every earlier `album` tour whose last show is before
  the target's first show (asserted).
- *New material.* A second logistic regression on the new-material rows of the same training tours, features
  `is_single`, 1/`single_order`, played before the tour, `is_title_track` (this is the "calibrate the weights on past
  album tours"). Facts that never occur in the history get hand-set logit penalties: featured artist −1, spoken word
  −2, bonus track −2.
- *How many.* N = median over the last three album tours of their median played songs per show. New album songs =
  round(median of those tours' median per-show share of their promoted album × N). New companion songs (only when the
  target has new companion material, i.e. 2027) = round(e+i's median per-show share of *Songs of Innocence* × N).
  Within each group the probabilities are rescaled (capped at 1) to sum to the group's count, and the top songs by
  score fill the group's slots; the rest of the N slots go to the catalog songs with the highest probability.
- *Order.* Opener = the best-scoring new single when new material opened at least half the shows of the last three
  album tours (data: Zoo TV, PopMart, Elevation, Vertigo, i+e, e+i 100 %, U2 360° 40 %), else the catalog song with the
  highest `prev_opener_rate` × probability. Other songs by relative position: catalog songs at their
  `prev_avg_position` (else `career_avg_position`, else 0.5), new songs at the previous album tour's average position
  of its new songs, ties by score; catalog songs with `prev_encore_rate` ≥ 0.5 form the encore (`predicted_set`).
- *Rows written.* Pre-tour predictions for the planned tour **and for every backtest tour** (`is_backtest` true), so
  the data-analyst can reproduce every model metric in T-SQL; plus `shows_observed` (0 for the pre-tour row). Gold
  (T-49) keeps the planned tour's rows (`is_backtest = 0`). In-tour rows (one set per `as_of_date` = the day before
  each show after the first) have `predicted_in_setlist` = top N by posterior and no position or set. A planned tour
  whose `is_planned` flag is cleared after its first show (T-53) is named in the notebook parameter `PREDICTION_TOURS`
  so it is never backtested or trained on.
- *`model_version`* = `sl<model>-u2lib<version>` (e.g. `sl1.0-u2lib0.5.0`, ≤ 20 characters).

## 9.6 Backtest

For each album tour from Zoo TV (1992) to e+i (2018), train on the tours before it and predict as of its first show.

| Metric | Definition |
| --- | --- |
| `precision_at_n` | Share of the N predicted songs that are in the tour's core set (`is_core`) |
| `jaccard_first_show` | Overlap of the predicted setlist with the first show's actual setlist |
| `brier_play_rate` | Mean squared error of `probability` vs. `play_rate` |
| `new_count_error` | Predicted minus actual new songs per show (median) |

Baselines (same metrics): **B1** the previous album tour's core set; **B2** the N most-played songs of the career so
far; **B3** the latest tour of any type, which would be Sphere for 2027 and shows the anniversary/residency trap.
Results in `lk_silver.dbo.setlist_backtest` (tour, method, metric, value).

Exact definitions (T-48), so the T-SQL reproduction gives the same numbers:

- Every method predicts N songs, N = the model's expected songs per show for that tour. **B1** = top N by
  `prev_album_tour_rate`, **B2** = top N by `career_shows_played`, **B3** = top N by `last_tour_rate`; ties by
  `career_shows_played` descending, then `song_id` in code-point order (`COLLATE Latin1_General_100_BIN2_UTF8`). The
  baselines' probabilities for the Brier score are `prev_album_tour_rate`, `career_rate` (null = 0) and
  `last_tour_rate`.
- `precision_at_n` = predicted songs with `is_core` / N. `jaccard_first_show` = |predicted ∩ first show| / |predicted
  ∪ first show|, where the first show is the tour's earliest show with a setlist (by date, then `setlist_id`) and its
  set is every song played there (full performances, candidates or not). `brier_play_rate` = mean over the tour's
  candidate rows of (probability − `play_rate`)². `new_count_error` = predicted new songs (model: the new-song slots;
  baselines: `is_new_material` songs in their set) − the tour's median per show of promoted-album songs.
- Extra `method = 'context'` rows per tour: `songs_per_show_predicted`/`_actual`, `core_size_actual`,
  `new_per_show_predicted`/`_actual`.

## 9.7 Gold and model

| Table | Grain | Notes |
| --- | --- | --- |
| `fact_setlist_prediction` | (`as_of_date_key`, `tour_key`, `song_key`) | From `setlist_prediction`; `tour_key` of the planned tour; `probability` float, `predicted_in_setlist` bit, `predicted_position` int, `predicted_set` varchar(10), `model_part` varchar(10), `model_version` varchar(20) |
| `fact_setlist_backtest` | (`tour_key`, `method`, `metric`) | From `setlist_backtest` |
| `dim_tour` (new columns) | | `tour_type` varchar(20), `is_planned` bit, added with `ALTER TABLE` (SPEC-04 rule) |
| `dim_song` (new columns) | | `release_role_2027` varchar(30) (null for catalog), `is_single` bit |

Additive only: no existing Gold column changes, so SPEC-05 relationships stay. New measures (data-analyst, SPEC-05
conventions): `Predicted probability`, `Predicted songs`, `Hit rate` (predicted and played / predicted, for shows
already played), `Model vs. baseline` (from `fact_setlist_backtest`).

## 9.8 Report

New page **10 · Next tour** (dashboard-designer, SPEC-06 and the `u2-design-system` skill):
- Predicted setlist in order, with probability bars and new vs. catalog colour.
- New material: the 25 tracks by release (Days of Ash, Easter Lily, Carnaval de Luz) with probability.
- "How good is this?": backtest precision of the model vs. B1–B3.
- From the first show on: predicted vs. played per show, and how the probabilities move over the tour.

Charter addition (T-43): **Q12** *Which songs will the 2027 tour play, how much of the 2026 trilogy will be in it,
and how close was the prediction once the tour began?*

## 9.9 Acceptance criteria

- `bronze_seed_release_2026_tracks` has 25 rows; every `release_track` row has a `song_id` and an `album_id`.
- Every tour has a `tour_type`; the three anniversary/residency tours are not training examples (check in the notebook).
- No feature reads a show on or after its target tour's first show (asserted in the notebook).
- The model beats B1 on mean `precision_at_n` over the backtest tours from Elevation (2001) on. If it does not,
  the page shows the baseline and says so; the result is recorded either way.
- `fact_setlist_prediction` has one row per candidate song for the pre-tour `as_of_date`, and the predicted setlist
  length equals the expected songs per show.
- Backtest results and the 2027 prediction are recorded in `docs/run-log.md` with the run id and `model_version`.

## 9.10 Sources (checked 2026-10-25)

- Album, tracks, singles: [Wikipedia: Carnaval de Luz](https://en.wikipedia.org/wiki/Carnaval_de_Luz),
  [Rolling Stone](https://www.rollingstone.com/music/music-news/u2-new-album-carnaval-de-luz-interview-1235630567/),
  [U2.com](https://www.u2.com/blogs/news/carnaval-de-luz-new-album-coming-in-november)
- EPs: [Wikipedia: Days of Ash](https://en.wikipedia.org/wiki/Days_of_Ash),
  [Wikipedia: Easter Lily (EP)](https://en.wikipedia.org/wiki/Easter_Lily_(EP)),
  [Variety](https://variety.com/2026/music/news/u2-easter-lily-ep-release-1236706082/)
- Tour: [U2.com: The Greatest Show on Earth](https://www.u2.com/blogs/news/carnaval-de-luz-presents-the-greatest-show-on-earth)
- Mount Temple show: [Ultimate Classic Rock](https://ultimateclassicrock.com/u2-50th-anniversary-surprise-dublin-concert/)

## 9.11 Open questions

- Should the EP songs count as "new material" for the promoted share on the existing Q4 page, or only here?
  (Default: only here; Q4 keeps `album_promoted`.)
- `m` = 5 for the in-tour update is a starting value; tune it on the backtest tours' first ten shows.
- (T-48) The catalog probabilities are calibrated on `is_core`, not on `play_rate`: their sum for 2027 (≈ 12 for 16
  catalog slots) is below the slot count, so "expected songs per show" on the page should use N, not the sum of
  probabilities. Recalibrating on `play_rate` is a possible v2, judged on the backtest only.
- (T-48) The scikit-learn version of Fabric Runtime 2.0 is read from the first run's exit value and written into
  `docs/run-log.md`; if the runtime has no scikit-learn, the cross-check is skipped and logged (the model does not need it).

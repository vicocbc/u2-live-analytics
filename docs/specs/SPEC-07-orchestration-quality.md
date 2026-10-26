# SPEC-07 · Orchestration and data quality

Owner: data-engineer

## Pipeline `pl_refresh`

```
nb_bronze_seeds ─┐
nb_u2_load_bronze ───┼─> nb_silver_shows ─┐
nb_bronze_musicbrainz ┘   nb_silver_catalog ─┼─> nb_silver_song_map ─> nb_silver_setlist_features ─>
    nb_silver_setlist_prediction ─> [SP] wh_gold.dbo.usp_build_gold ─> [SP] usp_assert_gold ─> semantic model refresh
```

- The setlist notebooks (SPEC-09, added in T-49) read `show`, `performance`, `song_map`, `song`, `album`, `tour` and
  `release_track`, so they run after `nb_silver_song_map`; `nb_silver_setlist_prediction` refreshes the `lk_silver`
  SQL endpoint again after writing, so Gold reads its tables.

- Bronze notebooks run in parallel; MusicBrainz may run monthly instead of weekly (parameter `run_musicbrainz`).
- Gold is a **Stored procedure** activity on `wh_gold` calling `dbo.usp_build_gold` with
  `@run_id = @pipeline().RunId`, followed by a second Stored procedure activity `dbo.usp_assert_gold` (same
  `@run_id`) that fails the pipeline on a hard Gold check. Two statements because Fabric Warehouse undoes the whole
  `EXEC` when a procedure raises, which would also erase the `dq_run_log` rows (SPEC-04, T-20).
- **SQL endpoint sync:** the Warehouse reads Silver through the `lk_silver` SQL analytics endpoint, whose metadata can
  lag behind fresh Delta writes. The last cell of `nb_silver_song_map` calls the *Refresh SQL endpoint metadata*
  REST API for `lk_silver` (with `sempy.fabric.FabricRestClient`) and waits for it, so Gold always reads the run's data.
  As a guard, `usp_dq_gold` checks that `lk_silver.dbo.show` holds rows of the current `_run_id`.
- Schedule: weekly, Monday early morning (Europe/Dublin).
- On failure: the pipeline stops; the failed activity's notebook output holds the error. Email notification optional.
- Each notebook exits with `notebookutils.notebook.exit(json)` returning its key counts so the pipeline run history shows them.

## Data quality checks

Bronze and Silver: each notebook's final cells, with `u2lib.quality` (`check(name, condition, severity)`); hard
failures raise, warnings print. Gold: `dbo.usp_dq_gold` inside the build transaction; a hard failure rolls Gold back,
`usp_build_gold` logs the checks, and `usp_assert_gold` raises with `THROW`, which fails the pipeline activity.

| Layer | Check | Severity |
| --- | --- | --- |
| Bronze | row count = API total; no duplicate natural ids | hard |
| Bronze | row count change vs. previous run > 10% | warning |
| Silver | `show + show_excluded = bronze show` | hard |
| Silver | mapped share of full performances ≥ 98% | warning below 98, hard below 95 |
| Gold | no null FKs; Unknown share < 1% | hard |
| Gold | `fact_show` = `dim_show` − 1 | hard |
| Gold | surrogate keys unique and ≠ `-1` in every dimension | hard |
| Gold | `lk_silver.dbo.show` contains the current run (endpoint synced) | hard |
| Gold | setlist facts = Silver; keys resolve; one pre-tour row per candidate; predicted length = positions 1..N; 2026 tracks have `release_role_2027`; planned tours ordered last (SPEC-04, T-49) | hard |

The table `wh_gold.dbo.dq_run_log` (`run_id`, `layer`, `check_name`, `value`, `status`, `checked_at`; DDL in SPEC-04) is
appended on every run and exposed on the report's "About the data" page as the last refresh status. Notebooks write
it with `Results.write(spark)` (Fabric Spark connector for Warehouse, `synapsesql`).

## Acceptance criteria

- A full pipeline run succeeds from empty lakehouses (only seeds and secrets present).
- Breaking a rule on purpose (e.g. truncate a Bronze table) makes the pipeline fail at the right check.
- Breaking a Gold rule on purpose leaves the previous Gold rows in place (the report keeps working) and the
  failure is in `dq_run_log`.

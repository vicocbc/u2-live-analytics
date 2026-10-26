# Task board

Owners: `data-engineer`, `data-analyst`, `data-scientist`, `dashboard-designer` (Claude Code subagents) and `vini` (human steps).
Status: `todo` · `in progress` · `review` · `done`. A task starts only when everything in *Depends on* is `done`.
No git until T-40: agents push changes to the workspace (MCP / `fab`) and keep `fabric/` as the working copy.

## Phase 1 · Foundation (SPEC-01)

| Id | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| T-01 | Create workspace `U2 Live Analytics`, lakehouses `lk_bronze`/`lk_silver` (created with "Lakehouse schemas" on; tables in `dbo`, specs adjusted 2026-10-21), warehouse `wh_gold`, and the `Files/seeds` folder in `lk_bronze` (`Files/bronze` is created by the notebooks) | vini | — | done |
| T-02 | Install prerequisites (incl. `sqlcmd`), `az login --allow-no-subscriptions`, `fab auth login`, set `U2_SQL_SERVER`, start Claude Code here and approve the `.mcp.json` servers; confirm with `/mcp` (see `docs/setup.md`) | vini | T-01 | done |
| T-03 | setlist.fm key in Key Vault `kv-vini-u2`, secret `setlistfm-api-key`, readable from notebooks | vini | T-01 | done |
| T-04 | Set the capacity XMLA endpoint to *Read Write* (needed by the Power BI modeling MCP) | vini | T-01 | done |
| T-05 | Scaffold `src/u2lib` (pyproject, modules from SPEC-01 §6), tests, ruff config, `docs/run-log.md` | data-engineer | — | done |
| T-06 | Build the wheel; add "Attach u2lib to env_u2" steps to `docs/setup.md` | data-engineer | T-05 | done |
| T-07 | Create `env_u2` in Fabric, attach wheel + `rapidfuzz`, publish | vini | T-06, T-01 | done |
| T-08 | Smoke test the tooling: list items with the Fabric MCP, `fab ls`, upload a test file to `lk_bronze/Files/seeds/_smoke/` and delete it; `sqlcmd` on `wh_gold` and apply `sql/wh_gold/deploy.txt` (creates `dq_run_log`) | data-engineer | T-02 | done |

## Phase 2 · Ingestion (SPEC-02)

| Id | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| T-09 | setlist.fm Bronze: `nb_u2_load_bronze` loaded by Vini (run `20261021T114228Z`, SPEC-02 §2.1). Left: `fab export` it to `fabric/nb_u2_load_bronze.Notebook/` and confirm the default lakehouse shows as `lk_bronze` | data-engineer | T-08 | done |
| T-10 | Write, push and run `nb_bronze_musicbrainz` (SPEC-02 §2.2) | data-engineer | T-07, T-08 | done |
| T-11 | Draft `seeds/tours.csv` from the distinct `tour_name` values in `lk_bronze.dbo.bronze_setlistfm_show` and the band's tour history | data-analyst | T-08 | done |
| T-12 | Upload seeds to `lk_bronze/Files/seeds/`; write, push and run `nb_bronze_seeds` | data-engineer | T-11 | done |
| T-13 | Validate Bronze: studio album list complete, tour list complete, counts in `docs/run-log.md` | data-analyst | T-09, T-10, T-12 | done |
| T-13a | Reload seeds: upload changed `seeds/tours.csv` and new `seeds/album_overrides.csv`, rerun `nb_bronze_seeds` (expects `bronze_seed_album_overrides` 3 rows) | data-engineer | T-13 | done |

## Phase 3 · Silver (SPEC-03)

| Id | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| T-14 | `nb_silver_shows`: `show`, `show_excluded`, `performance` | data-engineer | T-13 | done |
| T-15 | `nb_silver_catalog`: `album`, `song`, `tour` | data-engineer | T-13, T-13a | done |
| T-16 | `nb_silver_song_map` with resolution order and review queries; last cell syncs the `lk_silver` SQL endpoint (SPEC-07) | data-engineer | T-14, T-15 | done |
| T-17 | Review fuzzy and unmapped songs; grow `seeds/song_alias_overrides.csv` until ≥ 98% mapped | data-analyst | T-16 | done |
| T-18 | Review cancelled-show detection and snippet flags on samples; add edge cases to `tests/` | data-analyst | T-14 | done |

## Phase 4 · Gold (SPEC-04)

| Id | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| T-19 | `wh_gold` DDL for every Gold table + `usp_build_dimensions` (Unknown members, deterministic keys) in `sql/wh_gold/`, applied with `sqlcmd` | data-engineer | T-17, T-18 | done |
| T-20 | `usp_build_facts` (`fact_performance`, `fact_show`, debut/only-performance flags) and `usp_build_gold` (one transaction) | data-engineer | T-19 | done |
| T-21 | T-SQL validation queries and the three hand-checked facts (SPEC-04 acceptance) | data-analyst | T-20 | done |

## Phase 5 · Orchestration and quality (SPEC-07)

| Id | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| T-22 | Add `u2lib.quality` checks writing to `wh_gold.dbo.dq_run_log` to every notebook; `usp_dq_gold` with rollback on hard failure | data-engineer | T-20 | done |
| T-23 | Create `pl_refresh` (notebooks → Stored procedure activity `usp_build_gold` → model refresh; definition pushed via MCP or `fab import`), run it once with `fab job run` | data-engineer | T-22 | done |
| T-24 | Set the weekly schedule; run from empty lakehouses; break-a-rule test | vini | T-23 | done |

## Phase 6 · Semantic model (SPEC-05)

| Id | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| T-25 | Create Direct Lake model `sm_u2_live` on warehouse `wh_gold` in the portal (all Gold tables + `dq_run_log`) | vini | T-20, T-04 | done |
| T-26 | Connect the Power BI modeling MCP to `sm_u2_live`; export its TMDL to `fabric/sm_u2_live.SemanticModel/` | data-analyst | T-25 | done |
| T-27 | Relationships, hiding, sort-by, date table, data categories (via MCP), then refresh the TMDL copy | data-analyst | T-26 | done |
| T-28 | Measures with formats, descriptions and display folders; DAX tests in `tests/dax/` run through the MCP | data-analyst | T-27 | done |

## Phase 7 · Report (SPEC-06)

| Id | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| T-29 | Theme JSON and wireframes for the 9 pages, with question traceability (can run in parallel with Phases 3–6) | dashboard-designer | T-13 | done |
| T-30 | Approve wireframes and theme | vini | T-29 | done |
| T-31 | In Power BI Desktop, create a report live-connected to `sm_u2_live` with one placeholder visual, save as PBIP named `rpt_u2_live` inside `fabric/`, publish to the workspace | vini | T-28, T-30 | done |
| T-32 | Build pages 1–3 in PBIR, push with `fab import` | dashboard-designer | T-31 | done |
| T-33 | Build pages 4–6 in PBIR, push | dashboard-designer | T-32 | done |
| T-34 | Build drill-through pages 7–8 and About page 9, push | dashboard-designer | T-33 | done |
| T-35 | Finding-style page titles and annotations from validated numbers | data-analyst | T-34 | done |
| T-36 | Open in Desktop, fix rendering, run accessibility checklist | vini + dashboard-designer | T-35 | done |

## Phase 8 · Portfolio (SPEC-08)

| Id | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| T-37 | Screenshots and drill-through GIF into `docs/img/` | vini | T-36 | done |
| T-38 | `docs/data-dictionary.md` from specs and TMDL descriptions | data-analyst | T-28 | done |
| T-39 | README per SPEC-08; final `fab export` of every item into `fabric/` and check `sql/wh_gold/` matches the warehouse | data-analyst + data-engineer | T-37, T-38 | done |
| T-40 | **Git, by Vini (learning task):** secrets scan, `git init`, review `.gitignore`, first commits, CI workflow (ruff + pytest), create the GitHub repo, push, make public | vini | T-39 | done |
| T-40b | **Fabric Git integration (Vini + coordinator):** connect workspace `U2 Live Analytics` to `vicocbc/u2-live-analytics`, branch `main`, folder `fabric/`, first sync workspace → Git; then align docs, `CLAUDE.md` and `scripts/pipeline.ps1` with the new flow | vini | T-40 | done |

## Optional · Popularity

| Id | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| T-41 | Spec addendum and `nb_bronze_lastfm` (track listeners/playcount) | data-engineer | T-36 | todo |
| T-42 | `fact_popularity` + measures + "Live vs. listened" visual (Q11) | data-analyst + dashboard-designer | T-41 | todo |

## Phase 9 · Setlist prediction for the 2027 tour (SPEC-09)

| Id | Task | Owner | Depends on | Status |
| --- | --- | --- | --- | --- |
| T-43 | Review `seeds/release_2026_tracks.csv` (25 tracks, singles, dates) with Vini; add `tour_type`, `is_planned` and the planned 2027 tour row to `seeds/tours.csv`; add Q12 to `docs/charter.md` | data-analyst + vini | — | done |
| T-44 | Upload the changed seeds, rerun `nb_bronze_seeds` (expects `bronze_seed_release_2026_tracks` 25 rows) | data-engineer | T-43 | done |
| T-45 | `nb_silver_catalog`: `tour.tour_type`/`is_planned`, `release_track`, `song` rows for new tracks, singles history (SPEC-09 §9.2–9.3) | data-engineer | T-44 | done |
| T-46 | Validate T-45: every new track has a `song_id` and the right release (deluxe album vs. EPs), tour types, planned tour row | data-analyst | T-45 | done |
| T-47 | `nb_silver_setlist_features` with the no-leakage assertion (SPEC-09 §9.4) | data-scientist | T-46 | in progress |
| T-48 | `nb_silver_setlist_prediction`: baselines, model, backtest, 2027 prediction; results and `model_version` in `docs/run-log.md` (SPEC-09 §9.5–9.6); data-analyst reproduces the backtest metrics with T-SQL | data-scientist + data-analyst | T-47 | todo |
| T-49 | Gold: `fact_setlist_prediction`, `fact_setlist_backtest`, new `dim_tour`/`dim_song` columns (`ALTER TABLE`), procedures, notebooks added to `pl_refresh` | data-engineer | T-48 | todo |
| T-50 | Measures for SPEC-09 §9.7 with DAX tests; refresh the TMDL copy | data-analyst | T-49 | todo |
| T-51 | Page 10 · Next tour in PBIR (SPEC-09 §9.8) | dashboard-designer | T-50 | todo |
| T-52 | Check page 10 in Power BI Desktop | vini | T-51 | todo |
| T-53 | After the first show (2027-02-23): set the exact setlist.fm `tour_name` in `seeds/tours.csv`, rerun, confirm in-tour updates and predicted vs. played | data-analyst + vini | T-52 | todo |

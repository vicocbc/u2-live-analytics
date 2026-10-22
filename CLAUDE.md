# U2 Live Analytics

Portfolio project: ~50 years of U2 concerts (setlist.fm) and discography (MusicBrainz), modelled as a
medallion architecture in Microsoft Fabric (Bronze and Silver lakehouses, Gold warehouse) and published as a
Power BI report.
Everything in this repo is in English (code, comments, docs, table and column names).

## Where things are

| Path | What |
| --- | --- |
| `docs/architecture.md` | Data flow, Fabric items, development loop, naming. Read before any build task. |
| `docs/setup.md` | How Vini installs and signs in to the MCP servers and the Fabric CLI. |
| `docs/charter.md` | Business questions the report must answer. The source of truth for "what matters". |
| `docs/specs/` | One spec per component (SPEC-01 … SPEC-08). Each task points to a spec. |
| `tasks/BOARD.md` | Task board: id, owner agent, dependencies, status. |
| `fabric/` | Local working copy of the workspace items (notebooks, pipeline, semantic model, report) in the folder layout `fab export` produces. |
| `sql/wh_gold/` | Working copy of the Gold warehouse: table DDL, stored procedures, `deploy.txt` (apply order). |
| `src/u2lib/` | Pure-Python helpers (parsing, song-name normalisation) with unit tests in `tests/`. |
| `seeds/` | Small curated CSVs (tour metadata, song alias overrides) uploaded to `lk_bronze/Files/seeds/`. |
| `.mcp.json` | MCP servers for this project (Fabric local, Fabric Core remote, Power BI modeling local). |
| `.claude/agents/` | `data-engineer`, `data-analyst`, `dashboard-designer`. |
| `.claude/skills/` | Conventions the agents load (Fabric, medallion, source APIs, TMDL, PBIR, design system). |

## Source of truth and version control

- **The Git repository is the version-controlled copy; the Fabric workspace is the running copy.** The project
  was built without git; Vini created the repository and made the first push in task T-40. The workspace is not
  connected to Fabric Git integration: `fabric/` and `sql/` are exported from it and committed like any other file.
- **Vini owns the history.** Agents may stage changes and propose a commit message, but only commit or push when
  Vini asks for it. Never rewrite published history (no force-push, no rebase of pushed commits).
- **Before editing an item, pull it; after editing, push it and confirm it changed.** Pull with `fab export` or the
  Fabric MCP definition tools; push with `fab import`. If Vini edited something in the portal, the workspace wins:
  pull first, then commit. `pl_refresh` goes through `scripts/pipeline.ps1`, which swaps the environment-specific
  values (`__U2_SQL_SERVER__`, `__U2_PBI_CONNECTION_ID__`) so they never reach the repository.
- Warehouse objects follow the same rule with `sql/wh_gold/`: change the `.sql` file, apply it with `sqlcmd`,
  confirm the object changed. If Vini edited a procedure in the portal, script it back into `sql/` first.
- A commit is ready when `fabric/` and `sql/` match the workspace for every item it touches, `ruff check .`,
  `ruff format --check .` and `pytest` pass, and no secret, API data extract or environment-specific host is in
  the diff.

## Tools for working in Fabric

| Need | Use |
| --- | --- |
| List workspaces/items, create items, read/write item definitions | Fabric Core MCP (`fabric-core`) or Fabric local MCP (`fabric`); fallback `fab export` / `fab import` |
| Upload/download lakehouse files, list tables | Fabric local MCP (`fabric`) OneLake tools; fallback `fab cp` |
| Run a notebook or pipeline and wait for the result | Fabric CLI: `fab job run` (no MCP tool runs jobs) |
| Warehouse `wh_gold`: DDL, stored procedures, T-SQL validation queries (also cross-database on `lk_silver`) | `sqlcmd` (go-sqlcmd) with `--authentication-method ActiveDirectoryDefault` against `$env:U2_SQL_SERVER`, database `wh_gold` |
| Semantic model: relationships, measures, DAX queries, best-practice checks | Power BI modeling MCP (`powerbi-modeling`) connected to `sm_u2_live` in the workspace |
| Report pages and visuals (PBIR) | Files in `fabric/rpt_u2_live.Report/` pushed with `fab import`; Vini checks in Power BI Desktop (no MCP edits reports) |

If an MCP server is missing or not signed in, say which one and point Vini to `docs/setup.md`; never ask for credentials.

## How to work

1. Pick the next task in `tasks/BOARD.md` whose dependencies are all `done`.
2. Delegate it to the agent in the `Owner` column, passing the task id and its spec.
   Tasks owned by `vini` need a human (portal clicks, sign-ins, Power BI Desktop, screenshots): stop and ask.
3. The agent works only on what its task touches, then reports what changed in the workspace and in `fabric/`,
   and how it was verified (test results, row counts, run ids).
4. Update the task's status in `tasks/BOARD.md` (`todo` → `in progress` → `review` → `done`) and add a line to
   `docs/run-log.md` with the date, task id, counts and run ids. `done` only when every acceptance criterion is met.

## Hard rules

- Never write a secret into any file or tool argument that is logged. API keys come from Azure Key Vault
  `kv-vini-u2` inside notebooks; see the `fabric-conventions` skill.
- Never download API data into this folder. Data stays in OneLake. `seeds/` holds only hand-curated reference data.
- Destructive operations (delete an item, a table, a folder, a workspace) only when Vini asks for that exact item.
- Respect source terms: setlist.fm API is free for non-commercial use only; MusicBrainz requires a descriptive
  User-Agent and at most 1 request per second. Credit both in the README and the report's "About" page.
- Bronze is a full snapshot each run; Silver is rebuilt with `overwrite` from Bronze; Gold is rebuilt by
  `wh_gold.dbo.usp_build_gold` in one transaction from Silver.
- Gold table and column names are a contract with the semantic model. Changing them requires updating
  SPEC-04 and SPEC-05 together and telling the data-analyst.

## Definition of done (every task)

- Runs end to end in the workspace, or the owner states exactly what Vini must run and what to check.
- Data quality checks pass; counts and run ids recorded in `docs/run-log.md`.
- `fabric/` holds the latest definition of every item the task touched; docs touched by the change are updated.

---
name: fabric-conventions
description: Conventions for working in the U2 Live Analytics Fabric workspace from Claude Code without git — item names, pull/edit/push loop with the Fabric MCP servers and Fabric CLI, notebook file format, reading across lakehouses, secrets, running jobs. Use whenever creating, editing or running anything in the workspace or under fabric/.
---

# Fabric conventions

## Items and names

Workspace `U2 Live Analytics`; lakehouses `lk_bronze`, `lk_silver`; warehouse `wh_gold`; environment `env_u2`;
notebooks `nb_<layer>_<subject>` (Bronze and Silver only); Gold procedures `wh_gold.dbo.usp_<verb>_<subject>`;
pipeline `pl_refresh`; semantic model `sm_u2_live`; report `rpt_u2_live`.
Full list in `docs/architecture.md`.

## The loop with Fabric Git integration

The workspace is connected to GitHub (`main`, folder `fabric/`). `fabric/` is written by Fabric; never run
`fab import` or `fab export` on items under Git (they create workspace changes that conflict with Git).

1. **Before you start:** `git pull`, and ask Vini whether *Source control* in the workspace shows pending changes or
   updates for the items you will touch.
2. **Edit in files** (`fabric/<item>.<Type>/`, or generators such as `scripts/gen_report.py`), or **edit in Fabric**
   (the Power BI modeling MCP for the model, `sqlcmd` for `wh_gold`).
3. **Hand over:**
   - file edits: propose the commit; when Vini asks, commit and push; Vini then runs *Source control → Update all*;
   - Fabric edits: Vini commits from *Source control → Changes*; then run `git pull`.
4. **Verify** in the workspace (MCP `get_item`, a DAX query, `fab job run` for notebooks) and check that `fabric/`
   after `git pull` matches what you meant to change.

New item: create it in the workspace (portal or MCP `create_item`), have Vini commit it from *Source control*,
then `git pull`. Never write a `.platform` by hand.

Flags and argument names evolve: run `fab <command> --help` the first time you use a command in a session,
and list an MCP server's tools before relying on a tool name.

## Notebook files

Use the layout Fabric Git integration writes for a notebook (`.platform` + `notebook-content.py` with
`# Fabric notebook source`, `# METADATA`, `# PARAMETERS CELL`, `# CELL`, `# MARKDOWN` markers). Copy markers and
the METADATA block (default lakehouse binding, environment) from an existing notebook in `fabric/`; never invent ids in `.platform`.

Skeleton, always in this order: markdown header (purpose, inputs, outputs) → parameters cell →
imports and `RUN_ID` → read → transform (calls into `u2lib`) → write → quality checks →
`notebookutils.notebook.exit(json.dumps(counts))`.

## Running

| Need | How |
| --- | --- |
| Run a notebook and wait | `fab job run "U2 Live Analytics.Workspace/nb_silver_shows.Notebook"` |
| Pass parameters | `fab job run ... -P name:type=value` (check `--help` for the exact syntax) |
| Run the pipeline | `fab job run "U2 Live Analytics.Workspace/pl_refresh.DataPipeline"` |
| Status of a run | `fab job run-status ...` |

The exit value of the notebook (JSON counts) is how you report results. If `fab auth status` shows you are not
signed in, ask Vini to run `fab auth login`; never handle credentials.

## Lakehouse files and tables

- Upload/download: Fabric local MCP OneLake tools (`onelake_upload_file`, `onelake_list_files`, …) or
  `fab cp ./seeds/tours.csv "U2 Live Analytics.Workspace/lk_bronze.Lakehouse/Files/seeds/"`.
- List tables: MCP `onelake_list_tables`. Query data: inside a notebook (Spark SQL) and return results in the exit value.
- Both lakehouses have "Lakehouse schemas" on; every table is in schema `dbo`. In notebooks, write to the default
  lakehouse with `saveAsTable("show")` (lands in `dbo`); read other lakehouses in the same workspace with three-part
  names: `spark.read.table("lk_bronze.dbo.bronze_setlistfm_show")`.
- Bronze table names are `bronze_<source>_<entity>`; raw JSON goes to `Files/bronze/<source>/u2/<run_id>/` (SPEC-02).

## Warehouse `wh_gold` (Gold layer)

- Source of truth on disk: `sql/wh_gold/tables/*.sql`, `sql/wh_gold/procedures/*.sql`, applied in the order of
  `sql/wh_gold/deploy.txt`. Scripts are idempotent: tables `IF OBJECT_ID('dbo.x') IS NULL CREATE TABLE ...`,
  procedures `CREATE OR ALTER PROCEDURE`. Never drop a Gold table that the semantic model uses; alter it.
- Run T-SQL with go-sqlcmd and the Azure CLI sign-in (no passwords):
  `sqlcmd -S $env:U2_SQL_SERVER -d wh_gold --authentication-method ActiveDirectoryDefault -i sql/wh_gold/procedures/usp_build_facts.sql`
  (`-Q "..."` for a one-off query). `U2_SQL_SERVER` is the workspace SQL connection string, set by Vini (`docs/setup.md`).
- Read Silver from T-SQL with three-part names: `lk_silver.dbo.show`. After Silver notebooks write, the
  `lk_silver` SQL analytics endpoint must be synced before Gold reads it (SPEC-07).
- Fabric Warehouse T-SQL limits to remember: no `nvarchar` (use `varchar`, UTF-8 collation), no recursive CTEs,
  temp tables `#x` allowed in procedures, `check` and other reserved words need brackets (avoid them as names).
- Build: `EXEC dbo.usp_build_gold @run_id = '<id>'` during development; the pipeline's Stored procedure activity in production.

## Secrets

API keys live in Azure Key Vault `https://kv-vini-u2.vault.azure.net/` (setlist.fm: secret `setlistfm-api-key`).
Same pattern as `nb_u2_load_bronze`:

```python
API_KEY_SOURCE = "keyvault"
KEY_VAULT_URL  = "https://kv-vini-u2.vault.azure.net/"
SECRET_NAME    = "setlistfm-api-key"
API_KEY_INLINE = ""            # quick manual tests only; never save it filled in

def get_api_key() -> str:
    if API_KEY_SOURCE == "keyvault":
        return notebookutils.credentials.getSecret(KEY_VAULT_URL, SECRET_NAME).strip()
    if API_KEY_SOURCE == "inline" and API_KEY_INLINE:
        return API_KEY_INLINE
    raise ValueError("Set up the key: API_KEY_SOURCE = 'keyvault', or fill in API_KEY_INLINE.")
```

Never print the key, never pass it as a job parameter, never read the secret from Claude Code. The Key Vault URL
and secret name are not secrets and may appear in files.

## Safety

Deleting items, tables, folders or the workspace only when Vini asks for that exact object. Prefer `-f`
(force overwrite) only on items you just exported in the same task.

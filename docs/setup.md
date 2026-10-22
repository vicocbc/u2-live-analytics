# Setup: MCP servers and Fabric CLI

Claude Code reaches Fabric and Power BI through three MCP servers (declared in `.mcp.json`) plus the
Fabric CLI for running jobs. All of them act with **your** Microsoft Entra identity and permissions.

Assumes Windows (Power BI Desktop and the local Power BI modeling MCP server do not run on macOS).

## 1. Prerequisites

| Tool | Why | Check |
| --- | --- | --- |
| Node.js LTS (includes `npx`) | runs both local MCP servers | `node -v`, `npx -v` |
| Azure CLI | sign-in used by the local Fabric MCP server | `az version` |
| Python 3.10–3.13 | Fabric CLI and `u2lib` tests | `python --version` |
| go-sqlcmd (`winget install sqlcmd`) | T-SQL on the Gold warehouse `wh_gold` (DDL, procedures, validation queries) | `sqlcmd --version` |
| Power BI Desktop | check the report (PBIP) and take screenshots | — |

## 2. Sign in

```powershell
az login --allow-no-subscriptions    # same account you use in Fabric; no Azure subscription needed
pip install ms-fabric-cli
fab auth login                       # interactive browser sign-in
fab ls                               # should list your workspaces
```

### SQL connection to `wh_gold`

`sqlcmd` signs in with the same `az login` (no password). It needs the workspace SQL connection string:
open `wh_gold` in the portal → **Settings → SQL endpoint** (or the ⋯ menu → *Copy SQL connection string*), then
save it as a user environment variable (it is not a secret, but keep it out of the repo):

```powershell
[Environment]::SetEnvironmentVariable("U2_SQL_SERVER", "<paste>.datawarehouse.fabric.microsoft.com", "User")
```

Open a new terminal (and restart Claude Code) so the variable is visible, then check:

```powershell
sqlcmd -S $env:U2_SQL_SERVER -d wh_gold --authentication-method ActiveDirectoryDefault -Q "SELECT DB_NAME()"
```

## 3. Workspace settings the servers need

- **Power BI modeling MCP against a Fabric model** needs the capacity's XMLA endpoint set to *Read Write*
  (capacity settings → Power BI workloads). On a trial capacity you are usually the admin; otherwise ask whoever is.
- **Hosted Power BI / Fabric MCP endpoints** may require tenant settings enabled by a Fabric admin
  (for the Power BI one: *Users can use the Power BI Model Context Protocol server endpoint*).

## 4. Start Claude Code in this folder

```powershell
cd u2-live-analytics
claude
```

Claude Code asks to approve the project servers from `.mcp.json` the first time. Then run `/mcp` and check:

| Server | Expected | If it fails |
| --- | --- | --- |
| `fabric` | connected; `onelake_list_workspaces` lists your workspace | run `az login` again; on native Windows, if `npx` is not found, change the entry to `"command": "cmd", "args": ["/c", "npx", "-y", ...]` |
| `fabric-core` | asks you to sign in in the browser, then connected | if sign-in never completes, remove it from `.mcp.json`; the `fabric` server and `fab` cover the same needs |
| `powerbi-modeling` | connected | same `cmd /c` fix as above; check XMLA *Read Write* |

Quick test prompt: *"Use the fabric MCP server to list the items in workspace U2 Live Analytics."*

## 5. Local Python: `u2lib` tests and wheel

One-time, from this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Every change to `src/u2lib/`:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest          # fails below 90% coverage
.\.venv\Scripts\python.exe -m build --wheel   # writes dist\u2lib-<version>-py3-none-any.whl
```

Bump `version` in `pyproject.toml` and `__version__` in `src/u2lib/__init__.py` before building a wheel that
replaces one already attached to `env_u2`, so notebooks can print which version they run.

## 6. Attach u2lib to env_u2

`env_u2` is the Spark environment every notebook uses. Do this the first time (T-07) and after every new wheel.

1. In the workspace `U2 Live Analytics`: **+ New item → Environment**, name `env_u2`
   (skip if it exists). Keep the default runtime (Runtime 2.0, Spark 4.1 in this workspace; `u2lib` is pure
   Python and `rapidfuzz` needs Python ≥ 3.11, so any current runtime works).
2. Open `env_u2` → **Libraries → Custom libraries → Upload** and pick `dist\u2lib-<version>-py3-none-any.whl`.
   If an older `u2lib` wheel is listed, delete it there (custom libraries are matched by file, not by package name).
3. **Libraries → External repositories → Add library** (source PyPI): `rapidfuzz`. The portal requires a version: pick the latest one offered
   (3.14.6 on 2026-10-21). The wheel requires `>=3.0`.
   Fabric does not reliably install a custom wheel's dependencies, so list it explicitly.
4. **Save**, then **Publish** and wait until the status shows the publish succeeded (several minutes).
5. Make `env_u2` the workspace default: *Workspace settings → Data Engineering/Science → Spark settings →
   Environment*, turn **Set default environment** On, pick `env_u2`, **Save**. Notebooks left on "Workspace default"
   then use it. If a notebook still raises `ModuleNotFoundError: No module named 'u2lib'`, check its toolbar
   *Environment* selector, then **Stop session** and run again (a running session keeps its old environment).
6. Check in a notebook attached to `env_u2`:

   ```python
   import u2lib
   from u2lib import geo, songs
   print(u2lib.__version__, geo.continent("IE"), songs.normalize_title("The Fly"))
   # 0.2.0 Europe fly
   ```

## 7. What each tool is for

| Need | Tool |
| --- | --- |
| Create items, read/write notebook and pipeline definitions | `fabric-core` / `fabric` MCP, or `fab export` / `fab import` |
| Upload seeds and config files to the lakehouse | `fabric` MCP OneLake tools, or `fab cp` |
| Run a notebook or the pipeline | `fab job run` (no MCP tool runs jobs today) |
| Gold warehouse tables, procedures, T-SQL checks | `sqlcmd` against `wh_gold` with files from `sql/wh_gold/` |
| Semantic model changes and DAX validation queries | `powerbi-modeling` MCP |
| Report pages | PBIR files + `fab import`; you open the `.pbip` in Power BI Desktop to check |

Tool names and command flags change between releases; when something looks different, run `fab <command> --help`
or ask Claude to list the server's tools.

## 8. Environment-specific values in `fabric/`

`fabric/` is what `fab export` produces, so it references this workspace. None of these values is a secret, but some
are tied to this environment and a fork must replace them.

**Kept out of the files (placeholders, filled at import time).** `pl_refresh` is pushed and pulled with
`scripts/pipeline.ps1`, never with plain `fab import` / `fab export`:

| Placeholder in `fabric/pl_refresh.DataPipeline/pipeline-content.json` | Value | Set with |
| --- | --- | --- |
| `__U2_SQL_SERVER__` | `wh_gold` SQL endpoint host (Stored procedure activities) | `$env:U2_SQL_SERVER` (section 2) |
| `__U2_PBI_CONNECTION_ID__` | Power BI cloud connection used by the *Refresh semantic model* activity | `$env:U2_PBI_CONNECTION_ID` |

```powershell
$env:U2_SQL_SERVER = [Environment]::GetEnvironmentVariable('U2_SQL_SERVER','User')
$env:U2_PBI_CONNECTION_ID = '<connection id from Manage connections and gateways>'
./scripts/pipeline.ps1 -Action import    # push fabric/ -> workspace
./scripts/pipeline.ps1 -Action export    # pull workspace -> fabric/ (placeholders restored)
```

**Fabric object ids kept as exported** (`fab import` needs them to bind items in this workspace; in a new workspace,
re-bind in the portal or replace them with the new ids):

| Where | Ids |
| --- | --- |
| `fabric/nb_*.Notebook/notebook-content.py` (`# META` block) | workspace id, default lakehouse id (`lk_bronze` or `lk_silver`), known lakehouses |
| `fabric/pl_refresh.DataPipeline/pipeline-content.json` | workspace id, notebook ids, `wh_gold` id, `sm_u2_live` id |
| `fabric/sm_u2_live.SemanticModel/definition/expressions.tmdl` | Direct Lake source: workspace id and `wh_gold` id |
| `fabric/rpt_u2_live.Report/definition.pbir` | `sm_u2_live` id (live connection) |
| `fabric/*/.platform` | `logicalId` (zeros or as exported; never edit by hand) |

**Personal values to review before publishing:** the default of `CONTACT` in
`fabric/nb_bronze_musicbrainz.Notebook` (MusicBrainz User-Agent contact) is an e-mail address; switch it to the GitHub
repository URL when the repo exists. `docs/run-log.md` lists item ids and run ids as a history; they identify this
workspace only.

## Sources

- Fabric MCP servers overview: https://learn.microsoft.com/en-us/rest/api/fabric/articles/mcp-servers/what-is-fabric-mcp-server
- Fabric local MCP setup: https://learn.microsoft.com/en-us/rest/api/fabric/articles/mcp-servers/pro-dev-local/get-started-local
- Fabric Core MCP tools: https://learn.microsoft.com/en-us/rest/api/fabric/articles/mcp-servers/core-remote/tools-core-mcp-server
- Power BI authoring MCP: https://learn.microsoft.com/en-us/power-bi/developer/mcp/power-bi-authoring-mcp
- Fabric CLI: https://github.com/microsoft/fabric-cli

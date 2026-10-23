# SPEC-01 · Foundation

Owner: data-engineer (library, tests, local tooling) and vini (portal setup, sign-ins)

## Goal

A Fabric workspace that Claude Code can work in through MCP servers and the Fabric CLI, three lakehouses,
a Spark environment with our helper library, and a local project folder that is ready to become a GitHub
repo at the end.

## Deliverables

1. **Fabric workspace** `U2 Live Analytics` on a Fabric capacity (trial or paid), connected to GitHub with Fabric Git integration (folder `fabric/`, added in T-40b).
2. **Lakehouses** `lk_bronze`, `lk_silver` (with "Lakehouse schemas" on, the portal default; every table lives in
   schema `dbo`, so tables are `lk_silver.dbo.<table>` both in Spark and in T-SQL) and **Warehouse** `wh_gold` (Gold layer, schema `dbo`).
3. **Folders in `lk_bronze/Files`**: `bronze/` (raw JSON, created by the notebooks) and `seeds/`.
4. **Tooling** per `docs/setup.md`: the three servers in `.mcp.json` connected (`/mcp` shows them), Fabric CLI signed in,
   `sqlcmd` (go-sqlcmd) reaching `wh_gold` with the Azure CLI sign-in, XMLA endpoint *Read Write* on the capacity
   for the Power BI modeling server.
5. **Secrets**: setlist.fm key in Azure Key Vault `https://kv-vini-u2.vault.azure.net/`, secret `setlistfm-api-key`,
   readable by Vini's identity from notebooks. Notebooks support `API_KEY_SOURCE in {"keyvault","inline"}` and
   default to `"keyvault"`.
6. **Python package** `src/u2lib/` (pyproject-based, Python 3.11) with:
   - `dates.parse_setlistfm_date(s) -> date | None` (`dd-MM-yyyy`)
   - `songs.normalize_title(s) -> str` (casefold, strip quotes/brackets/punctuation, unify `&`/`and`, collapse spaces, remove leading "the " only for matching keys)
   - `songs.is_snippet(info: str | None) -> bool`
   - `shows.is_cancelled(info: str | None) -> bool`
   - `matching.best_match(name, candidates, threshold) -> (candidate, score) | None` using `rapidfuzz`
   - `geo.continent(country_code) -> str` (ISO 3166-1 alpha-2 → continent name, static mapping in the package)
   - `quality.check(name, condition, severity, value=None)` and `quality.Results` to collect, print, log and raise (used by SPEC-07)
7. **Tests** in `tests/` with `pytest`, plus `ruff` config. (A GitHub Actions workflow is added by Vini in T-40.)
8. **Wheel** built with `python -m build` and attached to Fabric environment `env_u2` (custom library), plus `rapidfuzz` from PyPI.
9. **Project hygiene**: `.gitignore` ready for the end of the project, `LICENSE` (MIT for code), `README.md` stub, `docs/run-log.md`.

## Acceptance criteria

- `pytest` passes locally; coverage of `u2lib` ≥ 90%; `ruff check` clean.
- `import u2lib` works in a Fabric notebook attached to `env_u2`.
- From Claude Code: the Fabric MCP lists the workspace items, `fab ls` lists them too, `sqlcmd` runs `SELECT 1` on
  `wh_gold`, and the Power BI modeling MCP
  connects to a test semantic model in the workspace (can be deleted afterwards).
- No API key in any file of the project folder (`grep -ri "x-api-key" .` returns only code that sets the header from a variable).

## Out of scope

Git and CI until T-40; deployment pipelines across dev/test/prod workspaces.

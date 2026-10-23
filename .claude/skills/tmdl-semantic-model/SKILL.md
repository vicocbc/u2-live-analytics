---
name: tmdl-semantic-model
description: How to change the sm_u2_live Direct Lake semantic model through the Power BI modeling MCP server and keep its TMDL working copy current — relationships, measure conventions, DAX patterns and validation queries. Use for any semantic model or DAX work in U2 Live Analytics.
---

# Semantic model (Power BI modeling MCP + TMDL copy)

## Working mode

The model lives in the workspace. Change it **through the `powerbi-modeling` MCP server** connected to
semantic model `sm_u2_live` in workspace `U2 Live Analytics` (ask the server to connect to that model first;
it needs XMLA *Read Write*, see `docs/setup.md`).

- Use the server's tools to create/update relationships, columns properties, measures; run DAX queries; run
  best-practice checks. Prefer one batch/transaction per logical change.
- After each task, Vini commits the model from the workspace's *Source control*; then `git pull` brings the TMDL
  into `fabric/sm_u2_live.SemanticModel/definition/`.
- Editing TMDL files by hand (committed with Git, applied with *Update all*) is the fallback only when the MCP server is
  unavailable.
  Then keep tabs/ordering, never change existing lineage tags, and ask Vini to confirm the model in the portal.

## TMDL layout (for reading the copy)

`definition/`: `database.tmdl`, `model.tmdl`, `relationships.tmdl`, `expressions.tmdl` (Direct Lake source),
`tables/<table>.tmdl` (columns, measures, `///` descriptions).

## Measure conventions

```tmdl
	/// Number of real shows (cancelled shows excluded in Silver).
	measure Shows = COUNTROWS ( fact_show )
		formatString: #,0
		displayFolder: Shows
```

- Title Case names with spaces, no prefixes. One base measure per fact; others build on base measures.
- Every measure: `///` description (one sentence, what and why), `formatString`, `displayFolder`.
- Percentages `0.0%`; counts `#,0`; dates `yyyy-mm-dd`.
- Use `DIVIDE`, variables (`VAR … RETURN`), and `KEEPFILTERS`/`TREATAS` over `FILTER(ALL(...))` where possible.
- Default exclusion: `Performances` excludes snippets, tapes and fragments (SPEC-05):

```dax
Performances =
CALCULATE (
    COUNTROWS ( fact_performance ),
    KEEPFILTERS ( fact_performance[is_snippet] = FALSE () ),
    KEEPFILTERS ( fact_performance[is_tape] = FALSE () ),
    KEEPFILTERS ( fact_performance[is_fragment] = FALSE () )
)
```

- Promoted-album share pattern (tour's promoted album vs. song's album):

```dax
Promoted Album Share % =
VAR PromotedAlbums = VALUES ( dim_tour[album_promoted_key] )
VAR FromPromoted =
    CALCULATE ( [Performances], TREATAS ( PromotedAlbums, dim_album[album_key] ) )
RETURN DIVIDE ( FromPromoted, [Performances] )
```

Validate per tour: at tour grain this must equal the share computed in T-SQL on `wh_gold`.

## Model hygiene

- Hide `*_key`, `*_id` (except where used for links), audit and technical flag columns.
- Sort-by columns per SPEC-05; mark `dim_date` as date table; set data categories on geography columns.
- Single-direction relationships only; no bidirectional filters; no fact-to-fact relationships.

## Validation

For each measure, save a DAX query in `tests/dax/<measure>.dax` with an `EVALUATE SUMMARIZECOLUMNS(...)` for a
fixed context and the expected value in a comment, cross-checked with a T-SQL query on `wh_gold` (`sqlcmd`).

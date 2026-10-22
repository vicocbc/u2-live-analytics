---
name: medallion-conventions
description: Rules for Bronze, Silver and Gold tables in U2 Live Analytics — what each layer may contain, naming, keys, audit columns, idempotency and data quality checks. Use when designing, building or validating any table in lk_bronze, lk_silver or the wh_gold warehouse.
---

# Medallion conventions

## Layer responsibilities

| Layer | May | Must not |
| --- | --- | --- |
| Bronze | Store values as delivered (strings OK), flatten JSON, add audit columns | Clean, deduplicate across sources, apply business rules |
| Silver | Type, trim, deduplicate, remove cancelled shows, derive flags, map songs to ids, finish anything that needs Python (`u2lib`: continents, song keys) | Aggregate, create surrogate keys, rename for presentation |
| Gold (`wh_gold`, T-SQL) | Surrogate keys, star schema, precomputed helper columns for sorting/flags | Hold raw text that needs cleaning; contain logic the model cannot explain; need Python |

## Naming

`snake_case`; singular entity names; `fact_`/`dim_` only in Gold; booleans `is_`/`has_`; dates `_date`;
surrogate keys `_key`; natural ids `_id`. Audit columns: `_run_id`, `_ingested_at` (Bronze), `_built_at` (Silver/Gold).

## Idempotency

- Bronze and Silver tables are rebuilt with `overwrite` from the layer below. Re-running a notebook with the same
  inputs gives the same rows.
- Gold is rebuilt by `wh_gold.dbo.usp_build_gold`: `DELETE` + `INSERT` of every Gold table inside one transaction,
  committed only if no hard check failed. Same Silver in, same Gold out.
- Surrogate keys are deterministic:
  `CAST(HASHBYTES('SHA2_256', CAST(natural_id AS varchar(400))) AS bigint)`. Unknown member key = `-1`.
- No `MERGE`, no `append` except `dq_run_log`.

## Data quality pattern

Notebooks (Bronze, Silver):

```python
from u2lib.quality import Results
dq = Results(run_id=RUN_ID, layer="silver")
dq.check("show_reconciles", n_show + n_excluded == n_bronze, "hard", value=n_show)
dq.check("mapped_share", mapped_share >= 0.98, "warning", value=mapped_share)
dq.write(spark)   # appends to wh_gold.dbo.dq_run_log through the Spark connector for Warehouse
dq.raise_on_hard_failures()
```

Gold: `dbo.usp_dq_gold` writes the same columns to `#dq` inside the build transaction; `usp_build_gold` appends
them to `dq_run_log` after commit or rollback and `THROW`s on a hard failure.

Log every check with its value, pass or fail. Hard failures stop the pipeline.

## Validation habits (analyst and engineer)

- Reconcile counts layer to layer and write the numbers in `docs/run-log.md`.
- Spot-check three real shows against their setlist.fm pages after any change to parsing or mapping.
- When a rule removes rows, keep them somewhere inspectable (`show_excluded`, `song_map` with `match_method = 'unmapped'`).

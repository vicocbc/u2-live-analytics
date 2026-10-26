# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "b4dc6bd7-5a22-48be-b2ed-e3f8ef65be4c",
# META       "default_lakehouse_name": "lk_silver",
# META       "default_lakehouse_workspace_id": "884603d0-6049-4208-afa7-00dbe334e819",
# META       "known_lakehouses": [
# META         {
# META           "id": "b4dc6bd7-5a22-48be-b2ed-e3f8ef65be4c"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # U2 · Silver · setlist prediction
# # Baselines, model, backtest and the 2027 prediction (SPEC-09 §9.5–9.6). Runs after `nb_silver_setlist_features`.
# # **Model** (`u2lib.prediction`, pure Python, deterministic): catalog songs = L2 logistic regression on `is_core`
# (the objective of scikit-learn's `LogisticRegression(C=1/L2)`, cross-checked below against the runtime's
# scikit-learn); new material = logistic regression on the new songs of past album tours (single, single order,
# played before the tour, title track) plus hand-set penalties for featured artist, spoken word and bonus track;
# how many new songs = median share on the last three album tours (companion EPs: e+i's share of Songs of Innocence).
# # **Backtest**: every album tour from Zoo TV to e+i, trained only on earlier album tours that ended before its first
# show; baselines B1 (previous album tour), B2 (career most played), B3 (latest tour of any type).
# # **Inputs** (`lk_silver.dbo`): `setlist_feature`, plus `show`, `performance` + `song_map`, `song`, `album`, `tour`,
# `release_track` for the tour profiles. **Outputs** (overwrite, `lk_silver.dbo`): `setlist_prediction`,
# `setlist_backtest`, `setlist_model_coef`; then the `lk_silver` SQL endpoint is synced (SPEC-07).

# PARAMETERS CELL ********************

RUN_ID   = ""            # empty = generated from the current UTC time (pipeline passes its run id)
WRITE_DQ = True          # append checks to wh_gold.dbo.dq_run_log
SYNC_SQL_ENDPOINT = True # refresh lk_silver SQL endpoint metadata after writing (SPEC-07)
SILVER_LAKEHOUSE  = "lk_silver"

# Same values as nb_silver_setlist_features.
PLANNED_FIRST_SHOW = {"Carnaval De Luz Presents: The Greatest Show On Earth World Tour": "2027-02-23"}
COMPANION_RELEASES = {"eXPERIENCE + iNNOCENCE Tour": ["Songs of Innocence"]}
# Tours to predict once setlist.fm publishes their shows and is_planned is cleared (T-53): add the tour name here.
PREDICTION_TOURS = []

BACKTEST_FROM = "Zoo TV"                              # first backtest tour (SPEC-09 §9.6)
ACCEPT_FROM = "Elevation"                             # acceptance: model beats B1 on mean precision_at_n from here
COMPANION_REFERENCE = "eXPERIENCE + iNNOCENCE Tour"   # how much of a companion release a tour keeps
EXPECTED_BACKTEST_TOURS = ["Zoo TV", "Popmart Tour", "Elevation", "Vertigo", "U2 360°",
                           "iNNOCENCE + eXPERIENCE Tour", "eXPERIENCE + iNNOCENCE Tour"]
L2 = 1.0                                              # = scikit-learn C 1.0; fixed before the backtest, never tuned
SKLEARN_TOLERANCE = 1e-3                              # max |coefficient difference| u2lib vs scikit-learn

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import dataclasses
import json
import platform
import statistics
import time
import datetime as dt
from collections import defaultdict

import pyspark
from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType, BooleanType, DateType, DoubleType,
                               TimestampType)

import u2lib
from u2lib import prediction, setlist
from u2lib.quality import Results

try:
    import sklearn
    from sklearn.linear_model import LogisticRegression
    SKLEARN_VERSION = sklearn.__version__
except ImportError:            # the cross-check is skipped and logged
    SKLEARN_VERSION = None

RUN_TS = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
RUN_ID = RUN_ID or RUN_TS.strftime("%Y%m%dT%H%M%SZ")
MODEL_VERSION = prediction.model_version(u2lib.__version__)
VERSIONS = {"python": platform.python_version(), "pyspark": pyspark.__version__, "u2lib": u2lib.__version__,
            "scikit_learn": SKLEARN_VERSION}
print("Run:", RUN_ID, "| model_version", MODEL_VERSION, "|", VERSIONS)


def silver(table: str):
    return spark.read.table(f"dbo.`{table}`")


def collect(df) -> list[dict]:
    return [r.asDict() for r in df.collect()]

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 1. Read Silver

# CELL ********************

feature_rows = collect(silver("setlist_feature").drop("_run_id", "_built_at"))
feature_run_id = silver("setlist_feature").select("_run_id").first()["_run_id"]
show_rows = collect(silver("show").filter("has_setlist").select("setlist_id", "event_date", "tour_name"))
perf_rows = collect(
    silver("performance").alias("p")
    .join(silver("song_map").alias("m"),
          (F.col("p.song_key") == F.col("m.song_key"))
          & (F.coalesce(F.col("p.cover_artist"), F.lit("")) == F.coalesce(F.col("m.cover_artist"), F.lit(""))),
          "left")
    .select("p.setlist_id", "p.setlist_position", "p.is_encore", "p.is_tape", "p.is_snippet", "m.song_id"))
song_rows = collect(silver("song"))
album_rows = collect(silver("album"))
tour_rows = collect(silver("tour"))
release_track_rows = collect(silver("release_track"))
print(f"feature rows {len(feature_rows)} (features run {feature_run_id}) | shows {len(show_rows)} "
      f"| performances {len(perf_rows)}")

planned_first_show = {k: dt.date.fromisoformat(v) for k, v in PLANNED_FIRST_SHOW.items()}
inp = setlist.prepare_inputs(show_rows, perf_rows, song_rows, album_rows, tour_rows, release_track_rows,
                             planned_first_show, COMPANION_RELEASES)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2. Backtest and prediction (u2lib)

# CELL ********************

res = setlist.backtest_and_predict(feature_rows, inp.tours, inp.shows, inp.songs, inp.companions, BACKTEST_FROM,
                                   COMPANION_REFERENCE, MODEL_VERSION, L2, PREDICTION_TOURS)
title = {s.song_id: s.title for s in inp.songs.values()}
tour_by_name = {t.name: t for t in inp.tours}

metrics = defaultdict(lambda: defaultdict(dict))        # tour -> metric -> method -> value
for r in res.backtest:
    metrics[r["target_tour_name"]][r["metric"]][r["method"]] = r["value"]
backtest_tours = [t for t in res.tour_predictions if t in metrics]
accept_start = tour_by_name[ACCEPT_FROM].first_show_date
accept_tours = [t for t in backtest_tours if tour_by_name[t].first_show_date >= accept_start]
METHODS = ("model", "B1", "B2", "B3")
METRICS = ("precision_at_n", "jaccard_first_show", "brier_play_rate", "new_count_error")
means = {m: {k: statistics.mean(metrics[t][m][k] for t in accept_tours) for k in METHODS} for m in METRICS}
for m in METRICS:
    print(f"\n{m}\n{'tour':34s}" + "".join(f"{k:>9s}" for k in METHODS))
    for t in backtest_tours:
        print(f"{t[:34]:34s}" + "".join(f"{metrics[t][m][k]:9.3f}" for k in METHODS))
    print(f"{'mean from ' + ACCEPT_FROM:34s}" + "".join(f"{means[m][k]:9.3f}" for k in METHODS))

prediction_names = [t for t in res.tour_predictions if t not in metrics]
for name in prediction_names:
    pred = res.tour_predictions[name]
    print(f"\n{name}: {pred.expectation}")
    for r in sorted((r for r in pred.rows if r["predicted_in_setlist"]), key=lambda r: r["predicted_position"]):
        print(f"{r['predicted_position']:3d} {r['predicted_set']:7s} {r['model_part']:8s} {r['probability']:.3f}  "
              f"{title[r['song_id']]}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 3. Cross-check against scikit-learn
# Refits every catalog and new-material model with the runtime's `LogisticRegression` on the same standardised
# features and compares the coefficients. A difference above `SKLEARN_TOLERANCE` is a warning, not a failure: the
# written numbers always come from `u2lib`, so a rerun gives the same values whatever the runtime.

# CELL ********************

sk_diffs = {}
if SKLEARN_VERSION:
    rows_by_tour = defaultdict(list)
    for r in feature_rows:
        rows_by_tour[r["target_tour_name"]].append(r)
    for name, pred in res.tour_predictions.items():
        training = [r for t in res.training_tours[name] for r in rows_by_tour[t]]
        for part, model, feats in (("catalog", pred.catalog_model, prediction.CATALOG_FEATURES),
                                   ("new", pred.new_model, prediction.NEW_FEATURES)):
            if model is None:
                continue
            rows = [r for r in training if bool(r["is_new_material"]) == (part == "new")]
            active = [j for j, sd in enumerate(model.scales) if sd]
            x = [[(v[j] - model.means[j]) / model.scales[j] for j in active] for v in prediction.design(rows, feats)]
            y = [int(bool(r["is_core"])) for r in rows]
            try:
                sk = LogisticRegression(C=1.0 / L2, tol=1e-10, max_iter=10000).fit(x, y)
            except ValueError as e:                  # e.g. one class only: nothing to compare
                print(f"{name} / {part}: scikit-learn fit skipped ({e})")
                continue
            ours = [model.intercept] + [model.coefs[j] for j in active]
            theirs = [float(sk.intercept_[0])] + [float(c) for c in sk.coef_[0]]
            sk_diffs[f"{name} / {part}"] = max(abs(a - b) for a, b in zip(ours, theirs))
    print("max |coef u2lib - scikit-learn|:", {k: round(v, 6) for k, v in sk_diffs.items()})
else:
    print("scikit-learn not available in this runtime: cross-check skipped")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4. Write `setlist_prediction`, `setlist_backtest`, `setlist_model_coef`

# CELL ********************

S, I, B, D, X = StringType(), IntegerType(), BooleanType(), DateType(), DoubleType()
SCHEMAS = {
    "setlist_prediction": StructType([
        StructField("target_tour_name", S), StructField("as_of_date", D), StructField("shows_observed", I),
        StructField("song_id", S), StructField("probability", X), StructField("predicted_in_setlist", B),
        StructField("predicted_position", I), StructField("predicted_set", S), StructField("model_part", S),
        StructField("is_backtest", B), StructField("model_version", S)]),
    "setlist_backtest": StructType([
        StructField("target_tour_name", S), StructField("method", S), StructField("metric", S),
        StructField("value", X), StructField("model_version", S)]),
    "setlist_model_coef": StructType([
        StructField("target_tour_name", S), StructField("model_part", S), StructField("feature", S),
        StructField("coef_standardized", X), StructField("coef_raw", X), StructField("n_train", I),
        StructField("n_positive", I), StructField("model_version", S)]),
}
rows_by_table = {"setlist_prediction": res.predictions, "setlist_backtest": res.backtest,
                 "setlist_model_coef": res.coefs}


def typed(rows: list[dict], schema: StructType) -> list[dict]:
    """Keep the schema's columns; ints in double columns become floats (Spark does not cast them)."""
    doubles = {f.name for f in schema.fields if isinstance(f.dataType, DoubleType)}
    return [{f.name: (float(r[f.name]) if f.name in doubles and r[f.name] is not None else r[f.name])
             for f in schema.fields} for r in rows]


dfs, counts = {}, {}
for table, rows in rows_by_table.items():
    df = (spark.createDataFrame(typed(rows, SCHEMAS[table]), schema=SCHEMAS[table])
          .withColumn("_run_id", F.lit(RUN_ID))
          .withColumn("_built_at", F.lit(RUN_TS).cast(TimestampType())))
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"dbo.{table}")
    dfs[table] = silver(table)
    counts[table] = dfs[table].count()
    print(f"lk_silver.dbo.{table}: {counts[table]} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 5. Data quality checks

# CELL ********************

dq = Results(run_id=RUN_ID, layer="silver")
pred_df = dfs["setlist_prediction"]

dq.check("setlist_backtest_tours_expected", backtest_tours == EXPECTED_BACKTEST_TOURS, "hard",
         value="; ".join(backtest_tours))
train_types = {tour_by_name[u].tour_type for names in res.training_tours.values() for u in names}
dq.check("setlist_training_album_tours_only", train_types == {"album"}, "hard", value=",".join(sorted(train_types)))
in_training = sorted({u for names in res.training_tours.values() for u in names} & set(prediction_names))
dq.check("setlist_prediction_tours_never_trained_on", not in_training, "hard", value="; ".join(in_training) or None)
dq.check("setlist_prediction_tour_present", len(prediction_names) >= 1, "hard", value="; ".join(prediction_names))

features_per_tour = defaultdict(int)
for r in feature_rows:
    features_per_tour[r["target_tour_name"]] += 1
pre = (pred_df.filter("shows_observed = 0").groupBy("target_tour_name")
       .agg(F.count("*").alias("rows"), F.countDistinct("song_id").alias("songs"),
            F.sum(F.col("predicted_in_setlist").cast("int")).alias("picked"),
            F.countDistinct("predicted_position").alias("positions"), F.max("predicted_position").alias("max_pos"))
       .collect())
bad_rows, bad_len = [], []
for r in pre:
    n = res.tour_predictions[r.target_tour_name].expectation.songs_per_show
    if not (r.rows == r.songs == features_per_tour[r.target_tour_name]):
        bad_rows.append(f"{r.target_tour_name}: {r.rows} rows, {r.songs} songs, "
                        f"{features_per_tour[r.target_tour_name]} candidates")
    if not (r.picked == r.positions == r.max_pos == n):
        bad_len.append(f"{r.target_tour_name}: picked {r.picked}, positions {r.positions}, expected {n}")
dq.check("setlist_prediction_one_row_per_candidate", not bad_rows and len(pre) == len(res.tour_predictions), "hard",
         value="; ".join(bad_rows) or len(pre))
dq.check("setlist_prediction_length_equals_expected_songs", not bad_len, "hard", value="; ".join(bad_len) or len(pre))
n_bad_prob = pred_df.filter("probability IS NULL OR probability < 0 OR probability > 1").count()
dq.check("setlist_prediction_probability_in_range", n_bad_prob == 0, "hard", value=n_bad_prob)
n_dup = counts["setlist_prediction"] - pred_df.select("target_tour_name", "as_of_date", "song_id").distinct().count()
dq.check("setlist_prediction_no_dup_grain", n_dup == 0, "hard", value=n_dup)
n_metrics_null = dfs["setlist_backtest"].filter("value IS NULL").count()
dq.check("setlist_backtest_values_present", n_metrics_null == 0, "hard", value=n_metrics_null)

beats_b1 = means["precision_at_n"]["model"] > means["precision_at_n"]["B1"]
dq.check("setlist_model_beats_b1_precision_from_elevation", beats_b1, "warning",
         value=f"model {means['precision_at_n']['model']:.3f} vs B1 {means['precision_at_n']['B1']:.3f}")
sk_worst = max(sk_diffs.values()) if sk_diffs else None
dq.check("setlist_logistic_matches_sklearn", sk_worst is not None and sk_worst <= SKLEARN_TOLERANCE, "warning",
         value=f"{sk_worst:.2e} (scikit-learn {SKLEARN_VERSION})" if sk_worst is not None else "skipped")

# wh_gold.dbo.dq_run_log.value is varchar(200): longer values (failure lists) keep their first 200 characters
dq.results = [dataclasses.replace(r, value=str(r.value)[:200]) if len(str(r.value)) > 200 else r for r in dq.results]
if WRITE_DQ:
    dq.write(spark)
dq.raise_on_hard_failures()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 6. Sync the `lk_silver` SQL analytics endpoint
# So `wh_gold` (T-49) and the data-analyst's T-SQL reproduction read this run's tables (same code as
# `nb_silver_song_map`).

# CELL ********************

sync_tables, sync_failures = None, []
if SYNC_SQL_ENDPOINT:
    import sempy.fabric as fabric

    client = fabric.FabricRestClient()
    workspace_id = notebookutils.runtime.context["currentWorkspaceId"]
    lakehouses = client.get(f"/v1/workspaces/{workspace_id}/lakehouses").json()["value"]
    lakehouse = next(lh for lh in lakehouses if lh["displayName"] == SILVER_LAKEHOUSE)
    sql_endpoint_id = lakehouse["properties"]["sqlEndpointProperties"]["id"]

    resp = client.post(f"/v1/workspaces/{workspace_id}/sqlEndpoints/{sql_endpoint_id}/refreshMetadata", json={})
    if resp.status_code == 202:                       # long-running operation: poll until it finishes
        location = resp.headers["Location"].split("api.fabric.microsoft.com")[-1]
        for _ in range(60):
            time.sleep(int(resp.headers.get("Retry-After", 5)))
            state = client.get(location).json()
            if state.get("status") in ("Succeeded", "Failed"):
                break
        if state.get("status") != "Succeeded":
            raise RuntimeError(f"SQL endpoint refresh did not succeed: {state}")
        result = client.get(location.rstrip("/") + "/result").json()
    else:
        resp.raise_for_status()
        result = resp.json()
    statuses = result.get("value", [])
    sync_tables = len(statuses)
    sync_failures = [s["tableName"] for s in statuses if s.get("status") == "Failure"]
    if sync_failures:
        raise RuntimeError(f"SQL endpoint sync failed for {sync_failures}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

predictions_out = {}
for name in prediction_names:
    pred = res.tour_predictions[name]
    chosen = sorted((r for r in pred.rows if r["predicted_in_setlist"]), key=lambda r: r["predicted_position"])
    predictions_out[name] = {
        "as_of_date": str(tour_by_name[name].first_show_date - dt.timedelta(days=1)),
        "expected_songs_per_show": pred.expectation.songs_per_show,
        "new_songs_predicted": pred.details["n_new_predicted"],
        "new_album": pred.expectation.n_new_album, "new_companion": pred.expectation.n_new_companion,
        "sum_probability": round(sum(r["probability"] for r in pred.rows), 2),
        "sum_probability_new": round(sum(r["probability"] for r in pred.rows if r["model_part"] == "new"), 2),
        "setlist": [[r["predicted_position"], title[r["song_id"]], round(r["probability"], 3), r["model_part"],
                     r["predicted_set"]] for r in chosen],
        "coefficients": {f"{c['model_part']}.{c['feature']}": round(c["coef_raw"], 3)
                         for c in res.coefs if c["target_tour_name"] == name},
    }
exit_value = {
    "run_id": RUN_ID, "model_version": MODEL_VERSION, "features_run_id": feature_run_id, "versions": VERSIONS,
    **counts,
    "backtest": {t: {m: {k: round(metrics[t][m][k], 3) for k in METHODS} for m in METRICS} for t in backtest_tours},
    "mean_from_" + ACCEPT_FROM: {m: {k: round(v, 3) for k, v in means[m].items()} for m in METRICS},
    "model_beats_b1": beats_b1,
    "sklearn_max_coef_diff": sk_worst,
    "predictions": predictions_out,
    "sql_endpoint_tables_synced": sync_tables,
    **dq.summary(),
}
print(json.dumps(exit_value, indent=2, ensure_ascii=False, default=str))
notebookutils.notebook.exit(json.dumps(exit_value, ensure_ascii=False, default=str))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

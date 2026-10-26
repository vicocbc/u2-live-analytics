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

# # U2 · Silver · setlist features
# # Builds `setlist_feature` for the 2027 setlist prediction (SPEC-09 §9.4): one row per (candidate song, target tour).
# Targets: every `album` tour that has a previous album tour (October … e+i; Zoo TV … e+i are the backtest tours, the
# earlier ones only train) plus the planned tour. Every feature of a target uses only shows dated before its first
# show; `u2lib.features.assert_no_leakage` raises on a violation and the checks below verify it again from the table.
# # **Inputs** (`lk_silver.dbo`): `show` (with a setlist), `performance` joined to `song_map`, `song`, `album`, `tour`,
# `release_track`. "Played" = full performance: no tape, no snippet, no fragment (SPEC-05).
# # **Output** (overwrite): `lk_silver.dbo.setlist_feature`. Logic lives in `u2lib.features` and `u2lib.setlist`
# (unit-tested); this notebook only reads, calls them, writes and checks.

# PARAMETERS CELL ********************

RUN_ID   = ""            # empty = generated from the current UTC time (pipeline passes its run id)
WRITE_DQ = True          # append checks to wh_gold.dbo.dq_run_log

# Planned tours have no shows in Silver: announced first show (SPEC-09 §9.1). Key = tour.tour_name.
PLANNED_FIRST_SHOW = {"Carnaval De Luz Presents: The Greatest Show On Earth World Tour": "2027-02-23"}
# Companion releases per tour (SPEC-09 §9.4 release_role). A planned tour also gets every release_track release
# that is not its promoted album (the 2026 EPs Days of Ash and Easter Lily).
COMPANION_RELEASES = {"eXPERIENCE + iNNOCENCE Tour": ["Songs of Innocence"]}
EXPECTED_BACKTEST_TOURS = ["Zoo TV", "Popmart Tour", "Elevation", "Vertigo", "U2 360°",
                           "iNNOCENCE + eXPERIENCE Tour", "eXPERIENCE + iNNOCENCE Tour"]
EXPECTED_LAST_TOUR_2027 = "U2:UV Achtung Baby Live at Sphere"   # B3 for 2027 (SPEC-09 §9.6)
EXPECTED_NEW_TRACKS = 25                                       # release_track rows (SPEC-09 §9.2)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import json
import datetime as dt
from collections import Counter

from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType, BooleanType, DateType, DoubleType,
                               TimestampType)

import u2lib
from u2lib import setlist
from u2lib.quality import Results

RUN_TS = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
RUN_ID = RUN_ID or RUN_TS.strftime("%Y%m%dT%H%M%SZ")
print("Run:", RUN_ID, "| u2lib", u2lib.__version__)


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

show_df = silver("show").filter("has_setlist").select("setlist_id", "event_date", "tour_name")
perf_df = (silver("performance").alias("p")
           .join(silver("song_map").alias("m"),
                 (F.col("p.song_key") == F.col("m.song_key"))
                 & (F.coalesce(F.col("p.cover_artist"), F.lit("")) == F.coalesce(F.col("m.cover_artist"), F.lit(""))),
                 "left")
           .select("p.setlist_id", "p.setlist_position", "p.is_encore", "p.is_tape", "p.is_snippet", "m.song_id"))
show_rows = collect(show_df)
perf_rows = collect(perf_df)
song_rows = collect(silver("song"))
album_rows = collect(silver("album"))
tour_rows = collect(silver("tour"))
release_track_rows = collect(silver("release_track"))
n_perf_silver = silver("performance").count()
print(f"shows with a setlist {len(show_rows)} | performances {len(perf_rows)} (Silver {n_perf_silver}) "
      f"| songs {len(song_rows)} | albums {len(album_rows)} | tours {len(tour_rows)} "
      f"| release tracks {len(release_track_rows)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2. Features (u2lib)
# `prepare_inputs` builds shows with their full performances, tours (planned first show from the parameter), songs
# (2026 tracks take release and date from `release_track`) and companion releases. `feature_table` builds every
# target's rows and raises `LeakageError` if any feature reads a show on or after the target's first show.

# CELL ********************

planned_first_show = {k: dt.date.fromisoformat(v) for k, v in PLANNED_FIRST_SHOW.items()}
inp = setlist.prepare_inputs(show_rows, perf_rows, song_rows, album_rows, tour_rows, release_track_rows,
                             planned_first_show, COMPANION_RELEASES)
feature_rows, leakage = setlist.feature_table(inp.tours, inp.shows, inp.songs, inp.album_titles, inp.album_release,
                                              inp.companions)
targets = setlist.target_tours(inp.tours)
for name, c in leakage.items():
    print(f"{name}: cutoff {c['cutoff']} | latest history show {c['history_max_date']} | rows {c['rows']} "
          f"| type {c['tour_type']}{' | planned' if c['is_planned'] else ''}")
print("Companion releases:", {t: sorted(inp.album_titles[a] for a in ids) for t, ids in inp.companions.items()})

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 3. Write `setlist_feature`

# CELL ********************

S, I, B, D, X = StringType(), IntegerType(), BooleanType(), DateType(), DoubleType()
FEATURE_SCHEMA = StructType([
    StructField("target_tour_name", S), StructField("target_first_show_date", D), StructField("is_planned_tour", B),
    StructField("song_id", S), StructField("song_title", S), StructField("album_id", S),
    StructField("release_date", D), StructField("is_original", B),
    StructField("prev_album_tour_name", S), StructField("prev_album_tour_rate", X),
    StructField("last_tour_name", S), StructField("last_tour_type", S), StructField("last_tour_rate", X),
    StructField("tours_played_share", X), StructField("career_rate", X), StructField("career_shows_played", I),
    StructField("tours_since_last_played", I), StructField("played_pre_tour", I),
    StructField("is_new_material", B), StructField("release_role", S), StructField("days_release_to_tour", I),
    StructField("is_single", B), StructField("single_order", I), StructField("is_title_track", B),
    StructField("has_featured_artist", B), StructField("is_spoken_word", B), StructField("is_bonus_track", B),
    StructField("prev_avg_position", X), StructField("prev_encore_rate", X), StructField("prev_opener_rate", X),
    StructField("career_avg_position", X), StructField("history_shows", I), StructField("history_max_date", D),
    StructField("play_rate", X), StructField("is_core", B), StructField("in_first_show", B),
])


def typed(rows: list[dict], schema: StructType) -> list[dict]:
    """Keep the schema's columns; ints in double columns become floats (Spark does not cast them)."""
    doubles = {f.name for f in schema.fields if isinstance(f.dataType, DoubleType)}
    return [{f.name: (float(r[f.name]) if f.name in doubles and r[f.name] is not None else r[f.name])
             for f in schema.fields} for r in rows]


df = (spark.createDataFrame(typed(feature_rows, FEATURE_SCHEMA), schema=FEATURE_SCHEMA)
      .withColumn("_run_id", F.lit(RUN_ID))
      .withColumn("_built_at", F.lit(RUN_TS).cast(TimestampType())))
df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("dbo.setlist_feature")
feat = silver("setlist_feature")
n_feat = feat.count()
print(f"lk_silver.dbo.setlist_feature: {n_feat} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4. Data quality checks
# The leakage check is repeated from the written table: for every target, the number of history shows a feature
# row reports must equal the number of shows with a setlist dated before the target's first show, and the latest
# history date must be before it.

# CELL ********************

dq = Results(run_id=RUN_ID, layer="silver")
tour_by_name = {t.name: t for t in inp.tours}
per_target = {r.target_tour_name: r for r in feat.groupBy("target_tour_name").agg(
    F.count("*").alias("rows"), F.max("history_max_date").alias("history_max_date"),
    F.min("history_shows").alias("hist_min"), F.max("history_shows").alias("hist_max"),
    F.min("target_first_show_date").alias("cutoff")).collect()}

leaks, bad_history = [], []
for name, r in per_target.items():
    if r.history_max_date is not None and r.history_max_date >= r.cutoff:
        leaks.append(f"{name}: {r.history_max_date} >= {r.cutoff}")
    shows_before = show_df.filter(F.col("event_date") < F.lit(r.cutoff)).count()
    if not (r.hist_min == r.hist_max == shows_before):
        bad_history.append(f"{name}: rows say {r.hist_min}-{r.hist_max}, Silver has {shows_before}")
dq.check("setlist_feature_no_leakage", not leaks, "hard", value="; ".join(leaks) or len(per_target))
dq.check("setlist_feature_history_matches_shows_before_cutoff", not bad_history, "hard",
         value="; ".join(bad_history) or len(per_target))

target_types = Counter(tour_by_name[n].tour_type for n in per_target)
dq.check("setlist_feature_targets_album_only", set(target_types) == {"album"}, "hard", value=json.dumps(target_types))
excluded = sorted(t.name for t in inp.tours if t.tour_type in ("anniversary", "residency"))
dq.check("setlist_feature_anniversary_residency_not_targets", not (set(excluded) & set(per_target)), "hard",
         value="; ".join(excluded))
missing_backtest = sorted(set(EXPECTED_BACKTEST_TOURS) - set(per_target))
dq.check("setlist_feature_backtest_tours_present", not missing_backtest, "hard",
         value="; ".join(missing_backtest) or len(EXPECTED_BACKTEST_TOURS))
planned = [t.name for t in targets if t.is_planned]
dq.check("setlist_feature_planned_tour_present", len(planned) >= 1, "hard", value="; ".join(planned) or None)
n_dup = n_feat - feat.select("target_tour_name", "song_id").distinct().count()
dq.check("setlist_feature_no_dup_song_per_tour", n_dup == 0, "hard", value=n_dup)

planned_df = feat.filter("is_planned_tour")
n_planned_targets = planned_df.filter("play_rate IS NOT NULL OR is_core IS NOT NULL OR in_first_show IS NOT NULL").count()
dq.check("setlist_feature_planned_has_no_targets", n_planned_targets == 0, "hard", value=n_planned_targets)
n_backtest_null = feat.filter("NOT is_planned_tour AND (play_rate IS NULL OR is_core IS NULL)").count()
dq.check("setlist_feature_backtest_targets_filled", n_backtest_null == 0, "hard", value=n_backtest_null)

new_ids = {r["song_id"] for r in release_track_rows}
planned_new = {r.song_id for r in planned_df.filter("is_new_material").select("song_id").collect()}
dq.check("setlist_feature_2026_tracks_are_new_material",
         planned_new == new_ids and len(new_ids) == EXPECTED_NEW_TRACKS, "hard",
         value=f"{len(planned_new & new_ids)}/{EXPECTED_NEW_TRACKS}")
last_2027 = sorted({r.last_tour_name for r in planned_df.select("last_tour_name").distinct().collect()})
dq.check("setlist_feature_2027_last_tour_is_sphere", last_2027 == [EXPECTED_LAST_TOUR_2027], "warning",
         value="; ".join(str(x) for x in last_2027))
n_rates_bad = feat.filter("prev_album_tour_rate < 0 OR prev_album_tour_rate > 1 OR last_tour_rate < 0 "
                          "OR last_tour_rate > 1 OR career_rate < 0 OR career_rate > 1 "
                          "OR play_rate < 0 OR play_rate > 1").count()
dq.check("setlist_feature_rates_in_range", n_rates_bad == 0, "hard", value=n_rates_bad)
late_singles = feat.filter("is_single AND song_title IN ('Red Hill Mining Town', 'Running to Stand Still')").count()
dq.check("setlist_feature_reissue_singles_not_singles", late_singles == 0, "hard", value=late_singles)
core_by_tour = {r.target_tour_name: r.n for r in feat.filter("is_core").groupBy("target_tour_name")
                .agg(F.count("*").alias("n")).collect()}
dq.check("setlist_feature_core_set_sizes", True, "warning", value=json.dumps(core_by_tour, ensure_ascii=False))

if WRITE_DQ:
    dq.write(spark)
dq.raise_on_hard_failures()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

exit_value = {
    "run_id": RUN_ID, "u2lib": u2lib.__version__, "setlist_feature": n_feat,
    "targets": len(per_target), "backtest_tours": len(EXPECTED_BACKTEST_TOURS), "planned_tours": planned,
    "rows_per_target": {n: r.rows for n, r in per_target.items()},
    "planned_new_material": len(planned_new), "last_tour_2027": last_2027,
    **dq.summary(),
}
print(json.dumps(exit_value, indent=2, ensure_ascii=False, default=str))
notebookutils.notebook.exit(json.dumps(exit_value, ensure_ascii=False, default=str))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

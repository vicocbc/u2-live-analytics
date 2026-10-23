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
# META         },
# META         {
# META           "id": "806086d9-e835-4b86-859e-8597701bb0c8"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # U2 · Silver · shows
# # Builds `show`, `show_excluded` and `performance` in `lk_silver` from the setlist.fm Bronze tables (SPEC-03 §3.1).
# # **Inputs**: `lk_bronze.dbo.bronze_setlistfm_show`, `lk_bronze.dbo.bronze_setlistfm_performance`,
# `lk_bronze.dbo.bronze_seed_show_exclusions` (manual exclusions; take precedence over the info-text rule).
# # **Outputs** (overwrite, schema `dbo` of the default lakehouse `lk_silver`):
# - `show`: real shows (cancelled/postponed removed), `tour_name` `(No tour)` when setlist.fm has none, continent from `u2lib.geo`.
# - `show_excluded`: removed setlists with the reason (kept for inspection).
# - `performance`: songs played at real shows; empty names dropped; snippet, cover, encore, opener and closer flags.
# # Rules from `u2lib`: `shows.exclusion_reason`, `songs.normalize_title`, `songs.is_snippet`, `geo.continent`.
# Same-day shows at the same venue are real (early/late shows), so no automatic `duplicate` exclusion; known
# duplicates are listed in `seeds/show_exclusions.csv`.

# PARAMETERS CELL ********************

RUN_ID   = ""            # empty = generated from the current UTC time (pipeline passes its run id)
WRITE_DQ = True          # append checks to wh_gold.dbo.dq_run_log
NO_TOUR  = "(No tour)"   # tour_name for shows without a setlist.fm tour (SPEC-03 §3.2)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import json
import datetime as dt

from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType, BooleanType, DoubleType,
                               DateType, TimestampType)

import u2lib
from u2lib import geo, shows, songs
from u2lib.quality import Results

RUN_TS = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
RUN_ID = RUN_ID or RUN_TS.strftime("%Y%m%dT%H%M%SZ")
print("Run:", RUN_ID, "| u2lib", u2lib.__version__)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 1. Read Bronze

# CELL ********************

b_show = [r.asDict() for r in spark.read.table("lk_bronze.dbo.bronze_setlistfm_show").collect()]
b_perf = [r.asDict() for r in spark.read.table("lk_bronze.dbo.bronze_setlistfm_performance").collect()]
manual_exclusions = {r["setlist_id"].strip(): r["reason"].strip().lower() for r in
                     spark.read.table("lk_bronze.dbo.bronze_seed_show_exclusions").collect()
                     if r["setlist_id"] and r["reason"]}
EXCLUSION_REASONS = {"cancelled", "postponed", "duplicate"}
print("Manual exclusions:", manual_exclusions)
bronze_run_ids = sorted({r["_run_id"] for r in b_show})
print(f"Bronze shows {len(b_show)} | performances {len(b_perf)} | Bronze run {bronze_run_ids}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2. Transform

# CELL ********************

def clean(s):
    """Trim; empty string becomes None."""
    if s is None:
        return None
    s = str(s).strip()
    return s or None


show_rows, excluded_rows = [], []
for s in b_show:
    reason = manual_exclusions.get(s["setlist_id"]) or shows.exclusion_reason(s["show_info"])
    if reason:
        excluded_rows.append({
            "setlist_id": s["setlist_id"], "event_date": s["event_date"], "reason": reason,
            "venue_name": clean(s["venue_name"]), "city_name": clean(s["city_name"]),
            "song_count": s["song_count"], "show_info": clean(s["show_info"]),
        })
        continue
    country_code = clean(s["country_code"])
    show_rows.append({
        "setlist_id": s["setlist_id"],
        "event_date": s["event_date"],
        "tour_name": clean(s["tour_name"]) or NO_TOUR,
        "venue_id": clean(s["venue_id"]),
        "venue_name": clean(s["venue_name"]),
        "city_name": clean(s["city_name"]),
        "state_code": clean(s["state_code"]),
        "country_code": country_code,
        "country_name": clean(s["country_name"]),
        "continent": geo.continent(country_code),
        "latitude": s["latitude"],
        "longitude": s["longitude"],
        "song_count": s["song_count"],
        "has_setlist": (s["song_count"] or 0) > 0,
        "show_info": clean(s["show_info"]),
        "setlist_url": clean(s["setlist_url"]),
    })

real_ids = {s["setlist_id"] for s in show_rows}
excluded_ids = {s["setlist_id"] for s in excluded_rows}

perf_rows, n_empty_name, n_excluded_show_perf = [], 0, 0
for p in b_perf:
    if p["setlist_id"] in excluded_ids:
        n_excluded_show_perf += 1
        continue
    name = clean(p["song_name"])
    if not name:
        n_empty_name += 1
        continue
    info = clean(p["song_info"])
    cover_artist = clean(p["cover_artist"])
    perf_rows.append({
        "setlist_id": p["setlist_id"],
        "event_date": p["event_date"],
        "set_name": p["set_name"],
        "is_encore": p["encore_number"] is not None,
        "encore_number": p["encore_number"],
        "setlist_position": p["setlist_position"],
        "song_name_raw": name,
        "song_key": songs.normalize_title(name),
        "song_info": info,
        "is_tape": bool(p["is_tape"]),
        "is_snippet": songs.is_snippet(info),
        "is_cover": cover_artist is not None,
        "cover_artist": cover_artist,
        "with_artist": clean(p["with_artist"]),
    })

# Opener = first non-tape song of the show, closer = last non-tape song (tape intros/outros do not count).
first_pos, last_pos = {}, {}
for p in perf_rows:
    if p["is_tape"]:
        continue
    sid, pos = p["setlist_id"], p["setlist_position"]
    first_pos[sid] = min(pos, first_pos.get(sid, pos))
    last_pos[sid] = max(pos, last_pos.get(sid, pos))
for p in perf_rows:
    p["is_opener"] = not p["is_tape"] and first_pos.get(p["setlist_id"]) == p["setlist_position"]
    p["is_closer"] = not p["is_tape"] and last_pos.get(p["setlist_id"]) == p["setlist_position"]

print(f"show {len(show_rows)} | show_excluded {len(excluded_rows)} | performance {len(perf_rows)} "
      f"| dropped empty names {n_empty_name} | performances of excluded shows {n_excluded_show_perf}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 3. Write Silver tables

# CELL ********************

S, I, B, D = StringType(), IntegerType(), BooleanType(), DateType()
schemas = {
    "show": StructType([
        StructField("setlist_id", S), StructField("event_date", D), StructField("tour_name", S),
        StructField("venue_id", S), StructField("venue_name", S), StructField("city_name", S),
        StructField("state_code", S), StructField("country_code", S), StructField("country_name", S),
        StructField("continent", S), StructField("latitude", DoubleType()), StructField("longitude", DoubleType()),
        StructField("song_count", I), StructField("has_setlist", B), StructField("show_info", S),
        StructField("setlist_url", S)]),
    "show_excluded": StructType([
        StructField("setlist_id", S), StructField("event_date", D), StructField("reason", S),
        StructField("venue_name", S), StructField("city_name", S), StructField("song_count", I),
        StructField("show_info", S)]),
    "performance": StructType([
        StructField("setlist_id", S), StructField("event_date", D), StructField("set_name", S),
        StructField("is_encore", B), StructField("encore_number", I), StructField("setlist_position", I),
        StructField("song_name_raw", S), StructField("song_key", S), StructField("song_info", S),
        StructField("is_tape", B), StructField("is_snippet", B), StructField("is_cover", B),
        StructField("cover_artist", S), StructField("with_artist", S), StructField("is_opener", B),
        StructField("is_closer", B)]),
}
rows_by_table = {"show": show_rows, "show_excluded": excluded_rows, "performance": perf_rows}

dfs = {}
for table, rows in rows_by_table.items():
    df = (spark.createDataFrame(rows, schema=schemas[table])
          .withColumn("_run_id", F.lit(RUN_ID))
          .withColumn("_built_at", F.lit(RUN_TS).cast(TimestampType())))
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"dbo.`{table}`")
    dfs[table] = spark.read.table(f"dbo.`{table}`")
    print(f"lk_silver.dbo.{table}: {dfs[table].count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4. Data quality checks

# CELL ********************

dq = Results(run_id=RUN_ID, layer="silver")
n_show, n_excl, n_perf = (dfs[t].count() for t in ("show", "show_excluded", "performance"))

dq.check("show_reconciles_bronze", n_show + n_excl == len(b_show), "hard", value=f"{n_show}+{n_excl}={len(b_show)}")
dq.check("show_no_dup_id", n_show == dfs["show"].select("setlist_id").distinct().count(), "hard")
dq.check("performance_reconciles_bronze", n_perf + n_empty_name + n_excluded_show_perf == len(b_perf), "hard",
         value=f"{n_perf}+{n_empty_name}+{n_excluded_show_perf}={len(b_perf)}")
dq.check("performance_no_dup_position",
         n_perf == dfs["performance"].select("setlist_id", "setlist_position").distinct().count(), "hard")
orphans = dfs["performance"].join(dfs["show"], "setlist_id", "left_anti").count()
dq.check("performance_show_exists", orphans == 0, "hard", value=orphans)
shows_with_songs = len(first_pos)
dq.check("one_opener_per_show", dfs["performance"].filter("is_opener").count() == shows_with_songs, "hard",
         value=shows_with_songs)
dq.check("one_closer_per_show", dfs["performance"].filter("is_closer").count() == shows_with_songs, "hard",
         value=shows_with_songs)
unknown_continent = dfs["show"].filter(f"continent = '{geo.UNKNOWN}'").count()
dq.check("show_continent_known", unknown_continent == 0, "warning", value=unknown_continent)
dq.check("show_excluded_count", True, "warning", value=n_excl)          # logged for review (T-18)
bad_reasons = sorted(set(manual_exclusions.values()) - EXCLUSION_REASONS)
dq.check("show_exclusions_seed_reasons_valid", not bad_reasons, "hard", value=",".join(bad_reasons) or None)
bronze_ids = {s["setlist_id"] for s in b_show}
unknown_ids = sorted(set(manual_exclusions) - bronze_ids)
dq.check("show_exclusions_seed_ids_in_bronze", not unknown_ids, "warning", value=",".join(unknown_ids) or None)
dq.check("performance_empty_name_dropped", True, "warning", value=n_empty_name)
n_snippet = dfs["performance"].filter("is_snippet").count()
dq.check("performance_snippets", True, "warning", value=n_snippet)

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
    "run_id": RUN_ID, "bronze_run_id": ",".join(bronze_run_ids),
    "bronze_show": len(b_show), "show": n_show, "show_excluded": n_excl,
    "bronze_performance": len(b_perf), "performance": n_perf, "dropped_empty_name": n_empty_name,
    "dropped_excluded_show": n_excluded_show_perf, "snippets": n_snippet,
    "no_tour_shows": dfs["show"].filter(f"tour_name = '{NO_TOUR}'").count(),
    **dq.summary(),
}
print(json.dumps(exit_value, indent=2))
notebookutils.notebook.exit(json.dumps(exit_value))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

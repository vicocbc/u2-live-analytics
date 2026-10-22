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

# # U2 · Silver · song map
# # Maps every song played live to a `song_id` (SPEC-03 §3.3) and then syncs the `lk_silver` SQL analytics endpoint so
# the Gold build reads this run's data (SPEC-07).
# # **Inputs**: `lk_silver.dbo.performance`, `lk_silver.dbo.song` (from `nb_silver_shows` and `nb_silver_catalog`),
# `lk_bronze.dbo.bronze_seed_song_alias_overrides`.
# # **Output** `lk_silver.dbo.song_map`, one row per (`song_key`, `cover_artist`) seen in `performance`
# (`cover_artist` null for U2 songs). Gold joins `performance` on `song_key` and `ISNULL(cover_artist, '')`.
# # Resolution order, first hit wins (`match_method`): `override` (seed; `original` → `u2:<song key>`; `ignore` rows get `match_method = 'ignore'`
# and no `song_id`) → `exact` (normalised name = normalised U2 work title) → `fuzzy` (`u2lib.matching.best_match`,
# threshold `FUZZY_THRESHOLD`) → `cover` (synthetic `cover:<song key>:<artist key>`) → `unmapped`.
# # Review queries for the data-analyst: `sql/review/song_map_review.sql` (run with `sqlcmd` on `wh_gold`).

# PARAMETERS CELL ********************

RUN_ID          = ""     # empty = generated from the current UTC time (pipeline passes its run id)
WRITE_DQ        = True   # append checks to wh_gold.dbo.dq_run_log
FUZZY_THRESHOLD = 92
SYNC_SQL_ENDPOINT = True # refresh lk_silver SQL endpoint metadata after writing (SPEC-07)
SILVER_LAKEHOUSE  = "lk_silver"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import json
import time
import datetime as dt
from collections import Counter, defaultdict

from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType, DoubleType, TimestampType)

import u2lib
from u2lib import matching, songs
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

# ## 1. Read

# CELL ********************

perf = [r.asDict() for r in spark.read.table("dbo.performance")
        .select("song_key", "song_name_raw", "cover_artist", "is_tape", "is_snippet").collect()]
song = [r.asDict() for r in spark.read.table("dbo.song").collect()]
overrides = [r.asDict() for r in spark.read.table("lk_bronze.dbo.bronze_seed_song_alias_overrides").collect()]
print(f"performances {len(perf)} | songs {len(song)} | overrides {len(overrides)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2. Resolve

# CELL ********************

def clean(s):
    if s is None:
        return None
    s = str(s).strip()
    return s or None


song_by_id = {s["song_id"]: s for s in song}
# Match targets: every MusicBrainz work (original or played as a cover), not the synthetic u2:/cover: songs.
works = [s for s in song if not s["song_id"].startswith(("u2:", "cover:"))]


def original_rank(s):
    """Tie-break when several U2 works share a normalised title: has a studio first album, earliest year, id."""
    return (s["first_album_id"] is None, s["first_release_year"] or 9999, s["song_id"])


works_by_key = defaultdict(list)
for s in works:
    works_by_key[songs.normalize_title(s["title"])].append(s)
work_keys = sorted(k for k in works_by_key if k)

override_by_key = {}
for o in overrides:
    key = songs.normalize_title(o["song_name"])
    target = clean(o["work_id"])
    if key and target:
        override_by_key[key] = target.lower() if target.lower() in ("ignore", "original") else target

# Group performances by (song_key, cover_artist).
groups = defaultdict(lambda: {"names": Counter(), "performances": 0, "full_performances": 0})
for p in perf:
    g = groups[(p["song_key"], clean(p["cover_artist"]))]
    g["names"][p["song_name_raw"]] += 1
    g["performances"] += 1
    if not p["is_tape"] and not p["is_snippet"]:
        g["full_performances"] += 1

fuzzy_cache = {}
map_rows = []
for (key, cover_artist), g in groups.items():
    song_id, method, score, matched_title, candidates = None, "unmapped", None, None, None
    if key in override_by_key:
        target = override_by_key[key]
        if target == "ignore":
            method = "ignore"
        else:
            song_id = f"u2:{key}" if target == "original" else target   # "original": synthetic U2 song (§3.2)
            method, score = "override", 100.0
            matched_title = (song_by_id.get(song_id) or {}).get("title")
    elif key in works_by_key:
        hits = sorted(works_by_key[key], key=original_rank)
        song_id, method, score, matched_title, candidates = hits[0]["song_id"], "exact", 100.0, hits[0]["title"], len(hits)
    else:
        if key not in fuzzy_cache:
            fuzzy_cache[key] = matching.best_match(key, work_keys, FUZZY_THRESHOLD)
        best = fuzzy_cache[key]
        if best:
            hits = sorted(works_by_key[best[0]], key=original_rank)
            song_id, method, score, matched_title, candidates = hits[0]["song_id"], "fuzzy", best[1], hits[0]["title"], len(hits)
        elif cover_artist:
            song_id = f"cover:{key}:{songs.normalize_title(cover_artist)}"
            method, matched_title = "cover", (song_by_id.get(song_id) or {}).get("title")
    map_rows.append({
        "song_key": key,
        "cover_artist": cover_artist,
        "song_name_example": g["names"].most_common(1)[0][0],
        "song_id": song_id,
        "match_method": method,
        "match_score": score,
        "matched_title": matched_title,
        "match_candidates": candidates,
        "performances": g["performances"],
        "full_performances": g["full_performances"],
    })

by_method = Counter(r["match_method"] for r in map_rows)
print("song_map rows by method:", dict(by_method))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 3. Write

# CELL ********************

S, I = StringType(), IntegerType()
schema = StructType([
    StructField("song_key", S), StructField("cover_artist", S), StructField("song_name_example", S),
    StructField("song_id", S), StructField("match_method", S), StructField("match_score", DoubleType()),
    StructField("matched_title", S), StructField("match_candidates", I), StructField("performances", I),
    StructField("full_performances", I)])
df = (spark.createDataFrame(map_rows, schema=schema)
      .withColumn("_run_id", F.lit(RUN_ID))
      .withColumn("_built_at", F.lit(RUN_TS).cast(TimestampType())))
df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("dbo.song_map")
df_map = spark.read.table("dbo.song_map")
print("lk_silver.dbo.song_map:", df_map.count(), "rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4. Sync the lk_silver SQL analytics endpoint (SPEC-07)
# # All Silver tables of this run are written at this point. Gold reads Silver through the SQL endpoint, whose
# metadata can lag behind Delta writes, so refresh it and wait for the result.

# CELL ********************

sync_failures, sync_tables = [], 0
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
    for s in statuses:
        print(f"  {s['tableName']}: {s.get('status')}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 5. Data quality checks

# CELL ********************

dq = Results(run_id=RUN_ID, layer="silver")
n_map = df_map.count()

dq.check("song_map_no_dup_key", n_map == df_map.select("song_key", "cover_artist").distinct().count(), "hard")
dq.check("song_map_covers_all_performances", sum(r["performances"] for r in map_rows) == len(perf), "hard",
         value=len(perf))
missing_ids = sorted({r["song_id"] for r in map_rows if r["song_id"] and r["song_id"] not in song_by_id})
dq.check("song_map_song_ids_exist", not missing_ids, "hard", value=",".join(missing_ids[:20]) or None)
below = [r["song_key"] for r in map_rows if r["match_method"] == "fuzzy" and r["match_score"] < FUZZY_THRESHOLD]
dq.check("song_map_no_fuzzy_below_threshold", not below, "hard", value=len(below))
# nb_silver_catalog replicates this resolution to set song.is_original; both must agree (SPEC-03 §3.2).
COVER_TAG_EXCEPTIONS = {"a5a40c84-5e06-3249-ac20-360fac47dfc0", "4004dfec-990d-35e8-899a-32d76450e96c",
                        "c2f945b8-c4a3-3044-b55e-95aab187644d", "69985e91-92dd-3af4-81d0-f4f7ea259982"}
work_ids = {s["song_id"] for s in works}
covered_works = {r["song_id"] for r in map_rows if r["cover_artist"] and r["song_id"] in work_ids}
non_original = {s["song_id"] for s in works if not s["is_original"]}
mismatch = sorted((covered_works - COVER_TAG_EXCEPTIONS) ^ non_original)
dq.check("song_is_original_consistent_with_map", not mismatch, "hard", value=",".join(mismatch[:20]) or len(non_original))

full = sum(r["full_performances"] for r in map_rows if r["match_method"] != "ignore")
mapped = sum(r["full_performances"] for r in map_rows if r["match_method"] != "ignore" and r["song_id"])
share = mapped / full if full else 0.0
dq.check("mapped_share_ge_98", share >= 0.98, "warning", value=round(share, 4))
dq.check("mapped_share_ge_95", share >= 0.95, "hard", value=round(share, 4))
dq.check("song_map_fuzzy_to_review", True, "warning", value=by_method.get("fuzzy", 0))
unmapped_3 = sum(1 for r in map_rows if r["match_method"] == "unmapped" and r["performances"] >= 3)
dq.check("song_map_unmapped_ge3_to_review", True, "warning", value=unmapped_3)
if SYNC_SQL_ENDPOINT:
    dq.check("lk_silver_sql_endpoint_synced", not sync_failures, "hard",
             value=",".join(sync_failures) or sync_tables)

if WRITE_DQ:
    dq.write(spark)

exit_value = {
    "run_id": RUN_ID, "song_map": n_map, **{f"method_{k}": v for k, v in sorted(by_method.items())},
    "full_performances": full, "mapped_full_performances": mapped, "mapped_share": round(share, 4),
    "unmapped_keys_ge3": unmapped_3, "non_original_works": len(non_original), "sql_endpoint_tables_synced": sync_tables, **dq.summary(),
}
print(json.dumps(exit_value, indent=2))
dq.raise_on_hard_failures()
notebookutils.notebook.exit(json.dumps(exit_value))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

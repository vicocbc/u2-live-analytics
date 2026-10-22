# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "806086d9-e835-4b86-859e-8597701bb0c8",
# META       "default_lakehouse_name": "lk_bronze",
# META       "default_lakehouse_workspace_id": "884603d0-6049-4208-afa7-00dbe334e819",
# META       "known_lakehouses": [
# META         {
# META           "id": "806086d9-e835-4b86-859e-8597701bb0c8"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # U2 · Bronze · MusicBrainz
# Ingests U2's discography from the MusicBrainz API into `lk_bronze` (SPEC-02 §2.2).
# **Steps**
# 1. Browse release groups of the artist (`type=album|single|ep`, 100 per page).
# 2. Browse the official releases of each release group and keep the earliest one.
# 3. Look up each kept release with recordings and the works they perform.
# 4. Browse U2 works directly (fallback for songs not reached through a kept release).
# **Outputs** (full snapshot, `overwrite`): `bronze_musicbrainz_release_group`, `bronze_musicbrainz_release`,
# `bronze_musicbrainz_track`, `bronze_musicbrainz_recording_work`, `bronze_musicbrainz_work`.
# Raw JSON of every response in `Files/bronze/musicbrainz/u2/<run_id>/`.
# **Source terms**: no key; descriptive `User-Agent` mandatory; at most 1 request per second (enforced below).
# MusicBrainz core data is CC0; credit MusicBrainz in the README and the report.

# PARAMETERS CELL ********************

ARTIST_NAME = "U2"
ARTIST_MBID = "a3cb23fc-acd3-4ce0-8f36-1e5aa6a18432"   # validated against /artist/{mbid} below

APP_NAME    = "U2LiveAnalytics"
APP_VERSION = "0.1"
CONTACT     = "https://github.com/vicocbc/u2-live-analytics"   # MusicBrainz User-Agent contact (project repository)

RELEASE_GROUP_TYPES = "album|single|ep"
MIN_INTERVAL_SECONDS = 1.1     # MusicBrainz allows an average of 1 request/second
MAX_RETRIES   = 5
PAGE_LIMIT    = 100            # browse page size (MusicBrainz max)
MAX_RELEASE_GROUPS = None      # None = all; small number for a quick test

RAW_FOLDER   = "Files/bronze/musicbrainz/u2"
TABLE_PREFIX = "bronze_musicbrainz"
RUN_ID       = ""              # empty = generated from the current UTC time
WRITE_DQ     = True            # append checks to wh_gold.dbo.dq_run_log

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import json
import time
import datetime as dt

import requests
from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType, LongType, TimestampType)

import u2lib
from u2lib.quality import Results

BASE_URL = "https://musicbrainz.org/ws/2"
RUN_TS = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
RUN_ID = RUN_ID or RUN_TS.strftime("%Y%m%dT%H%M%SZ")
RUN_FOLDER = f"{RAW_FOLDER}/{RUN_ID}"
print("Run:", RUN_ID, "| u2lib", u2lib.__version__)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 1. HTTP client (rate limited, raw JSON saved before parsing)

# CELL ********************

session = requests.Session()
session.headers.update({
    "User-Agent": f"{APP_NAME}/{APP_VERSION} ( {CONTACT} )",
    "Accept": "application/json",
})

_last_call = [0.0]
n_calls = [0]


def mb_get(path: str, params: dict | None = None, raw_name: str | None = None) -> dict:
    """GET with >= MIN_INTERVAL_SECONDS between requests and backoff on 503/429/5xx.

    Saves the JSON to RUN_FOLDER/raw_name before returning it. Returns {} on 404.
    """
    url = f"{BASE_URL}/{path}"
    params = {**(params or {}), "fmt": "json"}
    for attempt in range(1, MAX_RETRIES + 1):
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
        n_calls[0] += 1
        try:
            resp = session.get(url, params=params, timeout=30)
        except requests.RequestException as exc:
            backoff = 2 ** attempt
            print(f"  {type(exc).__name__} on {path} (attempt {attempt}); waiting {backoff}s")
            time.sleep(backoff)
            continue
        if resp.status_code == 200:
            data = resp.json()
            if raw_name:
                notebookutils.fs.put(f"{RUN_FOLDER}/{raw_name}", json.dumps(data, ensure_ascii=False), True)
            return data
        if resp.status_code == 404:
            return {}
        if resp.status_code in (429, 503) or resp.status_code >= 500:
            retry_after = resp.headers.get("Retry-After", "")
            backoff = int(retry_after) if retry_after.isdigit() else 2 ** attempt
            print(f"  {resp.status_code} on {path} (attempt {attempt}); waiting {backoff}s")
            time.sleep(backoff)
            continue
        resp.raise_for_status()
    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {url} {params}")


def browse_all(entity: str, params: dict, list_key: str, count_key: str, raw_prefix: str) -> tuple[list[dict], int]:
    """Browse an entity page by page (limit/offset). Returns (items, API count)."""
    items, offset, page, total = [], 0, 1, None
    while True:
        data = mb_get(entity, {**params, "limit": PAGE_LIMIT, "offset": offset},
                      raw_name=f"{raw_prefix}_page_{page:04d}.json")
        batch = data.get(list_key) or []
        if total is None:
            total = data.get(count_key, 0)
        items.extend(batch)
        offset += len(batch)
        if not batch or offset >= total:
            return items, total
        page += 1

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2. Validate the artist

# CELL ********************

artist = mb_get(f"artist/{ARTIST_MBID}", raw_name="artist.json")
print(artist.get("name"), "|", artist.get("disambiguation", ""), "|", artist.get("country"))
assert artist.get("name", "").lower() == ARTIST_NAME.lower(), "MBID does not match the expected artist"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 3. Release groups, releases, tracks, works

# CELL ********************

# Step 1: release groups
release_groups, api_rg_total = browse_all(
    "release-group", {"artist": ARTIST_MBID, "type": RELEASE_GROUP_TYPES},
    "release-groups", "release-group-count", "release_group/release_group")
print(f"Release groups: {len(release_groups)} (API count {api_rg_total})")
if MAX_RELEASE_GROUPS:
    release_groups = release_groups[:MAX_RELEASE_GROUPS]

# Countries preferred among releases sharing the earliest date (worldwide, Europe, band's home markets).
COUNTRY_RANK = {"XW": 0, "XE": 1, "IE": 2, "GB": 3, "US": 4}


def earliest_release(releases: list[dict]) -> dict | None:
    """Earliest official release; ties broken by country preference, then release id (deterministic)."""
    if not releases:
        return None
    return min(releases, key=lambda r: (r.get("date") or "9999", COUNTRY_RANK.get(r.get("country"), 9), r["id"]))


# Step 2: official releases of each release group, keep the earliest
kept_releases, rg_without_release = [], []
for i, rg in enumerate(release_groups, start=1):
    releases, _ = browse_all("release", {"release-group": rg["id"], "status": "official"},
                             "releases", "release-count", f"release/{rg['id']}")
    kept = earliest_release(releases)
    if kept:
        kept_releases.append({**kept, "_release_group_id": rg["id"], "_official_release_count": len(releases)})
    else:
        rg_without_release.append(rg["id"])
    if i % 10 == 0 or i == len(release_groups):
        print(f"  releases browsed: {i}/{len(release_groups)} (calls so far {n_calls[0]})")
print(f"Kept releases: {len(kept_releases)} | release groups without an official release: {len(rg_without_release)}")

# Step 3: tracks, recordings and performed works of each kept release
release_details = []
for i, rel in enumerate(kept_releases, start=1):
    detail = mb_get(f"release/{rel['id']}",
                    {"inc": "recordings+recording-level-rels+work-rels+artist-credits"},
                    raw_name=f"release_lookup/{rel['id']}.json")
    if detail:
        release_details.append(detail)
    if i % 10 == 0 or i == len(kept_releases):
        print(f"  releases looked up: {i}/{len(kept_releases)} (calls so far {n_calls[0]})")

# Step 4: works by the artist (fallback list)
works_browsed, api_work_total = browse_all("work", {"artist": ARTIST_MBID}, "works", "work-count", "work/work")
print(f"Works browsed: {len(works_browsed)} (API count {api_work_total}) | total API calls: {n_calls[0]}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4. Flatten into rows

# CELL ********************

def credit_text(credits: list[dict] | None) -> str | None:
    if not credits:
        return None
    return "".join(f"{c.get('name') or (c.get('artist') or {}).get('name', '')}{c.get('joinphrase', '')}" for c in credits)


def work_row(w: dict, found_via: str) -> dict:
    languages = w.get("languages") or []
    return {
        "work_id": w.get("id"),
        "title": w.get("title"),
        "type": w.get("type"),
        "language": w.get("language") or (",".join(languages) if languages else None),
        "disambiguation": w.get("disambiguation") or None,
        "found_via": found_via,
    }


rg_rows = [{
    "release_group_id": rg.get("id"),
    "title": rg.get("title"),
    "primary_type": rg.get("primary-type"),
    "secondary_types": ",".join(rg.get("secondary-types") or []) or None,
    "first_release_date": rg.get("first-release-date") or None,
    "disambiguation": rg.get("disambiguation") or None,
} for rg in release_groups]

release_rows = [{
    "release_id": r.get("id"),
    "release_group_id": r["_release_group_id"],
    "title": r.get("title"),
    "date": r.get("date") or None,
    "country": r.get("country"),
    "status": r.get("status"),
    "disambiguation": r.get("disambiguation") or None,
    "official_release_count": r["_official_release_count"],
} for r in kept_releases]

track_rows, rec_work_rows, works_from_rels = [], [], {}
for rel in release_details:
    for medium in rel.get("media") or []:
        for t in medium.get("tracks") or []:
            rec = t.get("recording") or {}
            track_rows.append({
                "release_id": rel.get("id"),
                "medium_position": medium.get("position"),
                "medium_format": medium.get("format"),
                "track_position": t.get("position"),
                "track_number": t.get("number"),
                "track_title": t.get("title"),
                "recording_id": rec.get("id"),
                "recording_title": rec.get("title"),
                "length_ms": t.get("length") if t.get("length") is not None else rec.get("length"),
                "artist_credit": credit_text(t.get("artist-credit") or rec.get("artist-credit")),
            })
            for rr in rec.get("relations") or []:
                w = rr.get("work") or {}
                if rr.get("target-type") == "work" and rr.get("type") == "performance" and w.get("id"):
                    rec_work_rows.append({
                        "recording_id": rec.get("id"),
                        "work_id": w["id"],
                        "work_title": w.get("title"),
                        "attributes": ",".join(rr.get("attributes") or []) or None,
                    })
                    works_from_rels.setdefault(w["id"], w)

# Recordings appear on several kept releases: keep one row per recording-work pair.
rec_work_rows = list({(r["recording_id"], r["work_id"]): r for r in rec_work_rows}.values())

# Works: artist browse first; works only reached through recordings (covers, co-writes) added after.
work_by_id = {w["id"]: work_row(w, "artist_browse") for w in works_browsed}
for wid, w in works_from_rels.items():
    work_by_id.setdefault(wid, work_row(w, "recording_relation"))
work_rows = list(work_by_id.values())

print(f"release_group {len(rg_rows)} | release {len(release_rows)} | track {len(track_rows)} | "
      f"recording_work {len(rec_work_rows)} | work {len(work_rows)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 5. Write Delta tables (full snapshot)

# CELL ********************

S = StringType
schemas = {
    "release_group": StructType([StructField(c, S()) for c in
        ["release_group_id", "title", "primary_type", "secondary_types", "first_release_date", "disambiguation"]]),
    "release": StructType([StructField(c, S()) for c in
        ["release_id", "release_group_id", "title", "date", "country", "status", "disambiguation"]]
        + [StructField("official_release_count", IntegerType())]),
    "track": StructType([
        StructField("release_id", S()), StructField("medium_position", IntegerType()),
        StructField("medium_format", S()), StructField("track_position", IntegerType()),
        StructField("track_number", S()), StructField("track_title", S()),
        StructField("recording_id", S()), StructField("recording_title", S()),
        StructField("length_ms", LongType()), StructField("artist_credit", S())]),
    "recording_work": StructType([StructField(c, S()) for c in ["recording_id", "work_id", "work_title", "attributes"]]),
    "work": StructType([StructField(c, S()) for c in
        ["work_id", "title", "type", "language", "disambiguation", "found_via"]]),
}
rows_by_entity = {"release_group": rg_rows, "release": release_rows, "track": track_rows,
                  "recording_work": rec_work_rows, "work": work_rows}

previous_counts, dfs = {}, {}
for entity, rows in rows_by_entity.items():
    table = f"{TABLE_PREFIX}_{entity}"
    if spark.catalog.tableExists(table):
        previous_counts[entity] = spark.read.table(table).count()
    df = (spark.createDataFrame(rows, schema=schemas[entity])
          .withColumn("_run_id", F.lit(RUN_ID))
          .withColumn("_ingested_at", F.lit(RUN_TS).cast(TimestampType())))
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    dfs[entity] = spark.read.table(table)
    print(f"{table}: {dfs[entity].count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 6. Data quality checks

# CELL ********************

counts = {entity: df.count() for entity, df in dfs.items()}
dq = Results(run_id=RUN_ID, layer="bronze")


def dup_count(df, *cols) -> int:
    return df.count() - df.select(*cols).distinct().count()


if not MAX_RELEASE_GROUPS:
    dq.check("mb_release_group_count_eq_api", counts["release_group"] == api_rg_total, "hard",
             value=f"{counts['release_group']}/{api_rg_total}")
dq.check("mb_work_browse_count_eq_api", len(works_browsed) == api_work_total, "hard",
         value=f"{len(works_browsed)}/{api_work_total}")
dq.check("mb_release_group_no_dup_id", dup_count(dfs["release_group"], "release_group_id") == 0, "hard")
dq.check("mb_release_no_dup_id", dup_count(dfs["release"], "release_id") == 0, "hard")
dq.check("mb_track_no_dup_position",
         dup_count(dfs["track"], "release_id", "medium_position", "track_position") == 0, "hard")
dq.check("mb_work_no_dup_id", dup_count(dfs["work"], "work_id") == 0, "hard")
dq.check("mb_every_kept_release_looked_up", len(release_details) == len(kept_releases), "hard",
         value=f"{len(release_details)}/{len(kept_releases)}")
dq.check("mb_release_groups_without_official_release", len(rg_without_release) == 0, "warning",
         value=len(rg_without_release))

studio_albums = (dfs["release_group"]
                 .filter("primary_type = 'Album' AND secondary_types IS NULL")
                 .orderBy("first_release_date").select("first_release_date", "title").collect())
studio_titles = [r.title for r in studio_albums]
if not MAX_RELEASE_GROUPS:
    dq.check("mb_studio_album_boy_present", "Boy" in studio_titles, "hard", value=len(studio_titles))

tracks_without_work = (dfs["track"].join(dfs["recording_work"], "recording_id", "left_anti")
                       .select("recording_id").distinct().count())
dq.check("mb_recordings_without_work", tracks_without_work == 0, "warning", value=tracks_without_work)

for entity, prev in previous_counts.items():
    change = abs(counts[entity] - prev) / prev if prev else 0.0
    dq.check(f"mb_{entity}_change_vs_previous_le_10pct", change <= 0.10, "warning",
             value=f"{prev}->{counts[entity]}")

print("\nStudio albums:")
for r in studio_albums:
    print(f"  {r.first_release_date}  {r.title}")
print("\nSongs of Surrender:",
      [(r.primary_type, r.secondary_types) for r in
       dfs["release_group"].filter("title = 'Songs of Surrender'").collect()])

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
    "run_id": RUN_ID,
    "api_calls": n_calls[0],
    "api_release_group_total": api_rg_total,
    "api_work_total": api_work_total,
    "studio_albums": len(studio_titles),
    "release_groups_without_official_release": len(rg_without_release),
    "recordings_without_work": tracks_without_work,
    **{f"{TABLE_PREFIX}_{k}": v for k, v in counts.items()},
    **dq.summary(),
}
print(json.dumps(exit_value, indent=2))
notebookutils.notebook.exit(json.dumps(exit_value))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

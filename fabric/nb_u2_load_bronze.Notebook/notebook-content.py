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

# # U2 · Bronze · setlist.fm
# 
# Ingests every U2 setlist from the setlist.fm API into the Lakehouse.
# 
# **What this notebook does**
# 1. Fetches every page of `/artist/{mbid}/setlists` (20 shows per page) with retries and rate limiting.
# 2. Saves the raw JSON for each page to `Files/bronze/setlistfm/u2/<run_id>/`.
# 3. Creates three Delta tables in the Bronze layer:
#    - `bronze_setlistfm_setlist_raw`: one row per setlist, with the original JSON
#    - `bronze_setlistfm_show`: one row per show (date, venue, tour)
#    - `bronze_setlistfm_performance`: one row per song performed at each show
# 4. Runs data quality checks and builds the list of distinct song names (the starting point for `silver.song_map`).
# 
# **Prerequisites**
# - A Lakehouse attached to the notebook as the default.
# - A setlist.fm API key (free for non-commercial use: create an account and request one under *Settings › API*).
# - Recommended: store the key in Azure Key Vault and read it with `notebookutils.credentials.getSecret`.

# PARAMETERS CELL ********************

# Parameters (cell tagged "parameters" so pipelines can override them)

# Where to get the API key: "keyvault" (recommended) or "inline" (quick tests only)
API_KEY_SOURCE = "keyvault"
KEY_VAULT_URL  = "https://kv-vini-u2.vault.azure.net/"
SECRET_NAME    = "setlistfm-api-key"
API_KEY_INLINE = ""            # used only when API_KEY_SOURCE = "inline"; never commit it filled in

ARTIST_NAME  = "U2"
ARTIST_MBID  = "a3cb23fc-acd3-4ce0-8f36-1e5aa6a18432"   # U2's MusicBrainz ID (verified in the validation cell)

MAX_PAGES      = None   # None = all pages; use 2 or 3 for a quick test
SLEEP_SECONDS  = 0.6    # pause between calls (the API limits requests per second)
MAX_RETRIES    = 5

RAW_FOLDER     = "Files/bronze/setlistfm/u2"
TABLE_PREFIX   = "bronze_setlistfm"

RUN_ID         = ""     # empty = generated from the current UTC time (pl_refresh passes its run id)
WRITE_DQ       = True   # append the data quality checks to wh_gold.dbo.dq_run_log (SPEC-07)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import json, time, datetime as dt
import requests
from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType,
                               BooleanType, DoubleType, TimestampType)

BASE_URL = "https://api.setlist.fm/rest/1.0"
RUN_TS   = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
RUN_ID   = RUN_ID or RUN_TS.strftime("%Y%m%dT%H%M%SZ")
print("Run:", RUN_ID)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 1. API key and HTTP client

# CELL ********************

def get_api_key() -> str:
    if API_KEY_SOURCE == "keyvault":
        return notebookutils.credentials.getSecret(KEY_VAULT_URL, SECRET_NAME).strip()
    if API_KEY_SOURCE == "inline" and API_KEY_INLINE:
        return API_KEY_INLINE
    raise ValueError("Set up the key: API_KEY_SOURCE = 'keyvault', or fill in API_KEY_INLINE.")

session = requests.Session()
session.headers.update({
    "x-api-key": get_api_key(),
    "Accept": "application/json",      # without this the API returns XML
    "Accept-Language": "en",
})


def api_get(path: str, params: dict | None = None) -> dict:
    """GET with exponential backoff on 429 (rate limit) and 5xx errors."""
    url = f"{BASE_URL}{path}"
    for attempt in range(1, MAX_RETRIES + 1):
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            return {}
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = int(resp.headers.get("Retry-After", 0)) or 2 ** attempt
            print(f"  {resp.status_code} on {path} (attempt {attempt}); waiting {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {url}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2. Validate the artist

# CELL ********************

# Make sure the configured MBID really is U2 (avoids pulling data for cover or tribute bands)
artist = api_get(f"/artist/{ARTIST_MBID}")
print(artist.get("name"), "|", artist.get("disambiguation", ""), "|", artist.get("url"))
assert artist.get("name", "").lower() == ARTIST_NAME.lower(), "MBID does not match the expected artist"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 3. Fetch all setlists (paginated)

# CELL ********************

def fetch_all_setlists(mbid: str, max_pages: int | None = None) -> tuple[list[dict], int]:
    pages, page, total_pages, total_items = [], 1, None, 0
    while True:
        data = api_get(f"/artist/{mbid}/setlists", params={"p": page})
        if not data or not data.get("setlist"):
            break
        pages.append(data)
        if total_pages is None:
            total_items = data.get("total", 0)
            per_page    = data.get("itemsPerPage", 20) or 20
            total_pages = -(-total_items // per_page)
            print(f"API total: {total_items} setlists across {total_pages} pages")
        if page % 10 == 0 or page == total_pages:
            print(f"  page {page}/{total_pages}")
        if page >= total_pages or (max_pages and page >= max_pages):
            break
        page += 1
        time.sleep(SLEEP_SECONDS)
    return pages, total_items

pages, api_total = fetch_all_setlists(ARTIST_MBID, MAX_PAGES)
print(f"Pages fetched: {len(pages)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Save the raw JSON for each page (for auditing and reprocessing without calling the API again)
run_folder = f"{RAW_FOLDER}/{RUN_ID}"
for i, pg in enumerate(pages, start=1):
    notebookutils.fs.put(f"{run_folder}/page_{i:04d}.json", json.dumps(pg, ensure_ascii=False), True)
print("Raw JSON saved to:", run_folder)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4. Flatten the JSON into rows

# CELL ********************

def _parse_date(s: str | None) -> str | None:
    """setlist.fm uses dd-MM-yyyy; returns ISO yyyy-MM-dd."""
    if not s:
        return None
    try:
        return dt.datetime.strptime(s, "%d-%m-%Y").date().isoformat()
    except ValueError:
        return None


def _to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def flatten_setlist(sl: dict) -> tuple[dict, list[dict]]:
    venue   = sl.get("venue") or {}
    city    = venue.get("city") or {}
    coords  = city.get("coords") or {}
    country = city.get("country") or {}
    tour    = sl.get("tour") or {}

    show = {
        "setlist_id":     sl.get("id"),
        "version_id":     sl.get("versionId"),
        "event_date":     _parse_date(sl.get("eventDate")),
        "last_updated":   sl.get("lastUpdated"),
        "artist_mbid":    (sl.get("artist") or {}).get("mbid"),
        "tour_name":      tour.get("name"),
        "venue_id":       venue.get("id"),
        "venue_name":     venue.get("name"),
        "city_id":        city.get("id"),
        "city_name":      city.get("name"),
        "state":          city.get("state"),
        "state_code":     city.get("stateCode"),
        "country_code":   country.get("code"),
        "country_name":   country.get("name"),
        "latitude":       _to_float(coords.get("lat")),
        "longitude":      _to_float(coords.get("long")),
        "show_info":      sl.get("info"),
        "setlist_url":    sl.get("url"),
    }

    rows, show_pos = [], 0
    for set_idx, s in enumerate((sl.get("sets") or {}).get("set") or [], start=1):
        encore = s.get("encore")
        if s.get("name"):
            set_name = s["name"]
        elif encore:
            set_name = f"Encore {encore}"
        else:
            set_name = "Main set"
        for set_pos, song in enumerate(s.get("song") or [], start=1):
            show_pos += 1
            cover = song.get("cover") or {}
            with_ = song.get("with") or {}
            rows.append({
                "setlist_id":       show["setlist_id"],
                "event_date":       show["event_date"],
                "set_index":        set_idx,
                "set_name":         set_name,
                "encore_number":    int(encore) if encore else None,
                "set_position":     set_pos,
                "setlist_position": show_pos,
                "song_name":        (song.get("name") or "").strip(),
                "song_info":        song.get("info"),
                "is_tape":          bool(song.get("tape", False)),
                "cover_artist":     cover.get("name"),
                "cover_mbid":       cover.get("mbid"),
                "with_artist":      with_.get("name"),
            })
    show["song_count"] = sum(1 for r in rows if not r["is_tape"] and r["song_name"])
    return show, rows


raw_rows, show_rows, perf_rows = [], [], []
for pg in pages:
    for sl in pg.get("setlist", []):
        s, p = flatten_setlist(sl)
        show_rows.append(s)
        perf_rows.extend(p)
        raw_rows.append({
            "setlist_id":   sl.get("id"),
            "version_id":   sl.get("versionId"),
            "event_date":   s["event_date"],
            "last_updated": sl.get("lastUpdated"),
            "json_raw":     json.dumps(sl, ensure_ascii=False),
        })

print(f"Shows: {len(show_rows)} | performances: {len(perf_rows)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 5. Write Delta tables

# CELL ********************

raw_schema = StructType([
    StructField("setlist_id",   StringType()),
    StructField("version_id",   StringType()),
    StructField("event_date",   StringType()),
    StructField("last_updated", StringType()),
    StructField("json_raw",     StringType()),
])

show_schema = StructType([
    StructField("setlist_id",   StringType()),
    StructField("version_id",   StringType()),
    StructField("event_date",   StringType()),
    StructField("last_updated", StringType()),
    StructField("artist_mbid",  StringType()),
    StructField("tour_name",    StringType()),
    StructField("venue_id",     StringType()),
    StructField("venue_name",   StringType()),
    StructField("city_id",      StringType()),
    StructField("city_name",    StringType()),
    StructField("state",        StringType()),
    StructField("state_code",   StringType()),
    StructField("country_code", StringType()),
    StructField("country_name", StringType()),
    StructField("latitude",     DoubleType()),
    StructField("longitude",    DoubleType()),
    StructField("show_info",    StringType()),
    StructField("setlist_url",  StringType()),
    StructField("song_count",   IntegerType()),
])

perf_schema = StructType([
    StructField("setlist_id",       StringType()),
    StructField("event_date",       StringType()),
    StructField("set_index",        IntegerType()),
    StructField("set_name",         StringType()),
    StructField("encore_number",    IntegerType()),
    StructField("set_position",     IntegerType()),
    StructField("setlist_position", IntegerType()),
    StructField("song_name",        StringType()),
    StructField("song_info",        StringType()),
    StructField("is_tape",          BooleanType()),
    StructField("cover_artist",     StringType()),
    StructField("cover_mbid",       StringType()),
    StructField("with_artist",      StringType()),
])


def to_df(rows, schema):
    df = spark.createDataFrame(rows, schema=schema)
    df = df.withColumn("event_date", F.to_date("event_date"))
    if "last_updated" in df.columns:
        # API format: 2024-07-24T10:00:00.000+0000
        df = df.withColumn("last_updated", F.to_timestamp("last_updated", "yyyy-MM-dd'T'HH:mm:ss.SSSZ"))
    return (df.withColumn("_run_id", F.lit(RUN_ID))
              .withColumn("_ingested_at", F.lit(RUN_TS).cast(TimestampType())))


df_raw  = to_df(raw_rows,  raw_schema)
df_show = to_df(show_rows, show_schema)
df_perf = to_df(perf_rows, perf_schema)

# Full snapshot on every run: setlist.fm is crowd-sourced and old shows get corrected often,
# so rewriting everything is simpler and safer than an incremental merge.
previous_counts = {}   # row counts of the last run, for the "change vs previous run" check (SPEC-07)
for name, df in [("setlist_raw", df_raw), ("show", df_show), ("performance", df_perf)]:
    table = f"{TABLE_PREFIX}_{name}"
    if spark.catalog.tableExists(table):
        previous_counts[name] = spark.read.table(table).count()
    (df.write.format("delta").mode("overwrite")
       .option("overwriteSchema", "true").saveAsTable(table))
    print(f"{table}: {df.count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 6. Data quality checks

# CELL ********************

n_shows = df_show.count()
dups    = n_shows - df_show.select("setlist_id").distinct().count()
print(f"Shows written: {n_shows} | API total: {api_total} | duplicate ids: {dups}")
if MAX_PAGES is None and n_shows != api_total:
    print("  Warning: written count differs from API total (new shows added during the load, or empty pages)")

print("\nShows with no songs recorded:",
      df_show.filter("song_count = 0").count())
print("Performances with no song name:",
      df_perf.filter("song_name = ''").count())
print("Shows with no valid date:",
      df_show.filter("event_date IS NULL").count())

display(df_show.groupBy(F.year("event_date").alias("year"))
               .count().orderBy("year"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Top 15 most-played songs (excluding tapes)
display(
    df_perf.filter("NOT is_tape AND song_name <> ''")
           .groupBy("song_name").count()
           .orderBy(F.desc("count")).limit(15)
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 7. Input for Silver: distinct song names

# CELL ********************

# Basis for building silver.song_map (setlist.fm name -> MusicBrainz work MBID)
df_names = (df_perf.filter("song_name <> ''")
    .groupBy("song_name", "cover_artist")
    .agg(F.count("*").alias("performances"),
         F.min("event_date").alias("first_played"),
         F.max("event_date").alias("last_played"),
         F.sum(F.col("is_tape").cast("int")).alias("times_as_tape"))
    .orderBy(F.desc("performances")))

df_names.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{TABLE_PREFIX}_distinct_song")
print("Distinct names:", df_names.count())
display(df_names)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 8. Data quality log and exit value (SPEC-07)
# # Hard checks stop the pipeline; every check is appended to `wh_gold.dbo.dq_run_log`.

# CELL ********************

from u2lib.quality import Results

counts = {
    f"{TABLE_PREFIX}_setlist_raw": df_raw.count(),
    f"{TABLE_PREFIX}_show": n_shows,
    f"{TABLE_PREFIX}_performance": df_perf.count(),
    f"{TABLE_PREFIX}_distinct_song": df_names.count(),
}
dq = Results(run_id=RUN_ID, layer="bronze")
if MAX_PAGES is None:
    dq.check("setlistfm_show_count_eq_api_total", n_shows == api_total, "hard", value=f"{n_shows}/{api_total}")
dq.check("setlistfm_show_no_dup_id", dups == 0, "hard", value=dups)
dq.check("setlistfm_performance_not_empty", counts[f"{TABLE_PREFIX}_performance"] > 0, "hard",
         value=counts[f"{TABLE_PREFIX}_performance"])
n_no_date = df_show.filter("event_date IS NULL").count()
dq.check("setlistfm_show_has_date", n_no_date == 0, "warning", value=n_no_date)
for name, prev in previous_counts.items():
    now = counts[f"{TABLE_PREFIX}_{name}"]
    change = abs(now - prev) / prev if prev else 0.0
    dq.check(f"setlistfm_{name}_change_vs_previous_le_10pct", change <= 0.10, "warning", value=f"{prev}->{now}")

if WRITE_DQ:
    dq.write(spark)
exit_value = {"run_id": RUN_ID, "api_total": api_total, "pages": len(pages), **counts, **dq.summary()}
print(json.dumps(exit_value, indent=2))
dq.raise_on_hard_failures()
notebookutils.notebook.exit(json.dumps(exit_value))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Next steps
# 
# - **Silver**: clean `song_name` (trim, quotes, spelling variants), separate snippets using `song_info`, and build `song_map` with each composition's MBID.
# - **MusicBrainz**: a companion notebook to pull U2's discography (release groups and works) and populate `dim_album` and `dim_song`.
# - **Scheduling**: a weekly run in a Fabric pipeline is enough; a full U2 load is on the order of one or two hundred API calls.

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

# # U2 · Silver · catalog
# # Builds `album`, `song` and `tour` in `lk_silver` (SPEC-03 §3.2). Reads only Bronze, so it can run in parallel
# with `nb_silver_shows` (SPEC-07).
# # **Inputs**: `lk_bronze.dbo.bronze_musicbrainz_*`, `lk_bronze.dbo.bronze_seed_album_overrides`,
# `lk_bronze.dbo.bronze_seed_tours`, `lk_bronze.dbo.bronze_setlistfm_show`, `lk_bronze.dbo.bronze_setlistfm_distinct_song`.
# # **Outputs** (overwrite, `lk_silver.dbo`):
# - `album`: release groups with a kept official release; `album_type` by the first rule that applies
#   (override seed → Live → Compilation → EP → Single → plain Album = studio → anything else = compilation).
# - `song`: MusicBrainz works (artist browse) with their first album; works setlist.fm plays as covers get
#   `is_original = false` and `cover_artist` (except the Passengers/Bono exceptions); U2 originals without a work
#   (override `original`) as `u2:<song key>`; synthetic cover songs (`cover:<song key>:<artist key>`).
# - `tour`: one row per setlist.fm tour plus `(No tour)`, with the promoted album resolved by title.

# PARAMETERS CELL ********************

RUN_ID   = ""            # empty = generated from the current UTC time (pipeline passes its run id)
WRITE_DQ = True          # append checks to wh_gold.dbo.dq_run_log
NO_TOUR  = "(No tour)"

# Studio albums expected after the rules and overrides (SPEC-03 §3.2), compared with normalize_title.
EXPECTED_STUDIO = [
    "Boy", "October", "War", "The Unforgettable Fire", "The Joshua Tree", "Rattle and Hum", "Achtung Baby",
    "Zooropa", "Pop", "All That You Can’t Leave Behind", "How to Dismantle an Atomic Bomb",
    "No Line on the Horizon", "Songs of Innocence", "Songs of Experience", "Carnaval de luz",
]
MIN_SHOWS_NEED_ALBUM = 20   # tours with at least this many shows need a promoted album or a note in the seed

FUZZY_THRESHOLD = 92        # same as nb_silver_song_map: used to find which works setlist.fm plays as covers
# Works kept is_original = true although setlist.fm tags another act (SPEC-03 §3.2, T-17).
ORIGINAL_DESPITE_COVER_TAG = {
    "a5a40c84-5e06-3249-ac20-360fac47dfc0",   # Miss Sarajevo (Passengers)
    "4004dfec-990d-35e8-899a-32d76450e96c",   # Your Blue Room (Passengers)
    "c2f945b8-c4a3-3044-b55e-95aab187644d",   # Silver and Gold
    "69985e91-92dd-3af4-81d0-f4f7ea259982",   # North and South of the River
}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import json
import datetime as dt
from collections import Counter, defaultdict

from pyspark.sql import functions as F
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType, BooleanType, DateType,
                               TimestampType)

import u2lib
from u2lib import matching, shows, songs
from u2lib.quality import Results

RUN_TS = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
RUN_ID = RUN_ID or RUN_TS.strftime("%Y%m%dT%H%M%SZ")
print("Run:", RUN_ID, "| u2lib", u2lib.__version__)


def bronze(table: str) -> list[dict]:
    return [r.asDict() for r in spark.read.table(f"lk_bronze.dbo.{table}").collect()]


def clean(s):
    if s is None:
        return None
    s = str(s).strip()
    return s or None

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 1. Read Bronze

# CELL ********************

b_rg = bronze("bronze_musicbrainz_release_group")
b_rel = bronze("bronze_musicbrainz_release")
b_track = bronze("bronze_musicbrainz_track")
b_rw = bronze("bronze_musicbrainz_recording_work")
b_work = bronze("bronze_musicbrainz_work")
b_album_ovr = bronze("bronze_seed_album_overrides")
b_tours = bronze("bronze_seed_tours")
b_show = bronze("bronze_setlistfm_show")
b_distinct = bronze("bronze_setlistfm_distinct_song")
b_song_ovr = bronze("bronze_seed_song_alias_overrides")
manual_exclusions = {r["setlist_id"].strip() for r in bronze("bronze_seed_show_exclusions") if r["setlist_id"]}
print(f"release groups {len(b_rg)} | releases {len(b_rel)} | tracks {len(b_track)} | recording-work {len(b_rw)} "
      f"| works {len(b_work)} | album overrides {len(b_album_ovr)} | seed tours {len(b_tours)} | shows {len(b_show)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2. Album

# CELL ********************

ALBUM_TYPES = {"studio", "live", "compilation", "re-recording", "ep", "single"}


def parse_partial_date(s):
    """MusicBrainz dates are yyyy, yyyy-MM or yyyy-MM-dd. Returns (date at the start of the period, year)."""
    s = clean(s)
    if not s:
        return None, None
    parts = s.split("-")
    try:
        y = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 1
        d = int(parts[2]) if len(parts) > 2 else 1
        return dt.date(y, m, d), y
    except (ValueError, IndexError):
        return None, None


def album_type_of(rg: dict, override: str | None) -> str:
    if override:
        return override
    secondary = [t.strip() for t in (rg["secondary_types"] or "").split(",") if t.strip()]
    primary = rg["primary_type"]
    if "Live" in secondary:
        return "live"
    if "Compilation" in secondary:
        return "compilation"
    if primary == "EP":
        return "ep"
    if primary == "Single":
        return "single"
    if primary == "Album" and not secondary:
        return "studio"
    return "compilation"


overrides = {o["release_group_id"]: clean(o["album_type"]) for o in b_album_ovr}
bad_override_types = sorted({t for t in overrides.values() if t not in ALBUM_TYPES})
kept_rg_ids = {r["release_group_id"] for r in b_rel}

album_rows = []
for rg in b_rg:
    if rg["release_group_id"] not in kept_rg_ids:
        continue                                   # bootleg-only group: no official release
    release_date, release_year = parse_partial_date(rg["first_release_date"])
    album_type = album_type_of(rg, overrides.get(rg["release_group_id"]))
    album_rows.append({
        "album_id": rg["release_group_id"],
        "title": clean(rg["title"]),
        "release_date": release_date,
        "release_year": release_year,
        "album_type": album_type,
        "is_studio": album_type == "studio",
    })
album_by_id = {a["album_id"]: a for a in album_rows}
overrides_not_applied = sorted(set(overrides) - set(album_by_id))
print(f"albums {len(album_rows)} | studio {sum(a['is_studio'] for a in album_rows)} "
      f"| overrides not matching a kept group {overrides_not_applied}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 3. Song (U2 works + covers)

# CELL ********************

# recording -> albums it appears on (through tracks of kept releases)
release_to_album = {r["release_id"]: r["release_group_id"] for r in b_rel}
recording_albums = defaultdict(set)
for t in b_track:
    album_id = release_to_album.get(t["release_id"])
    if album_id in album_by_id and t["recording_id"]:
        recording_albums[t["recording_id"]].add(album_id)

work_albums = defaultdict(set)
for rw in b_rw:
    work_albums[rw["work_id"]].update(recording_albums.get(rw["recording_id"], ()))


def album_sort_key(album_id):
    a = album_by_id[album_id]
    return (a["release_date"] or dt.date(9999, 12, 31), album_id)


def first_album_and_year(album_ids):
    """First album (studio first, then any; earliest date, then id) and earliest year. Re-recordings never count."""
    albums = [a for a in album_ids if album_by_id[a]["album_type"] != "re-recording"]
    studio = [a for a in albums if album_by_id[a]["is_studio"]]
    first_album = min(studio or albums, key=album_sort_key) if albums else None
    years = [album_by_id[a]["release_year"] for a in albums if album_by_id[a]["release_year"]]
    return first_album, (min(years) if years else None)


u2_works = [w for w in b_work if w["found_via"] == "artist_browse"]

# Song-name overrides (same seed as nb_silver_song_map): key -> work id, "original" or "ignore".
override_by_key = {}
for o in b_song_ovr:
    key, target = songs.normalize_title(o["song_name"]), clean(o["work_id"])
    if key and target:
        override_by_key[key] = target.lower() if target.lower() in ("ignore", "original") else target


def original_rank(w):
    """Tie-break among U2 works sharing a normalised title (same as nb_silver_song_map)."""
    first_album, year = first_album_and_year(work_albums.get(w["work_id"], ()))
    return (first_album is None, year or 9999, w["work_id"])


works_by_key = defaultdict(list)
for w in u2_works:
    works_by_key[songs.normalize_title(w["title"])].append(w)
work_keys = sorted(k for k in works_by_key if k)


def resolve_work(key):
    """Work id a setlist.fm song key maps to by the song_map order override -> exact -> fuzzy, else None."""
    target = override_by_key.get(key)
    if target:
        return None if target in ("ignore", "original") else target
    if key in works_by_key:
        return min(works_by_key[key], key=original_rank)["work_id"]
    best = matching.best_match(key, work_keys, FUZZY_THRESHOLD)
    return min(works_by_key[best[0]], key=original_rank)["work_id"] if best else None


# Works that setlist.fm plays as covers (SPEC-03 §3.2): artist weighted by performances.
cover_artists_by_work = defaultdict(Counter)
for d in b_distinct:
    artist, name = clean(d["cover_artist"]), clean(d["song_name"])
    if artist and name:
        work_id = resolve_work(songs.normalize_title(name))
        if work_id:
            cover_artists_by_work[work_id][artist] += d["performances"] or 0

# Keep a MusicBrainz work only if setlist.fm references it (any name resolving to it by the song_map order) or it has a
# recording on a kept official U2 release (work_albums, re-recordings included). The artist browse also returns works
# U2 never played or released ("(I Can't Get No) Satisfaction", Billie Jean, …): they are dropped (model BPA review).
referenced_works = set()
for d in b_distinct:
    name = clean(d["song_name"])
    if name:
        work_id = resolve_work(songs.normalize_title(name))
        if work_id:
            referenced_works.add(work_id)
kept_works = [w for w in u2_works if w["work_id"] in referenced_works or work_albums.get(w["work_id"])]
dropped_works = len(u2_works) - len(kept_works)
print(f"MusicBrainz works kept {len(kept_works)} of {len(u2_works)} (referenced {len(referenced_works)}, "
      f"dropped {dropped_works}: never played and not on a U2 release)")

song_rows = []
for w in kept_works:
    first_album, first_year = first_album_and_year(work_albums.get(w["work_id"], ()))
    tagged = cover_artists_by_work.get(w["work_id"])
    is_cover = bool(tagged) and w["work_id"] not in ORIGINAL_DESPITE_COVER_TAG
    song_rows.append({
        "song_id": w["work_id"],
        "title": clean(w["title"]),
        "first_album_id": first_album,
        "first_release_year": first_year,
        "is_original": not is_cover,
        "cover_artist": tagged.most_common(1)[0][0] if is_cover else None,
    })
non_original_works = sum(1 for s in song_rows if not s["is_original"])

# U2 originals without a MusicBrainz work: override work_id = "original" -> song_id "u2:<song key>".
recording_title_albums = defaultdict(set)
for t in b_track:
    album_id = release_to_album.get(t["release_id"])
    if album_id in album_by_id and t["recording_title"]:
        recording_title_albums[songs.normalize_title(t["recording_title"])].add(album_id)
name_counts = defaultdict(Counter)
for d in b_distinct:
    name = clean(d["song_name"])
    if name:
        name_counts[songs.normalize_title(name)][name] += d["performances"] or 0
synthetic_originals = []
for key, target in sorted(override_by_key.items()):
    if target != "original":
        continue
    first_album, first_year = first_album_and_year(recording_title_albums.get(key, ()))
    title = name_counts[key].most_common(1)[0][0] if name_counts.get(key) else key
    synthetic_originals.append({
        "song_id": f"u2:{key}", "title": title, "first_album_id": first_album,
        "first_release_year": first_year, "is_original": True, "cover_artist": None,
    })
song_rows.extend(synthetic_originals)

# Fragments (short lead-ins/excerpts that setlist.fm lists as songs, e.g. The Cry): override rows with
# is_fragment = true flag their target song; default measures exclude them like snippets (SPEC-03 §3.2).
fragment_ids = set()
for o in b_song_ovr:
    key, target = songs.normalize_title(o["song_name"]), clean(o["work_id"])
    if key and target and (clean(o.get("is_fragment")) or "").lower() == "true":
        if target.lower() == "original":
            fragment_ids.add(f"u2:{key}")
        elif target.lower() != "ignore":
            fragment_ids.add(target)
for s in song_rows:
    s["is_fragment"] = s["song_id"] in fragment_ids
fragments_missing = sorted(fragment_ids - {s["song_id"] for s in song_rows})
print("Fragments:", sorted(fragment_ids))
print(f"non-original works {non_original_works} | synthetic originals {len(synthetic_originals)} "
      f"(with a first album {sum(1 for s in synthetic_originals if s['first_album_id'])})")

# Covers: one synthetic song per (song key, cover artist key); title = most played spelling.
covers = {}
for d in sorted(b_distinct, key=lambda r: (-(r["performances"] or 0), r["song_name"] or "")):
    artist = clean(d["cover_artist"])
    name = clean(d["song_name"])
    if not artist or not name:
        continue
    song_id = f"cover:{songs.normalize_title(name)}:{songs.normalize_title(artist)}"
    covers.setdefault(song_id, {"song_id": song_id, "title": name, "first_album_id": None,
                                "first_release_year": None, "is_original": False, "cover_artist": artist})
song_rows.extend(covers.values())
print(f"songs {len(song_rows)} (U2 works {len(kept_works)} of {len(u2_works)}, covers {len(covers)}) "
      f"| U2 works with a first album {sum(1 for s in song_rows if s['first_album_id'])}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 4. Tour

# CELL ********************

# Show statistics per tour from real shows (same exclusion rule as nb_silver_shows).
tour_stats = {}
for s in b_show:
    if s["setlist_id"] in manual_exclusions or shows.exclusion_reason(s["show_info"]):
        continue
    name = clean(s["tour_name"]) or NO_TOUR
    st = tour_stats.setdefault(name, {"first": None, "last": None, "shows": 0})
    st["shows"] += 1
    d = s["event_date"]
    if d:
        st["first"] = d if st["first"] is None else min(st["first"], d)
        st["last"] = d if st["last"] is None else max(st["last"], d)

albums_by_key = defaultdict(list)
for a in album_rows:
    albums_by_key[songs.normalize_title(a["title"])].append(a)


def resolve_album(title):
    """Album id for a seed title: normalised title match; prefer studio, then earliest release date, then id."""
    hits = albums_by_key.get(songs.normalize_title(title), [])
    if not hits:
        return None
    best = min(hits, key=lambda a: (not a["is_studio"], a["release_date"] or dt.date(9999, 12, 31), a["album_id"]))
    return best["album_id"]


seed_by_name = {t["tour_name"]: t for t in b_tours}
tour_rows, unresolved, missing_note = [], [], []
for name in sorted(tour_stats):
    seed = seed_by_name.get(name, {})
    promoted_title = clean(seed.get("album_promoted"))
    album_id = resolve_album(promoted_title) if promoted_title else None
    if promoted_title and not album_id:
        unresolved.append(f"{name} -> {promoted_title}")
    st = tour_stats[name]
    if (name != NO_TOUR and not album_id and st["shows"] >= MIN_SHOWS_NEED_ALBUM
            and not clean(seed.get("note"))):
        missing_note.append(name)
    tour_rows.append({
        "tour_name": name,
        "tour_name_display": clean(seed.get("tour_name_display")) or name,
        "album_promoted_id": album_id,
        "is_residency": (clean(seed.get("is_residency")) or "false").lower() == "true",
        "era": clean(seed.get("era")),
        "first_show_date": st["first"],
        "last_show_date": st["last"],
        "shows": st["shows"],
    })
tours_not_in_seed = sorted(n for n in tour_stats if n != NO_TOUR and n not in seed_by_name)
seed_tours_not_in_bronze = sorted(n for n in seed_by_name if n not in tour_stats)
print(f"tours {len(tour_rows)} | unresolved promoted albums {unresolved} | not in seed {tours_not_in_seed}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 5. Write Silver tables

# CELL ********************

S, I, B, D = StringType(), IntegerType(), BooleanType(), DateType()
schemas = {
    "album": StructType([
        StructField("album_id", S), StructField("title", S), StructField("release_date", D),
        StructField("release_year", I), StructField("album_type", S), StructField("is_studio", B)]),
    "song": StructType([
        StructField("song_id", S), StructField("title", S), StructField("first_album_id", S),
        StructField("first_release_year", I), StructField("is_original", B), StructField("cover_artist", S),
        StructField("is_fragment", B)]),
    "tour": StructType([
        StructField("tour_name", S), StructField("tour_name_display", S), StructField("album_promoted_id", S),
        StructField("is_residency", B), StructField("era", S), StructField("first_show_date", D),
        StructField("last_show_date", D), StructField("shows", I)]),
}
rows_by_table = {"album": album_rows, "song": song_rows, "tour": tour_rows}

dfs = {}
for table, rows in rows_by_table.items():
    df = (spark.createDataFrame(rows, schema=schemas[table])
          .withColumn("_run_id", F.lit(RUN_ID))
          .withColumn("_built_at", F.lit(RUN_TS).cast(TimestampType())))
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"dbo.`{table}`")
    dfs[table] = spark.read.table(f"dbo.`{table}`")
    print(f"lk_silver.dbo.{table}: {dfs[table].count()} rows")

# Report images (SPEC-04 presentation assets): copied unchanged from Bronze; only the audit columns are Silver's.
image_counts = {}
for table in ("report_image", "report_image_chunk"):
    src = spark.read.table(f"lk_bronze.dbo.bronze_seed_{table}").drop("_run_id", "_ingested_at")
    (src.withColumn("_run_id", F.lit(RUN_ID)).withColumn("_built_at", F.lit(RUN_TS).cast(TimestampType()))
        .write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"dbo.{table}"))
    image_counts[table] = (spark.read.table(f"dbo.{table}").count(), src.count())
    print(f"lk_silver.dbo.{table}: {image_counts[table][0]} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 6. Data quality checks

# CELL ********************

dq = Results(run_id=RUN_ID, layer="silver")
counts = {t: dfs[t].count() for t in dfs}

studio_titles = sorted(r.title for r in dfs["album"].filter("is_studio").select("title").collect())
expected_keys = sorted(songs.normalize_title(t) for t in EXPECTED_STUDIO)
actual_keys = sorted(songs.normalize_title(t) for t in studio_titles)
print("Studio albums:", studio_titles)
dq.check("album_studio_list_matches_spec", actual_keys == expected_keys, "hard", value=len(studio_titles))
sos = [r.album_type for r in dfs["album"].filter("title = 'Songs of Surrender'").collect()]
dq.check("album_songs_of_surrender_rerecording", sos == ["re-recording"], "hard", value=",".join(sos))
dq.check("album_no_dup_id", counts["album"] == dfs["album"].select("album_id").distinct().count(), "hard")
dq.check("album_override_types_valid", not bad_override_types, "hard", value=",".join(bad_override_types) or None)
dq.check("album_overrides_all_applied", not overrides_not_applied, "warning",
         value=",".join(overrides_not_applied) or None)

dq.check("song_no_dup_id", counts["song"] == dfs["song"].select("song_id").distinct().count(), "hard")
work_ids = {w["work_id"] for w in u2_works}
kept_ids = {w["work_id"] for w in kept_works}
dq.check("song_u2_works_complete", sum(1 for s in song_rows if s["song_id"] in work_ids) == len(kept_works), "hard",
         value=f"{len(kept_works)} kept of {len(u2_works)}")
dq.check("song_referenced_works_kept", referenced_works <= kept_ids, "hard",
         value=",".join(sorted(referenced_works - kept_ids)) or len(referenced_works))
dq.check("song_works_dropped_unplayed_unreleased", True, "warning", value=dropped_works)
with_album = sum(1 for s in song_rows if s["song_id"] in work_ids and s["first_album_id"])
dq.check("song_u2_works_with_first_album", True, "warning", value=f"{with_album}/{len(kept_works)}")
dq.check("song_non_original_works", True, "warning", value=non_original_works)
dq.check("song_fragments_resolved", not fragments_missing, "hard",
         value=",".join(fragments_missing) or len(fragment_ids))
n_original_overrides = sum(1 for t in override_by_key.values() if t == "original")
dq.check("song_synthetic_originals_complete", len(synthetic_originals) == n_original_overrides, "hard",
         value=len(synthetic_originals))
bad_targets = sorted(t for t in override_by_key.values() if t not in ("ignore", "original") and t not in work_ids)
dq.check("song_override_work_ids_exist", not bad_targets, "hard", value=",".join(bad_targets) or None)

dq.check("tour_one_row_per_tour_plus_no_tour", counts["tour"] == len(tour_stats) and NO_TOUR in tour_stats, "hard",
         value=counts["tour"])
dq.check("tour_promoted_album_resolved", not unresolved, "hard", value="; ".join(unresolved) or None)
dq.check("tour_big_tours_have_album_or_note", not missing_note, "hard", value="; ".join(missing_note) or None)
dq.check("tour_names_in_seed", not tours_not_in_seed, "warning", value="; ".join(tours_not_in_seed) or None)
dq.check("seed_tours_in_bronze", not seed_tours_not_in_bronze, "warning",
         value="; ".join(seed_tours_not_in_bronze) or None)
for table, (n_silver, n_bronze) in image_counts.items():
    dq.check(f"{table}_copied", n_silver == n_bronze, "hard", value=f"{n_silver}/{n_bronze}")

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
    "run_id": RUN_ID, **counts,
    "studio_albums": len(studio_titles), "u2_works": len(u2_works), "u2_works_kept": len(kept_works), "covers": len(covers),
    "non_original_works": non_original_works, "synthetic_originals": len(synthetic_originals),
    "fragments": len(fragment_ids),
    **{t: n for t, (n, _) in image_counts.items()},
    "u2_works_with_first_album": with_album,
    "tours_with_promoted_album": sum(1 for t in tour_rows if t["album_promoted_id"]),
    **dq.summary(),
}
print(json.dumps(exit_value, indent=2))
notebookutils.notebook.exit(json.dumps(exit_value))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

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

# # U2 · Bronze · seeds
# # Copies the hand-curated CSVs in `Files/seeds/` into Bronze tables `bronze_seed_<file>` (SPEC-02 §2.3).
# # **Inputs**: `Files/seeds/*.csv` (uploaded from the project's `seeds/` folder with `fab cp`), UTF-8, header row,
# double-quoted fields may contain commas.
# # **Outputs** (full snapshot, `overwrite`): one table per CSV, every column as a string as delivered, plus
# `_run_id` and `_ingested_at`. Expected today: `bronze_seed_tours`, `bronze_seed_song_alias_overrides`,
`bronze_seed_album_overrides`, `bronze_seed_show_exclusions`, `bronze_seed_release_2026_tracks` (SPEC-09 §9.2).
# # **Checks**: required columns present, row count = rows parsed by Python's `csv` module, no duplicate keys.

# PARAMETERS CELL ********************

SEED_FOLDER  = "Files/seeds"
TABLE_PREFIX = "bronze_seed"
RUN_ID       = ""              # empty = generated from the current UTC time
WRITE_DQ     = True            # append checks to wh_gold.dbo.dq_run_log

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import base64
import csv
import io
import json
import os
import datetime as dt

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType

import u2lib
from u2lib.quality import Results

RUN_TS = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
RUN_ID = RUN_ID or RUN_TS.strftime("%Y%m%dT%H%M%SZ")
print("Run:", RUN_ID, "| u2lib", u2lib.__version__)

# Required columns and natural key of each known seed (SPEC-02 §2.3). Other CSVs are loaded without key checks.
SEED_CONTRACT = {
    "tours": {
        "required": ["tour_name", "tour_name_display", "album_promoted", "is_residency", "era", "tour_type",
                     "is_planned"],
        "key": ["tour_name"],
        "min_rows": 1,
    },
    "release_2026_tracks": {           # SPEC-09 §9.2: the 25 tracks of the 2026 trilogy
        "required": ["track_title", "release_title", "release_group_id", "release_type", "release_date",
                     "track_number", "is_single", "single_date", "single_order", "featured_artist",
                     "is_spoken_word", "is_bonus_track", "note"],
        "key": ["release_title", "track_number"],
        "min_rows": 25,
    },
    "song_alias_overrides": {
        "required": ["song_name", "work_id", "note", "is_fragment"],
        "key": ["song_name"],
        "min_rows": 0,     # grows during T-17
    },
    "album_overrides": {
        "required": ["release_group_id", "title", "album_type", "note"],
        "key": ["release_group_id"],
        "min_rows": 1,
    },
    "show_exclusions": {
        "required": ["setlist_id", "event_date", "reason", "note"],
        "key": ["setlist_id"],
        "min_rows": 0,
    },
}

# Report photos (SPEC-04 "Report presentation assets"): manifest seeds/report_images.csv + files in
# Files/seeds/report_images/. Loaded as base64 chunks, not as a plain seed table. Missing manifest = no images yet.
IMAGE_MANIFEST = "report_images"
IMAGE_COLUMNS = ["image_id", "file_name", "mime_type", "credit_text", "license", "source_url", "note"]
IMAGE_FOLDER_LOCAL = f"/lakehouse/default/{SEED_FOLDER}/report_images"   # default lakehouse mount (lk_bronze)
CHUNK_CHARS = 8000
MAX_IMAGES = 12

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 1. Read the CSVs

# CELL ********************

def read_seed(path: str) -> tuple[list[str], list[list[str]]]:
    """Parse a seed CSV with Python's csv module (handles quoted commas and line breaks). Values stay strings."""
    text = notebookutils.fs.head(path, 100 * 1024 * 1024)
    text = text.lstrip("﻿")
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]     # ignore blank lines
    header = [h.strip() for h in rows[0]]
    body = rows[1:]
    bad = [i for i, r in enumerate(body, start=2) if len(r) != len(header)]
    if bad:
        raise ValueError(f"{path}: rows with a wrong number of fields at lines {bad[:10]}")
    return header, body


seed_files = sorted((f for f in notebookutils.fs.ls(SEED_FOLDER) if f.name.lower().endswith(".csv")),
                    key=lambda f: f.name)
seeds = {}
for f in seed_files:
    name = f.name[:-4].lower()
    header, body = read_seed(f"{SEED_FOLDER}/{f.name}")
    seeds[name] = (header, body)
    print(f"{f.name}: {len(body)} rows, columns {header}")

# The image manifest is loaded by section 2b, not as a plain seed table.
image_manifest = seeds.pop(IMAGE_MANIFEST, (IMAGE_COLUMNS, []))
print(f"Report image manifest: {len(image_manifest[1])} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2. Write Delta tables (full snapshot, strings as delivered)

# CELL ********************

dfs = {}
for name, (header, body) in seeds.items():
    table = f"{TABLE_PREFIX}_{name}"
    schema = StructType([StructField(c, StringType()) for c in header])
    rows = [[v if v != "" else None for v in r] for r in body]
    df = (spark.createDataFrame(rows, schema=schema)
          .withColumn("_run_id", F.lit(RUN_ID))
          .withColumn("_ingested_at", F.lit(RUN_TS).cast(TimestampType())))
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    dfs[name] = spark.read.table(table)
    print(f"{table}: {dfs[name].count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 2b. Report images: base64 chunks (SPEC-04 presentation assets; works with zero images)

# CELL ********************

header, body = image_manifest
missing_image_columns = [c for c in IMAGE_COLUMNS if c not in header]
manifest = [dict(zip(header, r)) for r in body] if not missing_image_columns else []
image_rows, chunk_rows, missing_files, roundtrip_errors = [], [], [], []
for m in manifest:
    image_id, file_name = m["image_id"].strip(), m["file_name"].strip()
    path = f"{IMAGE_FOLDER_LOCAL}/{file_name}"
    if not os.path.isfile(path):
        missing_files.append(file_name)
        continue
    with open(path, "rb") as fh:
        data = fh.read()
    b64 = base64.b64encode(data).decode("ascii")
    chunks = [b64[i:i + CHUNK_CHARS] for i in range(0, len(b64), CHUNK_CHARS)]
    if base64.b64decode("".join(chunks)) != data:
        roundtrip_errors.append(image_id)
    image_rows.append({**{c: (m.get(c) or None) for c in IMAGE_COLUMNS}, "image_id": image_id,
                       "file_name": file_name, "bytes": len(data), "base64_length": len(b64),
                       "chunk_count": len(chunks)})
    chunk_rows.extend({"image_id": image_id, "chunk_no": i, "chunk": c} for i, c in enumerate(chunks, start=1))

image_schema = StructType([StructField(c, StringType()) for c in IMAGE_COLUMNS]
                          + [StructField(c, IntegerType()) for c in ("bytes", "base64_length", "chunk_count")])
chunk_schema = StructType([StructField("image_id", StringType()), StructField("chunk_no", IntegerType()),
                           StructField("chunk", StringType())])
for name, rows, schema in [("report_image", image_rows, image_schema), ("report_image_chunk", chunk_rows, chunk_schema)]:
    table = f"{TABLE_PREFIX}_{name}"
    df = (spark.createDataFrame(rows, schema=schema)
          .withColumn("_run_id", F.lit(RUN_ID))
          .withColumn("_ingested_at", F.lit(RUN_TS).cast(TimestampType())))
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
    print(f"{table}: {spark.read.table(table).count()} rows")
n_images, n_chunks = len(image_rows), len(chunk_rows)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## 3. Data quality checks

# CELL ********************

dq = Results(run_id=RUN_ID, layer="bronze")
counts = {}
for name, contract in SEED_CONTRACT.items():
    present = name in dfs
    dq.check(f"seed_{name}_present", present, "hard")
    if not present:
        continue
    df = dfs[name]
    n = df.count()
    counts[f"{TABLE_PREFIX}_{name}"] = n
    missing = [c for c in contract["required"] if c not in df.columns]
    dq.check(f"seed_{name}_required_columns", not missing, "hard", value=",".join(missing) or None)
    dq.check(f"seed_{name}_count_eq_file", n == len(seeds[name][1]), "hard", value=f"{n}/{len(seeds[name][1])}")
    dq.check(f"seed_{name}_min_rows", n >= contract["min_rows"], "hard", value=n)
    if not missing:
        key = contract["key"]
        dups = n - df.select(*key).distinct().count()
        nulls = df.filter(" OR ".join(f"{k} IS NULL" for k in key)).count()
        dq.check(f"seed_{name}_no_dup_key", dups == 0, "hard", value=dups)
        dq.check(f"seed_{name}_no_null_key", nulls == 0, "hard", value=nulls)

dq.check("seed_report_images_columns", not missing_image_columns, "hard", value=",".join(missing_image_columns) or None)
dq.check("seed_report_images_files_exist", not missing_files, "hard", value=",".join(missing_files) or n_images)
dq.check("seed_report_images_roundtrip", not roundtrip_errors, "hard", value=",".join(roundtrip_errors) or n_chunks)
image_ids = [r["image_id"] for r in image_rows]
dq.check("seed_report_images_no_dup_id", len(image_ids) == len(set(image_ids)), "hard", value=n_images)
dq.check("seed_report_images_max_12", n_images <= MAX_IMAGES, "warning", value=n_images)
counts[f"{TABLE_PREFIX}_report_image"] = n_images
counts[f"{TABLE_PREFIX}_report_image_chunk"] = n_chunks

for name in dfs:
    if name not in SEED_CONTRACT:
        counts[f"{TABLE_PREFIX}_{name}"] = dfs[name].count()
        print(f"Note: {name}.csv has no contract in SEED_CONTRACT; loaded without key checks")

if WRITE_DQ:
    dq.write(spark)
dq.raise_on_hard_failures()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

exit_value = {"run_id": RUN_ID, "seed_files": len(seeds), **counts, **dq.summary()}
print(json.dumps(exit_value, indent=2))
notebookutils.notebook.exit(json.dumps(exit_value))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

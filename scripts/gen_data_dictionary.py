"""Generate docs/data-dictionary.md from the TMDL copy and wh_gold column types (T-38).

Usage: python scripts/gen_data_dictionary.py <repo root> <types file>
The types file is the UTF-16 output of `sqlcmd ... -W -s "|" -h -1 -u -o <file>` with one `table|column|type` row
per Gold column (INFORMATION_SCHEMA.COLUMNS, schema dbo) and `ROWS|table|count` rows for row counts.
"""

import re
import sys
from datetime import date
from pathlib import Path

repo = Path(sys.argv[1])
types_file = Path(sys.argv[2])
out = repo / "docs" / "data-dictionary.md"
tables_dir = repo / "fabric" / "sm_u2_live.SemanticModel" / "definition" / "tables"

gold_types: dict[tuple[str, str], str] = {}
row_counts: dict[str, str] = {}
for line in types_file.read_text(encoding="utf-16").splitlines():
    parts = [p.strip() for p in line.split("|")]
    if len(parts) != 3 or not parts[0]:
        continue
    if parts[0] == "ROWS":
        row_counts[parts[1]] = parts[2]
    else:
        gold_types[(parts[0], parts[1])] = parts[2]


def unquote(name: str) -> str:
    name = name.strip()
    return name[1:-1].replace("''", "'") if name.startswith("'") and name.endswith("'") else name


def parse_table(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    table = {"name": None, "description": "", "hidden": False, "columns": [], "measures": [], "calculated": False}
    doc: list[str] = []
    current = None
    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        indent = len(raw) - len(raw.lstrip("\t"))
        if s.startswith("///"):
            doc.append(s[3:].strip())
        elif indent == 0 and s.startswith("table "):
            table["name"] = unquote(s[6:])
            table["description"] = " ".join(doc)
            doc = []
            current = table
        elif indent == 1 and s.startswith("column "):
            name = unquote(re.split(r"\s=\s", s[7:], maxsplit=1)[0])
            current = {
                "kind": "column",
                "name": name,
                "description": " ".join(doc),
                "hidden": False,
                "dataType": "",
                "sortBy": "",
                "category": "",
                "format": "",
            }
            table["columns"].append(current)
            doc = []
        elif indent == 1 and s.startswith("measure "):
            head = s[8:]
            name_part, _, expr = head.partition(" = ")
            expr_lines = [expr] if expr.strip() else []
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                nind = len(nxt) - len(nxt.lstrip("\t"))
                if nxt.strip() == "" or nind >= 3:
                    if nxt.strip():
                        expr_lines.append(nxt.strip("\t").rstrip())
                    j += 1
                    continue
                break
            current = {
                "kind": "measure",
                "name": unquote(name_part),
                "description": " ".join(doc),
                "expression": "\n".join(expr_lines).strip(),
                "format": "",
                "folder": "",
                "hidden": False,
            }
            table["measures"].append(current)
            doc = []
            i = j - 1
        elif indent == 1 and s.startswith("partition ") and "calculated" in s:
            table["calculated"] = True
        elif indent == 1 and s == "isHidden":
            table["hidden"] = True
        elif indent == 2 and current is not None and current is not table:
            if s == "isHidden":
                current["hidden"] = True
            elif s.startswith("dataType:"):
                current["dataType"] = s.split(":", 1)[1].strip()
            elif s.startswith("sortByColumn:"):
                current["sortBy"] = s.split(":", 1)[1].strip()
            elif s.startswith("dataCategory:"):
                current["category"] = s.split(":", 1)[1].strip()
            elif s.startswith("formatString:"):
                current["format"] = s.split(":", 1)[1].strip()
            elif s.startswith("displayFolder:"):
                current["folder"] = s.split(":", 1)[1].strip()
        elif indent == 1 and s.startswith("isHidden"):
            table["hidden"] = True
        i += 1
    return table


def cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


tables = [parse_table(p) for p in sorted(tables_dir.glob("*.tmdl"))]
order = [
    "fact_performance",
    "fact_show",
    "dim_show",
    "dim_song",
    "dim_album",
    "dim_tour",
    "dim_venue",
    "dim_date",
    "dq_run_log",
    "report_image",
    "report_image_chunk",
]
gold = sorted([t for t in tables if t["name"] in order], key=lambda t: order.index(t["name"]))
params = [t for t in tables if t["name"] not in order]

md: list[str] = []
md.append("# Data dictionary")
md.append("")
md.append("Generated in T-38 from the TMDL copy `fabric/sm_u2_live.SemanticModel/` (descriptions set through the")
md.append("Power BI modeling MCP) and the column types of warehouse `wh_gold` (`INFORMATION_SCHEMA.COLUMNS`). Specs:")
md.append("`docs/specs/SPEC-04-gold.md` (tables, rules) and `docs/specs/SPEC-05-semantic-model.md` (model, measures).")
md.append(f"Row counts are from Gold as of {date.today().isoformat()}. Regenerate after any model change.")
md.append("")
md.append(
    "Conventions: `*_key` surrogate keys (SHA2_256 of the natural id, `-1` = Unknown member), `*_id` natural ids,"
)
md.append("`_built_at` build timestamp (UTC). Hidden = hidden in the report field list (still usable in measures).")
md.append(
    "Default exclusion: every song-level measure counts *full* performances only (no snippets, tapes or fragments)."
)
md.append("")
md.append("## Tables")
md.append("")
md.append("| Table | Rows | Hidden | Description |")
md.append("| --- | --- | --- | --- |")
for t in gold:
    hidden = "yes" if t["hidden"] else ""
    md.append(f"| `{t['name']}` | {row_counts.get(t['name'], '')} | {hidden} | {cell(t['description'])} |")
for t in params:
    md.append(
        f"| `{t['name']}` | — | | Field parameter (calculated table) for a report choose-your-axis/measure control. |"
    )
md.append("")
md.append(
    "Relationships (single direction, many-to-one): `fact_performance` and `fact_show` → `dim_date` (`date_key`),"
)
md.append(
    "`dim_tour` (`tour_key`), `dim_venue` (`venue_key`), `dim_show` (`show_key`); `fact_performance` → `dim_song`"
)
md.append("(`song_key`); `dim_song` → `dim_album` (`album_key`). `dim_tour[album_promoted_key]` has no relationship:")
md.append("`Promoted Album Share %` applies it with `TREATAS`;")
md.append("`report_image_chunk` → `report_image` (`image_id`).")
md.append("")
md.append("## Columns")
for t in gold:
    md.append("")
    md.append(f"### `{t['name']}`")
    md.append("")
    md.append("| Column | Warehouse type | Hidden | Description |")
    md.append("| --- | --- | --- | --- |")
    for c in t["columns"]:
        extra = []
        if c["sortBy"]:
            extra.append(f"sorted by `{c['sortBy']}`")
        if c["category"]:
            extra.append(f"data category {c['category']}")
        desc = c["description"] or ("Build timestamp (UTC)." if c["name"] == "_built_at" else "")
        if extra:
            desc = (desc + " " if desc else "") + "(" + "; ".join(extra) + ")"
        sql_type = gold_types.get((t["name"], c["name"]), "")
        hidden = "yes" if c["hidden"] else ""
        md.append(f"| `{c['name']}` | {sql_type} | {hidden} | {cell(desc)} |")

md.append("")
md.append("## Measures")
measures = [(t["name"], m) for t in tables for m in t["measures"]]
folders = sorted({m["folder"] for _, m in measures})
for folder in folders:
    md.append("")
    md.append(f"### {folder.replace(chr(92), ' / ')}")
    md.append("")
    md.append("| Measure | Home table | Format | Description |")
    md.append("| --- | --- | --- | --- |")
    for home, m in sorted((x for x in measures if x[1]["folder"] == folder), key=lambda x: x[1]["name"]):
        md.append(
            f"| `{m['name']}` | `{home}` | `{cell(m['format'])}` | {cell(m['description'])} |"
            if m["format"]
            else f"| `{m['name']}` | `{home}` | | {cell(m['description'])} |"
        )

md.append("")
md.append("## Measure definitions (DAX)")
md.append("")
md.append("Long markup measures (`Tour Icon SVG`) are shortened here; the full text is in the TMDL copy.")
for _home, m in sorted(measures, key=lambda x: (x[1]["folder"], x[1]["name"])):
    expr = m["expression"]
    if len(expr) > 1200:
        expr = expr[:400] + "\n    -- ... (shortened, see TMDL)"
    md.append("")
    md.append(f"**{m['name']}**")
    md.append("")
    md.append("```dax")
    md.append(expr)
    md.append("```")

out.write_text("\n".join(md) + "\n", encoding="utf-8")
n_columns = sum(len(t["columns"]) for t in gold)
print(f"tables {len(tables)} (gold {len(gold)}, params {len(params)}), columns {n_columns}, measures {len(measures)}")

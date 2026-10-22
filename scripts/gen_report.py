"""Generate the PBIR pages of rpt_u2_live from the wireframes (docs/design/wireframes.md).

Why a generator: no visual was ever created in Desktop to copy from, and ~60 visuals share the same formatting.
Every visual gets a stable name (folder name), position on the 8 px grid, alt text and tab order.
Writes into fabric/rpt_u2_live.Report/:
  definition/report.json            theme (RegisteredResources/u2-theme.json), registered images, custom visuals
  definition/reportExtensions.json  report-level measures (HTML blocks, placeholders until T-35)
  definition/pages/<page>/...       page.json + visuals/<visual>/visual.json
  StaticResources/RegisteredResources/<image files>
Usage: python scripts/gen_report.py [--pages p00_spike,p01_overview,...]
"""

import argparse
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "fabric" / "rpt_u2_live.Report"
DEF = REPORT / "definition"
RES = REPORT / "StaticResources" / "RegisteredResources"
IMAGES = ROOT / "docs" / "design" / "images"


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
S_VISUAL = f"{SCHEMA}/visualContainer/2.4.0/schema.json"
S_PAGE = f"{SCHEMA}/page/2.1.0/schema.json"
S_PAGES = f"{SCHEMA}/pagesMetadata/1.1.0/schema.json"
S_EXT = f"{SCHEMA}/reportExtension/1.0.0/schema.json"

HTML = "htmlContent443BE3AD55E043BF878BED274D3A6865"  # HTML Content Secure (certified)
DENEB = "deneb7E15AEF80B9E4D4F8E12924291ECE89A"  # Deneb (certified)

T = {
    "bg": "#0F1115",
    "surface": "#181B21",
    "surface2": "#20242C",
    "border": "#2A2F38",
    "text": "#ECEDEF",
    "muted": "#A3A9B3",
    "accent": "#F2A93B",
    "neutral": "#6E7581",
    "d1": "#6FA8DC",
    "d1b": "#4F7FAE",
    "d2": "#93C47D",
    "d3": "#E06666",
    "d4": "#B4A7D6",
    "d6": "#F6B26B",
}


# ---------------------------------------------------------------- expression helpers
def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def color(hexv):
    return {"solid": {"color": lit(hexv)}}


def col(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(entity, prop, ext=False):
    src = {"Schema": "extension", "Entity": entity} if ext else {"Entity": entity}
    return {"Measure": {"Expression": {"SourceRef": src}, "Property": prop}}


def named(field, display):
    return {"__display": display, **field}


def proj(field, active=None):
    field = dict(field)
    display = field.pop("__display", None)
    kind = next(k for k in ("Column", "Measure", "Aggregation") if k in field)
    inner = field[kind]["Expression"] if kind == "Aggregation" else field[kind]
    ent = (inner["Column"] if kind == "Aggregation" else inner)["Expression"]["SourceRef"]["Entity"]
    prop = inner["Column"]["Property"] if kind == "Aggregation" else inner["Property"]
    qref = f"{ent}.{prop}" if kind != "Aggregation" else f"Min({ent}.{prop})"
    p = {"field": field, "queryRef": qref, "nativeQueryRef": prop}
    if display:
        p["displayName"] = display
    if active is not None:
        p["active"] = active
    return p


def props(**kw):
    return [{"properties": {k: v for k, v in kw.items()}}]


# ---------------------------------------------------------------- report-level measures
EXT_MEASURES = {}  # entity -> list of measures


def ext_measure(entity, name, expression, data_type="Text", refs=(), category=None, description=None):
    m = {"name": name, "dataType": data_type, "expression": expression}
    if category:
        m["dataCategory"] = category
    if description:
        m["description"] = description
    if refs:
        m["references"] = {"measures": [{"entity": e, "name": n} for e, n in refs]}
    EXT_MEASURES.setdefault(entity, []).append(m)
    return meas(entity, name, ext=True)


def placeholder(name, text=None):
    """Report-level stand-in 'ph <name>' for the model text measure [<name>] (data-analyst, T-35).

    Since T-35 it only forwards to the model measure; `text` (the old sketch wording) is ignored.
    """
    return ext_measure(
        "fact_show",
        f"ph {name}",
        f"[{name}]",
        refs=[("fact_show", name)],
        description=f"Bound to model measure [{name}] (T-35); kept so the text cards keep their binding.",
    )


# ---------------------------------------------------------------- visual builder
class Page:
    def __init__(self, name, display, drill=None, hidden=False):
        self.name, self.display, self.drill, self.hidden = name, display, drill, hidden
        self.visuals, self.z = [], 0

    def add(
        self,
        vname,
        vtype,
        x,
        y,
        w,
        h,
        roles=None,
        objects=None,
        vco=None,
        alt=None,
        title=None,
        filters=None,
        sort=None,
        tab=True,
        extra=None,
        fparams=None,
    ):
        self.z += 1
        visual = {"visualType": vtype}
        if roles:
            visual["query"] = {"queryState": {r: {"projections": [proj(f) for f in fs]} for r, fs in roles.items()}}
            for r, pcol in (fparams or {}).items():  # field parameter: projections hold the default field
                visual["query"]["queryState"][r]["fieldParameters"] = [{"parameterExpr": pcol, "index": 0, "length": 1}]
            if sort:
                visual["query"]["sortDefinition"] = {
                    "sort": [
                        {"field": {k: v for k, v in f.items() if k != "__display"}, "direction": d} for f, d in sort
                    ],
                    "isDefaultSort": False,
                }
        if objects:
            visual["objects"] = objects
        vco = dict(vco or {})
        vco.setdefault("subTitle", props(show=lit(False)))
        vco.setdefault("visualHeader", props(show=lit(False)))
        if isinstance(title, dict):  # title from a measure (Top N labels with totals)
            vco.setdefault("title", props(show=lit(True), text={"expr": title}))
        else:
            vco.setdefault("title", props(show=lit(bool(title)), **({"text": lit(title)} if title else {})))
        if alt:
            vco.setdefault("general", props(altText=lit(alt)))
        visual["visualContainerObjects"] = vco
        if extra:
            visual.update(extra)
        v = {
            "$schema": S_VISUAL,
            "name": vname,
            "position": {
                "x": x,
                "y": y,
                "z": self.z * 1000,
                "height": h,
                "width": w,
                "tabOrder": self.z * 1000 if tab else 99000 + self.z,
            },
            "visual": visual,
        }
        if filters:
            v["filterConfig"] = {"filters": filters}
        self.visuals.append(v)
        return v


def basic_filter(field, values, name):
    kind = "Column" if "Column" in field else "Measure"
    ent = field[kind]["Expression"]["SourceRef"]["Entity"]
    return {
        "name": name,
        "field": field,
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "t", "Entity": ent, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "In": {
                            "Expressions": [
                                {
                                    kind: {
                                        "Expression": {"SourceRef": {"Source": "t"}},
                                        "Property": field[kind]["Property"],
                                    }
                                }
                            ],
                            "Values": [[{"Literal": {"Value": "'" + v + "'"}}] for v in values],
                        }
                    }
                }
            ],
        },
    }


# ---------------------------------------------------------------- common elements
REGISTERED = set()


def image(page, vname, file, x, y, w, h, alt, scaling="Fill", decorative=True):
    REGISTERED.add(file)
    return page.add(
        vname,
        "image",
        x,
        y,
        w,
        h,
        alt=("Decorative: " + alt) if decorative else alt,
        tab=not decorative,
        objects={
            "general": props(
                imageUrl={
                    "expr": {
                        "ResourcePackageItem": {
                            "PackageName": "RegisteredResources",
                            "PackageType": 1,
                            "ItemName": file,
                        }
                    }
                }
            ),
            "imageScaling": props(imageScalingType=lit(scaling)),
        },
        vco={"background": props(show=lit(False)), "visualHeader": props(show=lit(False))},
    )


def scrim(page, vname, direction, x, y, w, h):
    return image(page, vname, f"scrim_from_{direction}.png", x, y, w, h, "gradient behind text", scaling="Fit")


def text(page, vname, x, y, w, h, runs, align="left", tab=False):
    """runs: list of paragraphs, each a list of (text, style dict). No padding, so small boxes do not scroll."""
    paragraphs = [
        {"textRuns": [{"value": t, "textStyle": s} for t, s in para], "horizontalTextAlignment": align} for para in runs
    ]
    return page.add(
        vname,
        "textbox",
        x,
        y,
        w,
        h,
        tab=tab,
        objects={"general": props(paragraphs=paragraphs)},
        vco={
            "background": props(show=lit(False)),
            "padding": props(top=lit(0), bottom=lit(0), left=lit(0), right=lit(0)),
        },
    )


def style(size=10, color_=T["muted"], family="Segoe UI", weight=None, italic=False):
    s = {"fontFamily": family, "fontSize": f"{size}pt", "color": color_}
    if weight:
        s["fontWeight"] = weight
    if italic:
        s["fontStyle"] = "italic"
    return s


DIN = "DIN, Bahnschrift, 'Segoe UI', sans-serif"


def wrap(field, before, after, suffix, description):
    """Report-level measure '<measure> · <suffix>' = before & [measure] & after (HTML around a text measure)."""
    m = field["Measure"]
    name, ent = m["Property"], m["Expression"]["SourceRef"]["Entity"]
    is_ext = m["Expression"]["SourceRef"].get("Schema") == "extension"
    new = ext_measure(
        FS,
        f"{name} · {suffix}",
        f'"{before}" & [{name}] & "{after}"',
        refs=[] if is_ext else [(ent, name)],
        description=description,
    )
    if is_ext:
        EXT_MEASURES[FS][-1]["references"] = {"measures": [{"schema": "extension", "entity": ent, "name": name}]}
    return new


def card_text(
    page,
    vname,
    x,
    y,
    w,
    h,
    field,
    size=32,
    color_=T["text"],
    family=DIN,
    italic=False,
    alt=None,
    weight=600,
    line=1.1,
):
    """A text measure (headline, callout, note) shown left-aligned and wrapped in HTML Content Secure.

    The wrapper fixes the typography and clips to the box (height minus a safety margin), so the visual never shows
    a scrollbar: if a text is longer than the box it is cut at a line, and the fix is a shorter text measure.
    """
    css = (
        f"font-family:{family.replace(chr(39), '')};font-size:{size}px;line-height:{line};color:{color_};"
        f"font-weight:{weight};{'font-style:italic;' if italic else ''}max-height:{h - 8}px;overflow:hidden"
    )
    wrapper = wrap(field, f"<div style='{css}'>", "</div>", vname, "Typography wrapper (presentation only).")
    return html(page, vname, x, y, w, h, wrapper, alt=alt or "Text", clip=False)


def html(page, vname, x, y, w, h, field, alt, filters=None, clip=True, links=False):
    """HTML Content Secure visual. clip=True wraps the measure in a fixed-height, overflow-hidden div."""
    if clip:
        field = wrap(
            field,
            f"<div style='height:{h - 8}px;overflow:hidden'>",
            "</div>",
            vname,
            "Clipping wrapper so the HTML visual never scrolls (presentation only).",
        )
    return page.add(
        vname,
        HTML,
        x,
        y,
        w,
        h,
        roles={"content": [field]},
        alt=alt,
        filters=filters,
        objects={
            "contentFormatting": props(
                format=lit("html"),
                fontFamily=lit("Segoe UI"),
                fontSize=lit(10),
                fontColour=color(T["muted"]),
                showRawHtml=lit(False),
                hyperlinks=lit(links),
            )
        },
        tab=True,
        vco={
            "background": props(show=lit(False)),
            "padding": props(top=lit(0), bottom=lit(0), left=lit(0), right=lit(0)),
        },
    )


def deneb(page, vname, x, y, w, h, fields, spec, alt, config=None):
    return page.add(
        vname,
        DENEB,
        x,
        y,
        w,
        h,
        roles={"dataset": fields},
        alt=alt,
        objects={
            "vega": props(
                provider=lit("vegaLite"),
                jsonSpec=lit(json.dumps(spec, separators=(",", ":"))),
                jsonConfig=lit(json.dumps(config or {}, separators=(",", ":"))),
                renderMode=lit("svg"),
                enableTooltips=lit(True),
            )
        },
        vco={"background": props(show=lit(False))},
    )


def nav(page, x=40, y=12, w=640):
    return page.add(
        f"{page.name[:3]}_nav",
        "pageNavigator",
        x,
        y,
        w,
        44,
        alt="Report pages",
        objects={
            "text": [
                {
                    "properties": {
                        "fontColor": color(T["muted"]),
                        "fontSize": lit(10),
                        "fontFamily": lit("Segoe UI"),
                        "verticalAlignment": lit("middle"),
                        "leftMargin": lit(0),
                        "rightMargin": lit(0),
                    }
                },
                {"properties": {"fontColor": color(T["accent"]), "bold": lit(True)}, "selector": {"id": "selected"}},
            ],
            "fill": props(show=lit(False)),
            "border": props(show=lit(False)),
            "outline": props(show=lit(False)),
            "accentBar": [
                {
                    "properties": {
                        "show": lit(True),
                        "color": color(T["accent"]),
                        "position": lit("Bottom"),
                        "width": lit(2),
                    },
                    "selector": {"id": "selected"},
                }
            ],
            "pages": [
                {"properties": {"showHiddenPages": lit(False)}},
                {"properties": {"showPage": lit(False)}, "selector": {"id": "p07_song_detail"}},
                {"properties": {"showPage": lit(False)}, "selector": {"id": "p08_show_detail"}},
                {"properties": {"showPage": lit(False)}, "selector": {"id": "p00_spike"}},
            ],
        },
        vco={"background": props(show=lit(False))},
    )


def back_button(page, x, y):
    return page.add(
        f"{page.name[:3]}_back",
        "actionButton",
        x,
        y,
        100,
        32,
        alt="Back to the previous page",
        objects={
            "icon": props(shapeType=lit("back"), lineColor=color(T["accent"]), iconSize=lit(14)),
            "text": button_state(show=lit(True), text=lit("Back"), fontColor=color(T["text"]), fontSize=lit(10)),
            "outline": props(show=lit(False)),
            "fill": props(show=lit(False)),
        },
        vco={"visualLink": props(show=lit(True), type=lit("Back"))},
    )


TOPN_COLUMNS = (
    "REMOVEFILTERS ( dim_song[song_title] ), REMOVEFILTERS ( dim_song[full_performances] ), "
    "REMOVEFILTERS ( dim_venue[city_name] ), REMOVEFILTERS ( fact_performance[guest_artist] ), "
    "REMOVEFILTERS ( dim_tour[tour_name_display] )"
)


def title_measure(name, prefix, count_expr, suffix="", refs=()):
    """Visual title stating the Top N cut and the total, e.g. 'Other people's songs: top 3 of 179 covers'."""
    return ext_measure(
        FS,
        name,
        f'"{prefix}" & FORMAT ( CALCULATE ( {count_expr}, {TOPN_COLUMNS} ), "#,0", "en-US" ) & "{suffix}"',
        refs=refs,
        description="Visual title with the Top N cut and the total (presentation only).",
    )


def button_state(**kw):
    """Action-button formatting for the default, hover and pressed states."""
    return [{"properties": kw, "selector": {"id": s}} for s in ("default", "hover", "press")]


FOOTER = "Data: setlist.fm, MusicBrainz · photos: Wikimedia Commons, credits on the About page"


def footer(page, x=40, w=900, note=None):
    words = f"{note} · {FOOTER}" if note else FOOTER
    text(page, f"{page.name[:3]}_footer", x, 696, w, 20, [[(words, style(8))]])


# ---------------------------------------------------------------- pages
def page_spike():
    p = Page("p00_spike", "Image spike (T-32)", hidden=True)
    b64 = SPIKE_JPEG
    glyph = (IMAGES / "glyph_zoo_tv.svg").read_text(encoding="utf-8").strip().replace('"', "'")
    expr = (
        "\"<div style='font-family:Segoe UI;color:#ECEDEF;font-size:13px'>"
        "<p><b>1 · inline SVG:</b> " + glyph.replace('"', '""') + "</p>"
        "<p><b>2 · SVG data URI in img:</b> <img width='48' src='data:image/svg+xml;utf8,"
        + glyph.replace("#", "%23").replace('"', '""')
        + "'></p>"
        "<p><b>3 · base64 JPEG literal in img:</b><br><img width='160' src='data:image/jpeg;base64," + b64 + "'></p>"
        '<p><b>4 · photo from the model ([Image Data URI]):</b><br>" & '
        'IF ( ISBLANK ( [Image Data URI] ), "<i>report_image is empty: load seeds/report_images.csv first</i>", '
        '"<img width=\'240\' src=\'" & [Image Data URI] & "\'>" ) & "</p></div>"'
    )
    m = ext_measure("fact_show", "Spike HTML", expr, refs=[("fact_show", "Image Data URI")])
    html(
        p,
        "p00_html_spike",
        40,
        40,
        560,
        500,
        m,
        "Spike: four ways of showing images in HTML Content Secure",
        filters=[basic_filter(col("report_image", "image_id"), ["photo_zoo_tv_1992_kiel"], "spikeImage")],
    )
    path = next(r for r in GLYPH_PATHS if r["tour_name"] == "Zoo TV")["path_unit"]
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"name": "dataset"},
        "width": "container",
        "height": "container",
        "layer": [
            {
                "mark": {"type": "bar", "color": T["d1"]},
                "encoding": {
                    "x": {
                        "field": "year",
                        "type": "ordinal",
                        "axis": {"labelColor": T["muted"], "values": [1980, 1990, 2000, 2010, 2020], "title": None},
                    },
                    "y": {"field": "Shows", "type": "quantitative", "axis": None},
                },
            },
            {
                "mark": {
                    "type": "point",
                    "shape": path,
                    "size": 900,
                    "filled": False,
                    "stroke": T["text"],
                    "strokeWidth": 2,
                },
                "encoding": {"x": {"datum": 1992, "type": "ordinal"}, "y": {"datum": 0, "type": "quantitative"}},
            },
            {
                "mark": {
                    "type": "image",
                    "width": 48,
                    "height": 48,
                    "url": "data:image/svg+xml;utf8," + glyph.replace("#", "%23"),
                },
                "encoding": {"x": {"datum": 2009, "type": "ordinal"}, "y": {"datum": 60, "type": "quantitative"}},
            },
        ],
        "config": {"view": {"stroke": None}, "background": None},
    }
    p.add(
        "p00_matrix_plain",
        "pivotTable",
        40,
        560,
        560,
        140,
        roles={
            "Rows": [col("dim_album", "album_label")],
            "Columns": [col("dim_date", "decade")],
            "Values": [meas(FP, "Album Share %")],
        },
        alt="Spike: plain matrix",
        filters=[basic_filter(col("dim_album", "album_type"), ["studio"], "studio")],
    )
    deneb(
        p,
        "p00_deneb_spike",
        640,
        40,
        600,
        640,
        [col("dim_date", "year"), meas("fact_show", "Shows")],
        spec,
        "Spike: Deneb bars with a path glyph (Zoo TV, 1992) and an SVG data-URI image (2009)",
    )
    return p


# ---------------------------------------------------------------- shared measures and specs
FS, FP = "fact_show", "fact_performance"
TOUR_START = [
    ("Early Days", 1976),
    ("U2-3", 1979),
    ("11 O'Clock Tick Tock", 1980),
    ("Boy", 1980.6),
    ("October Tour", 1981.6),
    ("Pre-War Tour", 1982.9),
    ("War", 1983.2),
    ("The Unforgettable Fire", 1984.7),
    ("A Conspiracy of Hope", 1986.4),
    ("Joshua Tree Promo Tour", 1987.2),
    ("The Joshua Tree", 1987.6),
    ("Lovetown", 1989.7),
    ("Zoo TV", 1992.2),
    ("Popmart Tour", 1997.3),
    ("Elevation", 2001.2),
    ("How to Dismantle an Atomic Bomb Promo Tour", 2004.8),
    ("Vertigo", 2005.2),
    ("U2 360°", 2009.5),
    ("iNNOCENCE + eXPERIENCE Tour", 2015.4),
    ("The Joshua Tree Tour 2017", 2017.4),
    ("eXPERIENCE + iNNOCENCE Tour", 2018.4),
    ("The Joshua Tree Tour 2019", 2019.8),
    ("U2:UV Achtung Baby Live at Sphere", 2023.7),
    ("Carnival De Luz Promo", 2026.4),
]
ERA_ORDER = {
    "1976-1980 Beginnings": 1,
    "1980-1985 Boy to Unforgettable Fire": 2,
    "1986-1990 Joshua Tree years": 3,
    "1992-1998 Zoo TV and PopMart": 4,
    "2001-2006 Elevation and Vertigo": 5,
    "2009-2011 U2 360": 6,
    "2015-2019 Innocence and Experience": 7,
    "2023-present Sphere and after": 8,
}


ERA_YEARS = [(1980, 1), (1985, 2), (1991, 3), (1999, 4), (2007, 5), (2013, 6), (2021, 7), (9999, 8)]


def tour_icon_values(rows=2, gap=1.6):
    """Inline lookup for Deneb: tour -> unit path, start year (decimal) and stagger row (at most `rows` rows)."""
    paths = {r["tour_name"]: r["path_unit"] for r in GLYPH_PATHS}
    rows_end, out = [-99.0] * rows, []
    for tour, yr in TOUR_START:
        row = max(range(rows), key=lambda i: yr - rows_end[i])  # the row with the most room
        rows_end[row] = yr
        out.append({"tour_name": tour, "start": yr, "row": row, "path": paths[tour]})
    return out


def years_spec(measure_name, label_peak=True):
    """Deneb (Vega-Lite): one bar per year as a single series (explicit x/x2 so bars never overlap, ~30% gap), era
    shading by colour on that series, busiest year in accent with its label above the bar, tour glyphs under the axis.
    Years without shows stay empty."""
    era_expr = " : ".join(f"datum.year <= {y} ? {i}" for y, i in ERA_YEARS[:-1]) + " : 8"
    domain = [1975.5, 2027]
    xscale = {"domain": domain, "nice": False, "zero": False}
    bars = {
        "mark": {"type": "bar", "cornerRadiusEnd": 1},
        "encoding": {
            "x": {
                "field": "x0",
                "type": "quantitative",
                "scale": xscale,
                "axis": {
                    "values": [1980, 1990, 2000, 2010, 2020],
                    "format": "d",
                    "labelColor": T["muted"],
                    "labelFontSize": 11,
                    "domain": False,
                    "ticks": False,
                    "grid": False,
                    "title": None,
                    "labelPadding": 4,
                },
            },
            "x2": {"field": "x1"},
            "y2": {"datum": 0},
            "y": {"field": "h", "type": "quantitative", "axis": None, "scale": {"domain": [0, 1]}},
            "color": {
                "field": "band",
                "type": "nominal",
                "legend": None,
                "scale": {"domain": ["peak", "a", "b"], "range": [T["accent"], T["d1"], T["d1b"]]},
            },
            "tooltip": [
                {"field": "year", "title": "Year", "format": "d"},
                {"field": "total", "title": measure_name, "format": ",d"},
            ],
        },
    }
    layers = [bars]
    if label_peak:
        layers.append(
            {
                "transform": [{"filter": "datum.band == 'peak'"}],
                "mark": {
                    "type": "text",
                    "align": "center",
                    "baseline": "bottom",
                    "dy": -4,
                    "color": T["accent"],
                    "fontSize": 12,
                    "fontStyle": "italic",
                    "fontWeight": 600,
                },
                "encoding": {
                    "x": {"field": "year", "type": "quantitative", "scale": xscale},
                    "y": {"field": "h", "type": "quantitative", "scale": {"domain": [0, 1]}},
                    "text": {"field": "label"},
                },
            }
        )
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"name": "dataset"},
        "width": "container",
        "background": None,
        "autosize": {"type": "fit-x", "contains": "padding"},
        "config": {"view": {"stroke": None}, "font": "Segoe UI"},
        "vconcat": [
            {
                "height": 150,
                "width": "container",
                "transform": [
                    {"aggregate": [{"op": "sum", "field": measure_name, "as": "total"}], "groupby": ["year"]},
                    {"filter": "datum.total > 0"},
                    {"joinaggregate": [{"op": "max", "field": "total", "as": "max_total"}]},
                    {"calculate": "datum.total / (datum.max_total * 1.18)", "as": "h"},
                    {"calculate": "datum.year - 0.36", "as": "x0"},
                    {"calculate": "datum.year + 0.36", "as": "x1"},
                    {"calculate": era_expr, "as": "era"},
                    {
                        "calculate": "datum.total == datum.max_total ? 'peak' : datum.era % 2 == 1 ? 'a' : 'b'",
                        "as": "band",
                    },
                    {"calculate": "format(datum.total, ',') + ' in ' + datum.year", "as": "label"},
                ],
                "layer": layers,
            },
            {
                "height": 44,
                "width": "container",
                "data": {"values": tour_icon_values()},
                "mark": {"type": "point", "filled": False, "stroke": T["text"], "strokeWidth": 1.5, "size": 200},
                "encoding": {
                    "x": {"field": "start", "type": "quantitative", "scale": xscale, "axis": None},
                    "y": {"field": "row", "type": "ordinal", "axis": None},
                    "shape": {"field": "path", "type": "nominal", "scale": None, "legend": None},
                    "tooltip": [{"field": "tour_name", "title": "Tour"}],
                },
            },
        ],
        "resolve": {"scale": {"x": "independent"}},
        "spacing": 2,
    }


def kpi_tiles_measure():
    icons = {k: svg_inline(f"icon_kpi_{k}.svg", 28) for k in ("shows", "songs", "countries")}

    def tile(icon, value, label, delta, accent=False):
        num_style = "font-family:DIN,Bahnschrift,Segoe UI;font-weight:600;font-size:46px;line-height:1;color:" + (
            T["accent"] if accent else T["text"]
        )
        return (
            f"\"<div style='display:flex;gap:10px;align-items:flex-start'>{icons[icon]}<div>"
            f'<div style=\'{num_style}\'>" & FORMAT ( {value}, "#,0", "en-US" ) & "</div>'
            f"<div style='color:#ECEDEF;font-size:13px'>{label}</div>"
            f'<div style=\'font-size:11px;font-weight:600;color:" & IF ( {delta} > 0, "#93C47D", '
            f'IF ( {delta} < 0, "#E06666", "#A3A9B3" ) ) & "\'>" & '
            f'IF ( ISBLANK ( {delta} ), "all eras", IF ( {delta} > 0, "▲ +", "▼ " ) & '
            f'FORMAT ( {delta}, "#,0", "en-US" ) & " vs previous era" ) & "</div></div></div>"'
        )

    body = (
        "\"<div style='display:flex;gap:28px'>\" & "
        + tile("shows", "[Shows]", "shows", "[Shows vs Previous Era]", True)
        + " & "
        + tile("songs", "[Distinct Songs]", "different songs", "[Distinct Songs vs Previous Era]")
        + " & "
        + tile("countries", "[Countries]", "countries", "[Countries vs Previous Era]")
        + ' & "</div>"'
    )
    return ext_measure(
        FS,
        "KPI Tiles p01",
        body,
        refs=[
            (FS, "Shows"),
            (FP, "Distinct Songs"),
            (FS, "Countries"),
            (FS, "Shows vs Previous Era"),
            (FP, "Distinct Songs vs Previous Era"),
            (FS, "Countries vs Previous Era"),
        ],
        description="HTML: three KPI tiles (icon, number, delta vs previous era) for HTML Content Secure.",
    )


def color_measure(name, expr, refs):
    return ext_measure(
        FS, name, expr, refs=refs, description="Hex colour for conditional formatting (presentation only)."
    )


def fill_by(measure_field):
    return [
        {
            "properties": {"fill": {"solid": {"color": {"expr": measure_field}}}},
            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]},
        }
    ]


def table(
    page, vname, x, y, w, h, fields, alt, sort=None, filters=None, title=None, extra_objects=None, vco=None, widths=None
):
    obj = {
        "columnHeaders": props(fontColor=color(T["muted"]), backColor=color(T["bg"]), wordWrap=lit(False)),
        "values": props(
            wordWrap=lit(False),
            backColorPrimary=color(T["bg"]),
            backColorSecondary=color(T["bg"]),
            fontColorPrimary=color(T["text"]),
            fontColorSecondary=color(T["text"]),
        ),
        "grid": props(
            gridHorizontal=lit(False),
            gridVertical=lit(False),
            rowPadding=lit(2),
            outlineColor=color(T["bg"]),
            imageHeight=lit(18),
            imageWidth=lit(18),
        ),
        "total": props(totals=lit(False)),
    }
    obj.update(extra_objects or {})
    if widths:  # widths: list of pixel widths in field order, so columns never need a horizontal scroll
        obj["columnWidth"] = [
            {"properties": {"value": lit(px)}, "selector": {"metadata": proj(fld)["queryRef"]}}
            for fld, px in zip(fields, widths, strict=True)
        ]
    return page.add(
        vname,
        "tableEx",
        x,
        y,
        w,
        h,
        roles={"Values": fields},
        alt=alt,
        sort=sort,
        filters=filters,
        title=title,
        objects=obj,
        vco={"background": props(show=lit(True), color=color(T["bg"]), transparency=lit(0)), **(vco or {})},
    )


def bar(page, vname, x, y, w, h, cat, val, alt, title=None, filters=None, fill=None, margin=50):
    obj = {
        "labels": props(show=lit(True), color=color(T["text"]), fontSize=lit(10), labelDisplayUnits=lit(1)),
        "valueAxis": props(show=lit(False), gridlineShow=lit(False)),
        "categoryAxis": props(
            show=lit(True),
            labelColor=color(T["text"]),
            fontSize=lit(10),
            showAxisTitle=lit(False),
            maxMarginFactor=lit(margin),
        ),
        "dataPoint": fill if fill else props(fill=color(T["d1"])),
    }
    return page.add(
        vname,
        "clusteredBarChart",
        x,
        y,
        w,
        h,
        roles={"Category": [cat], "Y": [val]},
        alt=alt,
        title=title,
        filters=filters,
        objects=obj,
        sort=[(val, "Descending")],
        vco={"background": props(show=lit(False))},
    )


def photo_card_measure(name, image_id_note, number_expr, caption_expr, refs, height):
    """HTML photo card: base64 photo filling a box of fixed height, a gradient on the lower half, number and caption."""
    expr = (
        f"VAR Img = [Image Data URI] RETURN \"<div style='position:relative;width:100%;height:{height}px;"
        "overflow:hidden;background:#0F1115'>\" & IF ( NOT ISBLANK ( Img ), \"<img src='\" & Img & \"' style='width:"
        f"100%;height:{height}px;object-fit:cover;display:block'>\" ) & "
        "\"<div style='position:absolute;left:0;right:0;bottom:0;height:55%;background:linear-gradient(to bottom, "
        "rgba(15,17,21,0), rgba(15,17,21,.92) 55%)'></div><div style='position:absolute;left:20px;right:20px;"
        "bottom:12px'><div style='font-family:DIN,Bahnschrift,Segoe UI;font-weight:600;font-size:40px;"
        "line-height:1;color:#F2A93B'>\" & "
        + number_expr
        + " & \"</div><div style='color:#ECEDEF;font-size:13px;margin-top:4px'>\" & "
        + caption_expr
        + " & \"</div><div style='color:#A3A9B3;font-size:9px;margin-top:4px'>\" & [Image Credit] & "
        '"</div></div></div>"'
    )
    return ext_measure(
        FS,
        name,
        expr,
        refs=[(FS, "Image Data URI"), (FS, "Image Credit"), *refs],
        description=f"HTML photo card ({image_id_note}): base64 photo, gradient, number, caption, credit.",
    )


def page_header(p, headline, glimpse, x=40, w=600, nav_w=None, h=152):
    """Navigation, then headline (up to two lines) and intro (up to three lines) in one HTML block, so a one-line
    headline leaves no gap above the intro."""
    nav(p, x, 6, nav_w or min(w, 720))
    combined = ext_measure(
        FS,
        f"Header {p.name[:3]}",
        "\"<div style='font-family:DIN,Bahnschrift,Segoe UI;font-size:32px;line-height:1.1;color:#ECEDEF;"
        f'font-weight:600;max-height:72px;overflow:hidden\'>" & [{headline[0]}] & "</div>'
        "<div style='font-family:Segoe UI;font-size:12.5px;line-height:1.5;color:#A3A9B3;margin-top:8px;"
        f'max-height:57px;overflow:hidden\'>" & [{glimpse[0]}] & "</div>"',
        refs=[(FS, headline[0]), (FS, glimpse[0])],
        description="HTML: page headline and intro paragraph from the model text measures (T-35).",
    )
    html(p, f"{p.name[:3]}_headline", x, 54, w, h, combined, alt="Page headline and introduction")


def measure_filter(field, more_than, name, kind=1):
    """Visual filter: measure > more_than (Advanced filter)."""
    ent = field["Measure"]["Expression"]["SourceRef"]["Entity"]
    return {
        "name": name,
        "field": field,
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [
                {"Name": "m", "Entity": ent, "Type": 0}
                | ({"Schema": "extension"} if field["Measure"]["Expression"]["SourceRef"].get("Schema") else {})
            ],
            "Where": [
                {
                    "Condition": {
                        "Comparison": {
                            "ComparisonKind": kind,
                            "Left": {
                                "Measure": {
                                    "Expression": {"SourceRef": {"Source": "m"}},
                                    "Property": field["Measure"]["Property"],
                                }
                            },
                            "Right": {"Literal": {"Value": f"{more_than}L"}},
                        }
                    }
                }
            ],
        },
    }


RANK_COUNT = [0]


def topn_filter(field, by, n, name, ascending=False):
    """Exact Top N: rank measure (ties broken by name) with a visual filter rank <= n."""
    c = field["Column"]
    colref = f"{c['Expression']['SourceRef']['Entity']}[{c['Property']}]"
    m = by["Measure"]["Property"]
    op = "<" if ascending else ">"
    RANK_COUNT[0] += 1
    rank = ext_measure(
        FS,
        f"Rank {RANK_COUNT[0]} {c['Property']} by {m}",
        f"VAR Cur = CALCULATE ( [{m}], REMOVEFILTERS ( dim_date ) ) VAR Me = SELECTEDVALUE ( {colref} ) "
        f"RETURN IF ( NOT ISBLANK ( Cur ) && NOT ISBLANK ( Me ), "
        f"COUNTROWS ( FILTER ( ALLSELECTED ( {colref} ), "
        f"VAR V = CALCULATE ( [{m}], REMOVEFILTERS ( dim_date ) ) RETURN "
        f"NOT ISBLANK ( V ) && "
        f"( V {op} Cur || ( V = Cur && {colref} < Me ) ) ) ) + 1 )",
        data_type="Integer",
        description=f"Rank of {c['Property']} by [{m}] for an exact Top N (ties broken alphabetically).",
    )
    return measure_filter(rank, n, name, kind=4)


def bool_filter(field, value, name):
    ent = field["Column"]["Expression"]["SourceRef"]["Entity"]
    return {
        "name": name,
        "field": field,
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "t", "Entity": ent, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "In": {
                            "Expressions": [
                                {
                                    "Column": {
                                        "Expression": {"SourceRef": {"Source": "t"}},
                                        "Property": field["Column"]["Property"],
                                    }
                                }
                            ],
                            "Values": [[{"Literal": {"Value": "true" if value else "false"}}]],
                        }
                    }
                }
            ],
        },
    }


def gradient(measure_field, metadata, low="#141A22", high="#3A78C0", font=False):
    """Matrix heatmap colours: background low->high; text light on dark cells and dark on bright cells."""

    def rule(lo, hi):
        return {
            "solid": {
                "color": {
                    "expr": {
                        "FillRule": {
                            "Input": measure_field,
                            "FillRule": {
                                "linearGradient2": {
                                    "min": {"color": lit(lo)["expr"]},
                                    "max": {"color": lit(hi)["expr"]},
                                    "nullColoringStrategy": {"strategy": lit("noColor")["expr"]},
                                }
                            },
                        }
                    }
                }
            }
        }

    p = {"backColor": rule(low, high)}
    if font:
        p["fontColor"] = rule(T["text"], T["bg"])
    return {"properties": p, "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": metadata}}


def data_bars(metadata, colour="#2F5F96"):
    return {
        "properties": {
            "dataBars": {
                "positiveColor": color(colour),
                "negativeColor": color(T["d3"]),
                "axisColor": color(T["bg"]),
                "reverseDirection": lit(False),
                "hideText": lit(False),
            }
        },
        "selector": {"metadata": metadata},
    }


def slicer(page, vname, x, y, w, h, field, alt, mode="Dropdown"):
    return page.add(
        vname,
        "slicer",
        x,
        y,
        w,
        h,
        roles={"Values": [field]},
        alt=alt,
        objects={
            "data": props(mode=lit(mode)),
            "header": props(show=lit(False)),
            "items": props(fontColor=color(T["text"]), background=color(T["surface"]), textSize=lit(10)),
        },
        vco={"background": props(show=lit(False))},
    )


def svg_inline(file, size):
    return (
        (IMAGES / file)
        .read_text(encoding="utf-8")
        .strip()
        .replace('"', "'")
        .replace("width='48' height='48'", f"width='{size}' height='{size}'")
    )


def big(value_expr, label, colour=T["accent"], size=40, label_colour=T["text"]):
    return (
        "\"<div><div style='font-family:DIN,Bahnschrift,Segoe UI;font-weight:600;font-size:"
        + str(size)
        + "px;line-height:1;color:"
        + colour
        + "'>\" & "
        + value_expr
        + " & \"</div><div style='font-size:12px;color:"
        + label_colour
        + ";margin-top:4px'>"
        + label
        + '</div></div>"'
    )


def prompt_html(message):
    """Shown on a drill-through page opened without a single item in context."""
    return (
        "\"<div style='font-family:Segoe UI;color:#A3A9B3;font-size:14px;padding-top:8px'>"
        "<div style='font-family:DIN,Bahnschrift,Segoe UI;font-weight:600;font-size:28px;color:#ECEDEF'>"
        f'Nothing selected yet</div>{message}</div>"'
    )


def subtitle(text_):
    return {"subTitle": props(show=lit(True), text=lit(text_), fontColor=color(T["muted"]), fontSize=lit(9))}


def era_button_slicer(page, x, y, w, h):
    """Transparent era buttons laid over the badge images; the selected tile gets an accent ring."""
    eras = list(ERA_ORDER)
    return page.add(
        "p01_era_buttons",
        "advancedSlicerVisual",
        x,
        y,
        w,
        h,
        roles={"Values": [col("dim_tour", "era")]},
        alt="Era filter: one badge per era; click again to show all eras",
        filters=[basic_filter(col("dim_tour", "era"), eras, "eras")],
        objects={
            "layout": props(style=lit("Cards"), rowCount=lit(1), columnCount=lit(8), cellPadding=lit(8)),
            "shapeCustomRectangle": props(tileShape=lit("oval")),
            "value": props(show=lit(False)),
            "label": props(show=lit(False)),
            "fillCustom": props(show=lit(False)),
            "image": props(show=lit(False)),
            "outline": [
                {"properties": {"show": lit(False)}, "selector": {"id": "default"}},
                {
                    "properties": {"show": lit(True), "lineColor": color(T["accent"]), "weight": lit(3)},
                    "selector": {"id": "selected"},
                },
            ],
            "selection": props(singleSelect=lit(True), strictSingleSelect=lit(False)),
        },
        vco={"background": props(show=lit(False))},
    )


# ---------------------------------------------------------------- page 1
def page_overview():
    p = Page("p01_overview", "Overview")
    image(p, "p01_hero_photo", "photo_360_2010_rome.jpg", 640, 0, 640, 400, "U2 360° Tour, Rome 2010, by Blackcat")
    scrim(p, "p01_scrim_left", "left", 640, 0, 280, 400)
    scrim(p, "p01_scrim_bottom", "bottom", 640, 168, 640, 232)
    scrim(p, "p01_scrim_top", "top", 640, 0, 640, 64)
    page_header(
        p,
        ("Headline p01", ""),
        ("First Glimpse p01", ""),
        w=580,
        nav_w=760,
    )
    html(p, "p01_kpi_tiles", 40, 212, 580, 96, kpi_tiles_measure(), alt="Shows, songs and countries")
    text(
        p,
        "p01_pick_label",
        40,
        312,
        460,
        18,
        [[("PICK AN ERA (CLICK AGAIN FOR ALL ERAS)", style(9, T["muted"], weight="bold"))]],
    )
    for i, (f, alt) in enumerate(
        [
            ("badge_era1_text.svg", "1976-1980"),
            ("badge_era2_1984_sydney.png", "1980-1985"),
            ("badge_era3_1987_dublin.png", "1986-1990"),
            ("badge_era4_1992_kiel.png", "1992-1998"),
            ("badge_era5_2001_philadelphia.png", "2001-2006"),
            ("badge_era6_2010_rome.png", "2009-2011"),
            ("badge_era7_2018_newark.png", "2015-2019"),
            ("badge_era8_2023_las_vegas.png", "2023-"),
        ]
    ):
        image(p, f"p01_era_badge_{i + 1}", f, 40 + i * 62, 337, 50, 50, f"era badge {alt}", scaling="Fit")
    era_button_slicer(p, 36, 334, 492, 56)
    text(
        p,
        "p01_chart_note",
        40,
        406,
        600,
        20,
        [[("Each bar is a year, shaded by era; icons mark where each tour began.", style(9))]],
    )
    deneb(
        p,
        "p01_shows_per_year",
        28,
        432,
        844,
        256,
        [col("dim_date", "year"), meas(FS, "Shows")],
        years_spec("Shows"),
        "Shows per year 1976 to 2026, shaded by era, busiest year highlighted, tour icons at each tour start",
    )
    top_color = color_measure(
        "Top Song Bar Color",
        'IF ( RANKX ( ALLSELECTED ( dim_song[song_title] ), [Performances] ) = 1, "#F2A93B", "#6FA8DC" )',
        refs=[(FP, "Performances")],
    )
    bar(
        p,
        "p01_top_songs",
        888,
        300,
        368,
        388,
        col("dim_song", "song_title"),
        named(meas(FP, "Performances"), "Times played"),
        "The ten most performed songs, number one highlighted",
        title=title_measure(
            "Title p01 top10", "The ten songs played most, of ", "[Distinct Songs]", "", [(FP, "Distinct Songs")]
        ),
        filters=[topn_filter(col("dim_song", "song_title"), meas(FP, "Performances"), 10, "top10")],
        fill=fill_by(top_color),
        margin=75,
    )
    footer(p, 40, 840)
    return p


# ---------------------------------------------------------------- page 2
def page_road():
    p = Page("p02_on_the_road", "Road")
    page_header(p, ("Headline p02", ""), ("First Glimpse p02", ""), w=720, h=96)
    p.add(
        "p02_venues_map",
        "azureMap",
        24,
        152,
        480,
        536,
        # venue coordinates (not geocoded city names: "Dublin" would also match Dublin, Ohio)
        roles={"Size": [meas(FS, "Shows")], "Y": [col("dim_venue", "latitude")], "X": [col("dim_venue", "longitude")]},
        alt="Map of the cities U2 played, bubbles sized by number of shows",
        objects={
            "mapControls": props(
                defaultStyle=lit("grayscale_dark"),
                autoZoom=lit(True),
                showLabels=lit(False),
                showStylePicker=lit(False),
                showNavigationControls=lit(False),
            ),
            "dataPoint": props(fill=color(T["d1"])),
            "bubbleLayer": props(
                minBubbleRadius=lit(2),
                maxRadius=lit(14),
                bubbleStrokeWidth=lit(1),
                borderShow=lit(True),
                autoStrokeColor=lit(False),
            ),
        },
        vco={"background": props(show=lit(False))},
    )
    image(
        p,
        "p02_photo",
        "photo_joshua_tree_1987_dublin.jpg",
        800,
        0,
        480,
        216,
        "Croke Park, Dublin 1987, by Damian McDonagh",
    )
    scrim(p, "p02_scrim_bottom", "bottom", 800, 72, 480, 144)
    top_city = "TOPN ( 1, VALUES ( dim_venue[city_name] ), [Shows] )"
    city = ext_measure(
        FS,
        "Top City Card p02",
        "\"<div style='font-family:Segoe UI'><div style='font-family:DIN,Bahnschrift,Segoe UI;font-weight:600;"
        "font-size:40px;line-height:1;color:#F2A93B'>\" & "
        f'MAXX ( {top_city}, dim_venue[city_name] ) & " · " & '
        f'FORMAT ( MAXX ( {top_city}, [Shows] ), "#,0", "en-US" ) & '
        "\"</div><div style='color:#ECEDEF;font-size:13px;margin-top:4px'>shows in the most-visited city "
        '(photo: Croke Park, Dublin, 1987)</div></div>"',
        refs=[(FS, "Shows")],
        description="HTML: the most-visited city and its number of shows.",
    )
    html(p, "p02_top_city", 816, 136, 448, 76, city, alt="The most-visited city and its number of shows")
    table(
        p,
        "p02_cities_table",
        800,
        224,
        456,
        272,
        [
            named(col("dim_venue", "city_name"), "City"),
            named(col("dim_venue", "country_name"), "Country"),
            meas(FS, "Shows"),
            named(meas(FS, "First Show Date"), "First visit"),
            named(meas(FS, "Last Show Date"), "Last visit"),
        ],
        "Every city with its number of shows and first and last visit, most shows first",
        sort=[(meas(FS, "Shows"), "Descending")],
        title=title_measure("Title p02 cities", "All ", "[Cities]", " cities, most shows first", [(FS, "Cities")]),
    )
    p.add(
        "p02_continent_decade",
        "hundredPercentStackedColumnChart",
        800,
        500,
        456,
        188,
        roles={
            "Category": [col("dim_date", "decade")],
            "Series": [col("dim_venue", "continent")],
            "Y": [meas(FS, "Shows")],
        },
        alt="Share of shows by continent in each decade",
        title="Where the shows were, decade by decade",
        objects={
            "legend": props(show=lit(True), position=lit("Top"), labelColor=color(T["muted"]), fontSize=lit(8)),
            "valueAxis": props(show=lit(False)),
            "labels": props(show=lit(False)),
        },
        vco={"background": props(show=lit(False))},
    )
    table(
        p,
        "p02_shows",
        520,
        152,
        264,
        536,
        [named(col("dim_show", "show_label"), "Show (date · city · venue)")],
        "Shows in the current selection, latest first; right-click a show and drill through to its setlist",
        sort=[(col("dim_show", "show_label"), "Descending")],
        filters=[measure_filter(meas(FS, "Shows"), 0, "has_show")],
        widths=[236],
        title=title_measure(
            "Title p02 shows", "", "[Shows]", " shows · right-click one for its setlist", [(FS, "Shows")]
        ),
    )
    footer(p, 40, 740, note="Bubble size = shows in the city")
    return p


# ---------------------------------------------------------------- page 3
def page_songs():
    p = Page("p03_the_songs", "Songs")
    image(p, "p03_band_photo", "photo_joshua_tree_2017_manchester_tn.jpg", 0, 0, 520, 272, "Joshua Tree Tour 2017")
    scrim(p, "p03_scrim_bottom", "bottom", 0, 112, 520, 160)
    card_text(
        p,
        "p03_top_song_callout",
        24,
        188,
        480,
        76,
        placeholder("Top Song Text"),
        size=28,
        color_=T["accent"],
        alt="The most played song and how often",
    )
    page_header(p, ("Headline p03", ""), ("First Glimpse p03", ""), x=552, w=704)
    p.add(
        "p03_explore_scatter",
        "scatterChart",
        552,
        206,
        704,
        214,
        roles={
            "Category": [col("dim_song", "song_title")],
            "X": [
                named(
                    {"Aggregation": {"Expression": col("dim_song", "first_release_year"), "Function": 3}},
                    "Year first released",
                )
            ],
            "Y": [named(meas(FP, "Performances"), "Times played")],
        },
        alt="Scatter of songs: year first released against times played; each dot is a song",
        title="Every song: year released and times played",
        objects={
            "dataPoint": props(fill=color(T["d1"])),
            "categoryAxis": props(
                gridlineShow=lit(False),
                start=lit(1976),
                end=lit(2027),
                showAxisTitle=lit(True),
                labelDisplayUnits=lit(1),
            ),
            "valueAxis": props(
                show=lit(True), gridlineShow=lit(False), showAxisTitle=lit(True), labelDisplayUnits=lit(1)
            ),
        },
        vco={"background": props(show=lit(False))},
    )
    table(
        p,
        "p03_song_ranking_table",
        24,
        288,
        496,
        400,
        [
            named(col("dim_song", "song_title"), "Song"),
            named(col("dim_album", "album_label"), "Album"),
            named(meas(FP, "Performances"), "Times"),
        ],
        "Every song with its album, most played first",
        sort=[(meas(FP, "Performances"), "Descending")],
        title=title_measure(
            "Title p03 songs",
            "All ",
            "[Distinct Songs]",
            " songs, most played first · right-click for the story",
            [(FP, "Distinct Songs")],
        ),
        widths=[230, 170, 56],
    )
    rare = {
        "name": "rare",
        "field": col("dim_song", "full_performances"),
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [{"Name": "s", "Entity": "dim_song", "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "Comparison": {
                            "ComparisonKind": 4,
                            "Left": {
                                "Column": {
                                    "Expression": {"SourceRef": {"Source": "s"}},
                                    "Property": "full_performances",
                                }
                            },
                            "Right": {"Literal": {"Value": "2L"}},
                        }
                    }
                }
            ],
        },
    }
    table(
        p,
        "p03_rarities",
        552,
        428,
        300,
        260,
        [named(col("dim_song", "song_title"), "Song"), named(meas(FP, "Last Played Date"), "Last played")],
        "Every rarity (played twice or less), most recent first",
        filters=[rare],
        sort=[(meas(FP, "Last Played Date"), "Descending")],
        title=title_measure(
            "Title p03 rarities",
            "All ",
            "[Rarities]",
            " rarities (played twice or less), most recent first",
            [(FP, "Rarities")],
        ),
        widths=[180, 90],
    )
    table(
        p,
        "p03_covers",
        868,
        414,
        388,
        152,
        [
            named(col("dim_song", "song_title"), "Song"),
            named(col("dim_song", "cover_artist"), "Original by"),
            named(meas(FP, "Performances"), "Times"),
        ],
        "Every song by another artist that U2 played, most played first",
        sort=[(meas(FP, "Performances"), "Descending")],
        filters=[
            bool_filter(col("dim_song", "is_original"), False, "covers"),
        ],
        title=title_measure(
            "Title p03 covers",
            "All ",
            "[Cover Songs]",
            " other people's songs, most played first",
            [(FP, "Distinct Songs")],
        ),
        widths=[160, 140, 50],
    )
    table(
        p,
        "p03_guests",
        868,
        568,
        388,
        122,
        [named(col(FP, "guest_artist"), "Guest"), named(meas(FP, "Guest Appearances"), "Times")],
        "Every guest who joined U2 on stage, most frequent first",
        sort=[(meas(FP, "Guest Appearances"), "Descending")],
        title=title_measure(
            "Title p03 guests",
            "All ",
            "[Guest Artists]",
            " guests on stage, most frequent first",
        ),
        widths=[300, 60],
    )
    footer(p, 552, 704)
    return p


# ---------------------------------------------------------------- page 4
def page_albums():
    p = Page("p04_albums_on_stage", "Albums")
    page_header(p, ("Headline p04", ""), ("First Glimpse p04", ""), w=736)
    perf = meas(FP, "Performances")
    p.add(
        "p04_album_share_columns",
        "hundredPercentStackedColumnChart",
        40,
        206,
        736,
        120,
        roles={
            "Category": [col("dim_date", "year")],
            "Series": [col("dim_album", "release_decade_group")],
            "Y": [named(perf, "Songs played")],
        },
        alt="Share of songs played each year, by the decade their album came out; years without shows are empty",
        title="Songs played each year, by album decade",
        objects={
            "legend": props(show=lit(True), position=lit("Top"), labelColor=color(T["muted"]), fontSize=lit(8)),
            "valueAxis": props(show=lit(False), gridlineShow=lit(False)),
            "categoryAxis": props(gridlineShow=lit(False), axisType=lit("Scalar"), labelColor=color(T["muted"])),
            "labels": props(show=lit(False)),
        },
        vco={"background": props(show=lit(False))},
    )
    card_text(
        p,
        "p04_area_note",
        400,
        206,
        376,
        24,
        placeholder("Annotation p04"),
        size=13,
        color_=T["accent"],
        family="Segoe UI",
        italic=True,
    )
    studio = basic_filter(col("dim_album", "album_type"), ["studio"], "studio")
    share = ext_measure(
        FP,
        "Album Share (no zeros)",
        "VAR S = [Album Share %] RETURN IF ( S >= 0.0005, S )",
        data_type="Double",
        refs=[(FP, "Album Share %")],
        description="Album Share % with blanks instead of 0.0% (matrix).",
    )
    EXT_MEASURES[FP][-1]["formatString"] = "0.0%"
    cell = ext_measure(
        FP,
        "Album Share Cell",
        "VAR S = [Album Share %] "
        "VAR Dec = VALUE ( LEFT ( SELECTEDVALUE ( dim_date[decade] ), 4 ) ) "
        "VAR Rel = SELECTEDVALUE ( dim_album[release_year] ) "
        'RETURN IF ( S > 0, IF ( S < 0.0005, "< 0.1%", FORMAT ( S, "0.0%", "en-US" ) ), '
        'IF ( NOT ISBLANK ( Dec ) && NOT ISBLANK ( Rel ) && Dec + 9 >= Rel, "0%" ) )',
        refs=[(FP, "Album Share %")],
        description="Matrix cell text: blank before the album existed, 0% when not played, < 0.1% when tiny.",
    )
    p.add(
        "p04_album_decade_matrix",
        "pivotTable",
        40,
        326,
        736,
        346,
        roles={
            "Rows": [named(col("dim_album", "album_label"), "Album")],
            "Columns": [col("dim_date", "decade")],
            "Values": [named(cell, "Share")],
        },
        alt="Heatmap: share of all songs played that came from each studio album, per decade, albums in release order",
        title=title_measure(
            "Title p04 albums",
            "Which albums stay: all ",
            "[Studio Albums]",
            " studio albums, share of songs per decade",
        ),
        filters=[studio, bool_filter(col("dim_album", "is_studio"), True, "is_studio")],
        sort=[(col("dim_album", "album_label"), "Ascending")],  # album_label sorts by album_order
        objects={
            "values": [gradient(share, "fact_performance.Album Share Cell")],
            "grid": props(
                gridHorizontal=lit(False),
                gridVertical=lit(False),
                outlineColor=color(T["bg"]),
                rowPadding=lit(0),
                textSize=lit(9),
            ),
            "columnHeaders": props(
                fontColor=color(T["muted"]), autoSizeColumnWidth=lit(False), defaultColumnWidth=lit(80)
            ),
            "subTotals": props(rowSubtotals=lit(False), columnSubtotals=lit(False)),
        },
        vco={"background": props(show=lit(False))},
    )
    card = photo_card_measure(
        "Photo Card p04",
        "photo_zoo_tv_1992_kiel",
        'FORMAT ( CALCULATE ( [Promoted Album Share %], dim_tour[tour_name] = "Zoo TV" ), "0%", "en-US" )',
        '"of the songs on Zoo TV came from Achtung Baby"',
        refs=[(FP, "Promoted Album Share %")],
        height=240,
    )
    html(
        p,
        "p04_photo_card",
        808,
        0,
        472,
        240,
        card,
        alt="Photo card: share of Zoo TV performances from the promoted album",
        filters=[basic_filter(col("report_image", "image_id"), ["photo_zoo_tv_1992_kiel"], "img")],
        clip=False,
    )
    promo = meas(FP, "Promoted Album Share %")
    album = ext_measure(
        FS,
        "Promoted Album Label",
        "VAR K = SELECTEDVALUE ( dim_tour[album_promoted_key] ) "
        "RETURN IF ( NOT ISBLANK ( K ) && K <> -1, LOOKUPVALUE ( dim_album[album_label], dim_album[album_key], K ) )",
        description="Short name of the album the tour promoted (inactive relationship, looked up by key).",
    )
    has_album = ext_measure(
        FS,
        "Has Promoted Album",
        "VAR K = SELECTEDVALUE ( dim_tour[album_promoted_key] ) RETURN IF ( NOT ISBLANK ( K ) && K <> -1, 1, 0 )",
        data_type="Integer",
        description="1 for tours with a promoted album (table filter).",
    )
    table(
        p,
        "p04_promoted_share_table",
        808,
        248,
        448,
        440,
        [
            named(meas(FS, "Tour Icon"), " "),
            named(col("dim_tour", "tour_name_display"), "Tour"),
            named(album, "Album"),
            named(promo, "From it"),
        ],
        "Every tour that promoted an album, in order, with the album and the share of songs that came from it",
        sort=[(col("dim_tour", "tour_name_display"), "Ascending")],  # tour_name_display sorts by tour_order
        filters=[measure_filter(has_album, 0, "promoted")],
        title=title_measure(
            "Title p04 tours",
            "All ",
            "[Tours with Promoted Album]",
            " tours with a new album: share from it",
        ),
        widths=[24, 186, 104, 84],
        extra_objects={
            "columnFormatting": [data_bars("fact_performance.Promoted Album Share %")],
            "grid": props(
                gridHorizontal=lit(False),
                gridVertical=lit(False),
                rowPadding=lit(0),
                textSize=lit(9),
                outlineColor=color(T["bg"]),
                imageHeight=lit(16),
                imageWidth=lit(16),
            ),
        },
    )
    text(
        p,
        "p04_matrix_note",
        40,
        672,
        736,
        18,
        [
            [
                (
                    "Songs count for their first album, so Boy shows in the 1970s (played before its release). "
                    "Blank = not released yet · 0% = not played.",
                    style(8),
                )
            ]
        ],
    )
    footer(p, 40, 740)
    return p


# ---------------------------------------------------------------- page 5
def page_setlists():
    p = Page("p05_setlist_evolution", "Setlists")
    page_header(p, ("Headline p05", ""), ("First Glimpse p05", ""), w=760)
    perf = meas(FP, "Performances")
    p.add(
        "p05_song_era_heatmap",
        "pivotTable",
        24,
        212,
        776,
        476,
        roles={
            "Rows": [named(col("dim_song", "song_title"), "Song")],
            "Columns": [named(col("dim_date", "decade"), "Decade")],
            "Values": [named(perf, "Times")],
        },
        alt="Heatmap of every song by decade, most played first: brighter cells mean more performances",
        title=title_measure(
            "Title p05 heatmap",
            "All ",
            "[Distinct Songs]",
            " songs by decade, most played first (scroll for more)",
            [(FP, "Distinct Songs")],
        ),
        sort=[(perf, "Descending")],
        objects={
            "values": [gradient(perf, "fact_performance.Performances")],
            "grid": props(
                gridHorizontal=lit(False),
                gridVertical=lit(False),
                rowPadding=lit(1),
                textSize=lit(9),
                outlineColor=color(T["bg"]),
            ),
            "columnHeaders": props(
                fontSize=lit(8),
                fontColor=color(T["muted"]),
                wordWrap=lit(True),
                autoSizeColumnWidth=lit(False),
                defaultColumnWidth=lit(84),
            ),
            "rowHeaders": props(fontSize=lit(9), fontColor=color(T["text"])),
            "subTotals": props(rowSubtotals=lit(False), columnSubtotals=lit(False)),
        },
        vco={"background": props(show=lit(False))},
    )
    image(
        p, "p05_photo", "photo_elevation_2001_philadelphia.jpg", 832, 0, 448, 176, "Elevation Tour, Philadelphia 2001"
    )
    scrim(p, "p05_scrim_bottom", "bottom", 832, 104, 448, 72)
    text(
        p,
        "p05_photo_note",
        848,
        148,
        408,
        22,
        [[("Elevation's heart stage: same songs, closer crowd", style(10, T["accent"], italic=True, weight="bold"))]],
    )
    var = meas(FP, "Setlist Variety")
    table(
        p,
        "p05_variety_table",
        832,
        184,
        424,
        230,
        [
            named(meas(FS, "Tour Icon"), " "),
            named(col("dim_tour", "tour_name_display"), "Tour"),
            named(var, "Variety"),
        ],
        "Every tour, most fixed setlist first: variety = different songs divided by songs per night",
        sort=[(var, "Ascending")],
        title=title_measure(
            "Title p05 variety",
            "All ",
            "CALCULATE ( DISTINCTCOUNT ( fact_show[tour_key] ), REMOVEFILTERS ( dim_tour ) )",
            " tours, most fixed setlist first",
        ),
        vco=subtitle("Variety = different songs ÷ songs per night; 1 = the same set every night"),
        extra_objects={"columnFormatting": [data_bars("fact_performance.Setlist Variety")]},
    )
    p.add(
        "p05_songs_per_show_line",
        "lineChart",
        832,
        414,
        424,
        132,
        roles={"Category": [col("dim_date", "year")], "Y": [named(meas(FP, "Avg Songs per Show"), "Songs per show")]},
        alt="Average songs per show by year",
        title="Songs per show, by year",
        objects={
            "dataPoint": props(fill=color(T["d1"])),
            "lineStyles": props(lineChartType=lit("straight"), strokeWidth=lit(2)),
            "valueAxis": props(show=lit(True), gridlineShow=lit(False), labelColor=color(T["muted"])),
            "categoryAxis": props(
                show=lit(True),
                gridlineShow=lit(False),
                labelColor=color(T["muted"]),
                axisType=lit("Scalar"),
                labelDisplayUnits=lit(1),
                fontSize=lit(9),
            ),
        },
        vco={"background": props(show=lit(False))},
    )
    bar(
        p,
        "p05_openers_bar",
        832,
        548,
        424,
        140,
        col("dim_song", "song_title"),
        named(meas(FP, "Opener Count"), "Times it opened"),
        "The three songs that opened the show most often",
        title=title_measure(
            "Title p05 openers",
            "Top openers: 3 of ",
            "[Opener Songs]",
            " openers",
        ),
        filters=[topn_filter(col("dim_song", "song_title"), meas(FP, "Opener Count"), 3, "top3")],
        margin=28,
    )
    footer(p, 40, 760)
    return p


# ---------------------------------------------------------------- page 6
def page_sphere():
    p = Page("p06_sphere_vs_touring", "Sphere")
    image(p, "p06_sphere_photo", "photo_sphere_2023_las_vegas.jpg", 0, 0, 520, 720, "U2 at Sphere, Las Vegas 2023")
    scrim(p, "p06_scrim_right", "right", 360, 0, 160, 720)
    scrim(p, "p06_scrim_bottom", "bottom", 0, 400, 520, 320)
    res = ext_measure(
        FS,
        "Residency Callouts p06",
        "\"<div style='font-family:Segoe UI'><div style='font-size:11px;letter-spacing:1.5px;font-weight:700;"
        "color:#ECEDEF'>"
        + svg_inline("glyph_sphere.svg", 16)
        + " RESIDENCY · SPHERE, LAS VEGAS · 2023-24</div><div style='display:flex;gap:28px;margin-top:8px'>\" & "
        + big(
            'FORMAT ( CALCULATE ( [Shows], REMOVEFILTERS ( dim_tour ), dim_tour[is_residency] = TRUE () ), "#,0", '
            '"en-US" )',
            "shows",
        )
        + " & "
        + big('FORMAT ( [Residency Songs per Show], "0", "en-US" )', "songs a night")
        + " & "
        + big('FORMAT ( [Residency Achtung Baby Share %], "0%", "en-US" )', "from Achtung Baby")
        + ' & "</div></div>"',
        refs=[(FS, "Shows"), (FP, "Residency Songs per Show"), (FP, "Residency Achtung Baby Share %")],
        description="HTML: residency callouts on the Sphere photo.",
    )
    html(p, "p06_residency_callouts", 32, 568, 470, 128, res, alt="Residency: shows, songs a night, Achtung Baby share")
    page_header(p, ("Headline p06", ""), ("First Glimpse p06", ""), x=560, w=696)

    def row(label, r, t, d, fmt, maxv, suffix=""):
        bar_ = (
            "\"<div style='display:flex;align-items:center;gap:8px'><div style='height:10px;border-radius:2px;"
            'background:{c};width:" & INT ( 140 * DIVIDE ( COALESCE ( {v}, 0 ), ' + maxv + " ) ) & \"px'></div><spa"
            "n style='font-fam"
            "ily:DIN,Bahnschrift,Segoe UI;font-weight:600;font-size:22px;color:{tc}'>\" & "
            'FORMAT ( COALESCE ( {v}, 0 ), "' + fmt + '", "en-US" ) & "</span></div>"'
        )
        return (
            "\"<div style='color:#ECEDEF;font-size:13px'>"
            + label
            + '</div>" & '
            + bar_.format(c=T["accent"], v=r, tc=T["accent"])
            + " & "
            + bar_.format(c=T["neutral"], v=t, tc=T["text"])
            + ' & "<div style=\'font-family:DIN,Bahnschrift,Segoe UI;font-weight:600;font-size:26px;color:" & '
            + f'IF ( COALESCE ( {d}, 0 ) >= 0, "#F2A93B", "#E06666" ) & "\'>" & '
            + f'IF ( COALESCE ( {d}, 0 ) > 0, "+", "" ) & '
            + f'FORMAT ( COALESCE ( {d}, 0 ), "{fmt.replace("%", "")}", "en-US" ) & "{suffix}</div>"'
        )

    head = (
        "\"<div style='display:grid;grid-template-columns:140px 1fr 1fr 110px;row-gap:12px;align-items:center;"
        "font-family:Segoe UI'><div></div><div style='font-size:11px;font-weight:700;letter-spacing:1.5px;"
        "color:#F2A93B'>"
        + svg_inline("glyph_sphere.svg", 14)
        + " RESIDENCY</div><div style='font-size:11px;font-weight:700;letter-spacing:1.5px;color:#A3A9B3'>"
        + svg_inline("glyph_innocence_experience.svg", 14)
        + " TOURING</div><div style='font-size:11px;font-weight:700;letter-spacing:1.5px;color:#A3A9B3'>"
        'DIFFERENCE</div>" & '
    )
    h2h = ext_measure(
        FS,
        "Head to Head p06",
        head
        + row(
            "Songs a night",
            "[Residency Songs per Show]",
            "[Touring Songs per Show]",
            "[Difference Songs per Show]",
            "0.0",
            "30",
        )
        + " & "
        + row(
            "Different songs",
            "[Residency Distinct Songs]",
            "[Touring Distinct Songs]",
            "[Difference Distinct Songs]",
            "#,0",
            "MAX ( [Residency Distinct Songs], [Touring Distinct Songs] )",
        )
        + " & "
        + row(
            "Achtung Baby share",
            "[Residency Achtung Baby Share %]",
            "[Touring Achtung Baby Share %]",
            "[Difference Achtung Baby Share (pp)]",
            "0%",
            "1",
            suffix=" pp",
        )
        + ' & "</div>"',
        refs=[
            (FP, n)
            for n in (
                "Residency Songs per Show",
                "Touring Songs per Show",
                "Difference Songs per Show",
                "Residency Distinct Songs",
                "Touring Distinct Songs",
                "Difference Distinct Songs",
                "Residency Achtung Baby Share %",
                "Touring Achtung Baby Share %",
                "Difference Achtung Baby Share (pp)",
            )
        ],
        description="HTML: residency vs touring head-to-head with bars and differences.",
    )
    html(p, "p06_head_to_head", 560, 212, 696, 188, h2h, alt="Residency versus touring: songs a night, songs, share")
    text(p, "p06_compare_label", 560, 414, 120, 18, [[("COMPARE WITH", style(9, T["muted"], weight="bold"))]])
    slicer(p, "p06_compare_slicer", 664, 404, 240, 36, col("dim_tour", "tour_name_display"), "Tours to compare with")
    card_text(
        p,
        "p06_note",
        920,
        410,
        336,
        28,
        placeholder("Annotation p06"),
        size=13,
        color_=T["accent"],
        family="Segoe UI",
        italic=True,
    )
    is_res = "CALCULATE ( COUNTROWS ( fact_show ), REMOVEFILTERS ( dim_tour ), dim_tour[is_residency] = TRUE () ) > 0"
    compare = 'KEEPFILTERS ( dim_tour[era] = "2015-2019 Innocence and Experience" )'
    year_expr = (
        "VAR D = CALCULATE ( MIN ( dim_date[date] ), fact_show ) "
        "RETURN YEAR ( D ) + DIVIDE ( INT ( D - DATE ( YEAR ( D ), 1, 1 ) ), 366 )"
    )
    year_dec = ext_measure(
        FS,
        "Show Year Decimal",
        f"IF ( {is_res}, CALCULATE ( {year_expr}, REMOVEFILTERS ( dim_tour ) ), "
        f"IF ( ISFILTERED ( dim_tour[tour_name_display] ), {year_expr}, CALCULATE ( {year_expr}, {compare} ) ) )",
        data_type="Double",
        description="Show date as a decimal year: residency shows always, other shows of the compared tours.",
    )
    EXT_MEASURES[FS][-1]["formatString"] = "0"
    songs = ext_measure(
        FS,
        "Songs in Show p06",
        f"IF ( {is_res}, CALCULATE ( [Performances], REMOVEFILTERS ( dim_tour ) ), "
        f"IF ( ISFILTERED ( dim_tour[tour_name_display] ), [Performances], CALCULATE ( [Performances], {compare} ) ) )",
        data_type="Integer",
        refs=[(FP, "Performances")],
        description="Songs in the show: residency shows always, other shows of the compared tours (default 2015-2019).",
    )
    dot_colour = ext_measure(
        FS,
        "Show Dot Colour p06",
        f'IF ( {is_res}, "{T["accent"]}", "{T["neutral"]}" )',
        description="Accent for residency shows, grey for touring shows (presentation only).",
    )
    title = ext_measure(
        FS,
        "Title p06 every show",
        '"Every show, one dot: Sphere (amber) vs " & IF ( ISFILTERED ( dim_tour[tour_name_display] ), '
        "IF ( COUNTROWS ( VALUES ( dim_tour[tour_name_display] ) ) <= 2, "
        'CONCATENATEX ( VALUES ( dim_tour[tour_name_display] ), dim_tour[tour_name_display], " and " ), '
        'COUNTROWS ( VALUES ( dim_tour[tour_name_display] ) ) & " tours" ), "the 2015-2019 tours" ) & " (grey) · ri'
        'ght-click a dot for its setlist"',
        description="Dynamic title of the p06 every-show chart.",
    )
    p.add(
        "p06_every_show_scatter",
        "scatterChart",
        560,
        448,
        696,
        240,
        roles={
            "Category": [col("dim_show", "show_label")],
            "X": [named(year_dec, "Year")],
            "Y": [named(songs, "Songs in the show")],
        },
        alt="Every show as a dot: songs per show by date; Sphere residency shows in amber, compared tours in grey",
        title=title,
        objects={
            "dataPoint": fill_by(dot_colour),
            "valueAxis": props(
                show=lit(True), gridlineShow=lit(False), labelColor=color(T["muted"]), showAxisTitle=lit(True)
            ),
            "categoryAxis": props(gridlineShow=lit(False), labelDisplayUnits=lit(1), labelColor=color(T["muted"])),
        },
        vco={"background": props(show=lit(False))},
    )
    footer(p, 560, 696)
    return p


# ---------------------------------------------------------------- page 7
def page_song_detail():
    p = Page("p07_song_detail", "Song", drill=col("dim_song", "song_title"), hidden=True)
    image(p, "p07_photo", "photo_popmart_1997_reggio_emilia.jpg", 800, 0, 480, 208, "PopMart Tour, Reggio Emilia 1997")
    scrim(p, "p07_scrim_left", "left", 800, 0, 240, 208)
    nav(p, 40, 6, 640)
    back_button(p, 704, 12)
    card_body = (
        "\"<div style='font-family:Segoe UI'><div style='font-size:11px;letter-spacing:1.5px;font-weight:700;"
        "color:#F2A93B'>SONG · \" & UPPER ( COALESCE ( CALCULATE ( SELECTEDVALUE ( dim_album[album_label] ), dim_so"
        'ng ), "not on a studio '
        'album" ) ) & IF ( NOT ISBLANK ( SELECTEDVALUE ( dim_song[first_release_year] ) ), " (" & '
        'SELECTEDVALUE ( dim_song[first_release_year] ) & ")" ) & "</div>'
        "<div style='font-family:DIN,Bahnschrift,Segoe UI;font-weight:600;font-size:36px;line-height:1.05;"
        'color:#ECEDEF;white-space:nowrap;overflow:hidden;text-overflow:ellipsis\'>" & [Selected Song] & "</div>'
        "<div style='display:flex;gap:30px;margin-top:12px'>\" & "
        + big('FORMAT ( [Performances], "#,0", "en-US" )', "performances", size=30)
        + " & "
        + big('FORMAT ( [First Played Date], "yyyy-mm-dd", "en-US" )', "live debut", colour=T["text"], size=30)
        + " & "
        + big('FORMAT ( [Last Played Date], "yyyy-mm-dd", "en-US" )', "last played", colour=T["text"], size=30)
        + " & "
        + big('FORMAT ( [Years Since Last Played], "0", "en-US" )', "years since", colour=T["text"], size=30)
        + ' & "</div></div>"'
    )
    card = ext_measure(
        FS,
        "Song Card p07",
        "IF ( HASONEVALUE ( dim_song[song_title] ), "
        + card_body
        + ", "
        + prompt_html("Right-click a song on the Songs page and choose Drill through → Song to see its story.")
        + " )",
        refs=[(FP, n) for n in ("Selected Song", "Performances", "First Played Date", "Last Played Date")]
        + [(FP, "Years Since Last Played")],
        description="HTML: song drill-through card, or a prompt when no single song is in context.",
    )
    one_song = ext_measure(
        FS,
        "Is One Song",
        "IF ( HASONEVALUE ( dim_song[song_title] ), 1, 0 )",
        data_type="Integer",
        description="1 when exactly one song is in context (drill-through page filter).",
    )
    html(p, "p07_song_card", 40, 56, 740, 144, card, alt="The selected song: album, performances, debut, last played")
    deneb(
        p,
        "p07_plays_per_year",
        28,
        212,
        760,
        248,
        [col("dim_date", "year"), meas(FP, "Performances")],
        years_spec("Performances"),
        "Performances of the song per year, busiest year highlighted, tour icons at each tour start",
    )
    p.visuals[-1]["filterConfig"] = {"filters": [measure_filter(one_song, 0, "one")]}
    tours = meas(FP, "Performances")
    table(
        p,
        "p07_tours_table",
        40,
        472,
        740,
        216,
        [
            named(meas(FS, "Tour Icon"), " "),
            named(col("dim_tour", "tour_name_display"), "Tour"),
            named(tours, "Times played"),
            named(meas(FP, "Share of Tour Shows %"), "Share of the tour's shows"),
        ],
        "Tour by tour: how often the song was played",
        filters=[measure_filter(meas(FP, "Performances"), 0, "played"), measure_filter(one_song, 0, "one")],
        sort=[(col("dim_tour", "tour_name_display"), "Ascending")],
        title="Tour by tour",
        extra_objects={"columnFormatting": [data_bars("fact_performance.Share of Tour Shows %")]},
    )

    table(
        p,
        "p07_shows",
        812,
        216,
        444,
        244,
        [
            named(col("dim_show", "show_label"), "Show (date · city · venue)"),
            named(col("dim_tour", "tour_name_display"), "Tour"),
        ],
        "Shows in the current selection, latest first; right-click a show and drill through to its setlist",
        sort=[(col("dim_show", "show_label"), "Descending")],
        filters=[measure_filter(meas(FP, "Performances"), 0, "played"), measure_filter(one_song, 0, "one")],
        widths=[270, 140],
        title=title_measure(
            "Title p07 shows",
            "Every time it was played: ",
            "[Shows Played]",
            " shows · right-click one for its setlist",
        ),
    )

    def pos_row(label, measure, colour):
        return (
            f"\"<div style='display:grid;grid-template-columns:90px 1fr 56px;align-items:center;gap:8px;"
            f"margin:6px 0'><span style='color:#ECEDEF;font-size:13px'>{label}</span>"
            f"<div style='height:12px;border-radius:2px;background:{colour};width:\" & "
            f"FORMAT ( MAX ( 100 * COALESCE ( DIVIDE ( [{measure}], [Performances] ), 0 ), "
            f'IF ( [{measure}] > 0, 1, 0 ) ), "0.0", "en-US" ) & "%\'></div>'
            "<span style='font-family:DIN,Bahnschrift,Segoe UI;font-weight:600;font-size:18px;color:#ECEDEF'>\" & "
            f'FORMAT ( COALESCE ( DIVIDE ( [{measure}], [Performances] ), 0 ), "0%", "en-US" ) & "</span></div>"'
        )

    pos = ext_measure(
        FS,
        "Position p07",
        "IF ( HASONEVALUE ( dim_song[song_title] ), \"<div style='font-family:Segoe UI'>\" & "
        + pos_row("Opener", "Opener Count", T["d2"])
        + " & "
        + pos_row("Encore", "Encore Count", T["d4"])
        + " & "
        + pos_row("Closer", "Closer Count", T["d6"])
        + " & \"<div style='color:#A3A9B3;font-size:11px;margin-top:6px'>Share of the song's performances; the rest "
        'were in the main set.</div></div>", "" )',
        refs=[(FP, "Opener Count"), (FP, "Encore Count"), (FP, "Closer Count"), (FP, "Performances")],
        description="HTML: where in the night the song is played (opener, encore, closer shares).",
    )
    text(
        p,
        "p07_position_title",
        812,
        472,
        444,
        24,
        [[("Where in the night it is played", style(10, T["text"], weight="bold"))]],
    )
    html(
        p,
        "p07_position",
        812,
        500,
        444,
        188,
        pos,
        alt="Share of the song's performances as opener, in encore, as closer",
    )
    footer(p, 40, 740)
    return p


# ---------------------------------------------------------------- page 8
def page_show_detail():
    p = Page("p08_show_detail", "Show", drill=col("dim_show", "show_label"), hidden=True)
    image(p, "p08_photo", "photo_war_1983_dublin.jpg", 900, 0, 380, 720, "War Tour, Dublin 1983, by Colm Henry")
    scrim(p, "p08_scrim_left", "left", 900, 0, 190, 720)
    nav(p, 40, 6, 640)
    back_button(p, 704, 12)
    header = (
        "\"<div style='color:#F2A93B;font-size:10px;letter-spacing:1.4px;font-weight:700;padding-top:8px'>\" & "
        'UPPER ( S ) & "</div>"'
    )
    pill = "<span style='font-size:10px;border-radius:8px;padding:0 5px;white-space:nowrap;"
    row = (
        "VAR Dim = fact_performance[is_snippet] || fact_performance[is_tape] RETURN "
        '"<div style=\'display:flex;align-items:center;gap:8px;padding:2px 0;opacity:" & IF ( Dim, "0.55", "1"'
        " ) & "
        "\"'><span style='color:#A3A9B3;width:20px;text-align:right;flex:none'>\" & P & \"</span>"
        "<span style='color:#ECEDEF;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>\" & "
        "dim_song[song_title] & \"</span><span style='margin-left:auto;display:flex;gap:4px;flex:none'>\" & "
        f'IF ( fact_performance[is_live_debut], "{pill}color:#F2A93B;border:1px solid #F2A93B\'>★ debut</span>" ) & '
        f'IF ( fact_performance[is_cover], "{pill}color:#A3A9B3;border:1px solid #2A2F38\'>cover</span>" ) & '
        "IF ( NOT ISBLANK ( fact_performance[guest_artist] ), "
        f'"{pill}color:#A3A9B3;border:1px solid #2A2F38\'>with " & fact_performance[guest_artist] & "</span>" ) & '
        f'IF ( fact_performance[is_tape], "{pill}color:#A3A9B3;border:1px dashed #6E7581\'>tape</span>" ) & '
        f'IF ( fact_performance[is_snippet], "{pill}color:#A3A9B3;border:1px dashed #6E7581\'>snippet</span>" ) & '
        '"</span></div>"'
    )
    # songs in setlist order; a set header is printed whenever the set changes from the previous position
    songs = (
        "CONCATENATEX ( SetRows, "
        "VAR P = fact_performance[setlist_position] VAR S = fact_performance[set_name] "
        "VAR PrevP = MAXX ( FILTER ( SetRows, fact_performance[setlist_position] < P ), fact_performance[setlist_posit"
        "ion] ) "
        "VAR PrevS = MAXX ( FILTER ( SetRows, fact_performance[setlist_position] = PrevP ), fact_performance[set_na"
        "me] ) "
        "RETURN IF ( ISBLANK ( PrevP ) || S <> PrevS, " + header + " ) & ( " + row + " )" + ', "", '
        "fact_performance[setlist_position], ASC )"
    )

    def stat(value, label, colour=T["text"]):
        return (
            "\"<div style='margin-top:14px'><div style='font-family:DIN,Bahnschrift,Segoe UI;font-weight:600;"
            f"font-size:26px;line-height:1;color:{colour}'>\" & {value} & \"</div><div style='font-size:12px;"
            f"color:#A3A9B3'>{label}</div></div>\""
        )

    stub_stats = (
        stat(
            'FORMAT ( [Performances], "#,0", "en-US" )',
            'songs" & IF ( Extras > 0, " + " & Extras & IF ( Tapes > 0 && Snips = 0, IF ( Tapes = 1, " tape", '
            '" tapes" ), IF ( Snips > 0 && Tapes = 0, IF ( Snips = 1, " snippet", " snippets" ), '
            '" tapes/snippets" ) ) ) & "',
        )
        + " & "
        + "IF ( NoTour, \"<div style='margin-top:14px;font-size:12px;color:#A3A9B3'>One-off show, outside a tour</"
        'div>", '
        + stat('FORMAT ( [Tour Avg Songs per Show], "0.0", "en-US" )', "songs a night on this tour")
        + " )"
        + " & "
        + stat('FORMAT ( COALESCE ( [Live Debuts], 0 ), "#,0", "en-US" )', "live debuts ★", T["accent"])
        + " & "
        + stat('FORMAT ( COALESCE ( [Covers Played], 0 ), "#,0", "en-US" )', "covers")
    )
    ticket_body = (
        "\"<div style='display:flex;background:#20242C;border-radius:10px;overflow:hidden;height:600px;"
        "font-family:Segoe UI'><div style='width:230px;padding:18px;border-right:2px dashed #0F1115;"
        "background:#262A33'>\" & SUBSTITUTE ( SUBSTITUTE ( CALCULATE ( [Tour Icon SVG], fact_show ), "
        "\"width='48'\", \"width='40'\" ), \"height='48'\", \"height='40'\" ) & "
        "\"<div style='color:#F2A93B;font-size:11px;letter-spacing:1.5px;font-weight:700;margin-top:10px'>\" & "
        'UPPER ( CALCULATE ( SELECTEDVALUE ( dim_tour[tour_name_display] ), fact_show ) ) & "</div>'
        "<div style='font-family:DIN,Bahnschrift,Segoe UI;font-weight:600;font-size:36px;line-height:1.05;"
        'color:#ECEDEF\'>" & UPPER ( FORMAT ( D, "d mmm", "en-US" ) ) & "<br>" & YEAR ( D ) & "</div>'
        "<div style='margin-top:10px;font-size:12.5px;color:#A3A9B3'><b style='color:#ECEDEF'>\" & "
        'CALCULATE ( SELECTEDVALUE ( dim_venue[venue_name] ), fact_show ) & "</b><br>" & '
        'CALCULATE ( SELECTEDVALUE ( dim_venue[city_name] ), fact_show ) & ", " & '
        'CALCULATE ( SELECTEDVALUE ( dim_venue[country_name] ), fact_show ) & "</div>" & '
        + stub_stats
        + " & \"</div><div style='flex:1;padding:16px 20px;columns:2;column-gap:28px;font-size:12px'>\" & "
        + songs
        + ' & "</div></div>"'
    )
    ticket = ext_measure(
        FS,
        "Ticket p08",
        "VAR D = CALCULATE ( MIN ( dim_date[date] ), fact_show ) "
        "VAR SetRows = CALCULATETABLE ( SUMMARIZE ( fact_performance, fact_performance[setlist_position], "
        "fact_performance[set_name], dim_song[song_title], fact_performance[is_live_debut], "
        "fact_performance[is_cover], fact_performance[guest_artist], fact_performance[is_snippet], "
        "fact_performance[is_tape] ) ) "
        "VAR Tapes = COUNTROWS ( FILTER ( SetRows, fact_performance[is_tape] ) ) "
        "VAR Snips = COUNTROWS ( FILTER ( SetRows, fact_performance[is_snippet] && NOT fact_performance[is_tape] ) ) "
        "VAR Extras = Tapes + Snips "
        'VAR NoTour = CALCULATE ( SELECTEDVALUE ( dim_tour[tour_name] ), fact_show ) = "(No tour)" '
        "RETURN IF ( HASONEVALUE ( dim_show[show_label] ), "
        + ticket_body
        + ", "
        + prompt_html(
            "Right-click a show in a shows list (Road page, Sphere dots, or a song's list) and choose "
            "Drill through → Show."
        )
        + " )",
        refs=[
            (FS, "Tour Icon SVG"),
            (FP, "Performances"),
            (FP, "Tour Avg Songs per Show"),
            (FP, "Live Debuts"),
            (FP, "Covers Played"),
        ],
        description="HTML: show ticket stub with the setlist in position order, or a prompt when no show is selected.",
    )
    html(p, "p08_ticket", 40, 56, 840, 616, ticket, alt="Ticket for the selected show: tour, date, venue, setlist")
    ext_measure(
        FS,
        "Setlist URL p08",
        "IF ( HASONEVALUE ( dim_show[show_label] ), SELECTEDVALUE ( dim_show[setlist_url] ) )",
        description="Web link of the selected show on setlist.fm.",
    )
    link = ext_measure(
        FS,
        "Setlist Link p08",
        "IF ( NOT ISBLANK ( [Setlist URL p08] ), \"<a href='\" & [Setlist URL p08] & \"' target='_blank' "
        "style='font-family:Segoe UI;font-size:15px;color:#F2A93B;text-decoration:none;font-weight:600'>"
        'Open this show on setlist.fm ↗</a>" )',
        description="HTML: link to the selected show on setlist.fm.",
    )
    EXT_MEASURES[FS][-1]["references"] = {
        "measures": [{"schema": "extension", "entity": FS, "name": "Setlist URL p08"}]
    }
    html(p, "p08_setlist_link", 40, 680, 400, 28, link, alt="Open this show on setlist.fm", links=True)
    return p


# ---------------------------------------------------------------- page 9
def page_about():
    p = Page("p09_about", "About")
    nav(p, 40, 6, 840)
    tiles = [
        "tile_era1_text.svg",
        "photo_boy_1981_toronto.jpg",
        "photo_joshua_tree_1987_dublin.jpg",
        "photo_zoo_tv_1992_kiel.jpg",
        "photo_elevation_2001_philadelphia.jpg",
        "photo_360_2010_rome.jpg",
        "photo_experience_innocence_2018_newark.jpg",
        "photo_sphere_2023_las_vegas_bow.jpg",
    ]
    for i, f in enumerate(tiles):
        image(p, f"p09_mosaic_{i + 1}", f, i * 160, 56, 160, 144, f"era photo {i + 1}", scaling="Fill")
    text(p, "p09_headline", 40, 216, 900, 44, [[("About the data, and the photos", style(24, T["text"], DIN, "bold"))]])
    author = ext_measure(
        FS,
        "Author p09",
        "\"<div style='font-family:Segoe UI;font-size:16px;color:#ECEDEF'>Built by <b>Vinicius Baccarini</b> · "
        "<a href='https://www.linkedin.com/in/vin%C3%ADcius-baccarini/' target='_blank' "
        "style='color:#F2A93B;text-decoration:none;font-weight:600'>LinkedIn ↗</a></div>\"",
        description="HTML: author line with LinkedIn link.",
    )
    html(p, "p09_author", 40, 262, 560, 28, author, alt="Built by Vinicius Baccarini, LinkedIn link", links=True)
    text(
        p,
        "p09_sources",
        40,
        300,
        560,
        132,
        [
            [("SOURCES", style(9, T["accent"], weight="bold"))],
            [
                ("setlist.fm", style(10, T["text"], weight="bold")),
                (
                    ": every U2 show and setlist, through the setlist.fm API (free for non-commercial use; data "
                    "contributed by fans). ",
                    style(10),
                ),
                ("MusicBrainz", style(10, T["text"], weight="bold")),
                (
                    ": albums, tracks and songs (CC0). A weekly pipeline loads both into Microsoft Fabric (Bronze, "
                    "Silver, Gold) and this report reads the Gold warehouse through a Direct Lake semantic model.",
                    style(10),
                ),
            ],
        ],
    )
    big_m = {"colour": T["text"], "size": 28, "label_colour": T["muted"]}
    lim = ext_measure(
        FS,
        "Limitations p09",
        "\"<div style='font-family:Segoe UI'><div style='font-size:11px;letter-spacing:1.5px;font-weight:700;"
        "color:#F2A93B'>LIMITATIONS</div><div style='display:flex;gap:30px;margin-top:6px'>\" & "
        + big('FORMAT ( [Shows] - [Shows with Setlist], "#,0", "en-US" )', "shows without a setlist", **big_m)
        + " & "
        + big(
            'IF ( [Unmapped Song Share %] < 0.001, "< 0.1%", FORMAT ( [Unmapped Song Share %], "0.0%", "en-US" ) )',
            "performances not matched to a song",
            **big_m,
        )
        + " & "
        + big('FORMAT ( [Last Refresh Date], "yyyy-mm-dd", "en-US" )', "last refresh", **big_m)
        + " & \"</div><div style='font-size:12px;color:#A3A9B3;margin-top:10px'>Early club shows (1976-1980) are "
        'often missing. Snippets and tapes are flagged and not counted as performances.</div></div>"',
        refs=[(FS, "Shows"), (FS, "Shows with Setlist"), (FP, "Unmapped Song Share %"), (FS, "Last Refresh Date")],
        description="HTML: data limitations with numbers from the model.",
    )
    html(p, "p09_limitations", 40, 440, 560, 200, lim, alt="Limitations: shows without a setlist, unmatched songs")
    credits = [
        r
        for r in read_csv(IMAGES / "credits.csv")
        if r["file"].startswith("photo_") or r["file"] == "icon_360_tour_logo.png"
    ]
    paras = [[("PHOTO AND ICON CREDITS", style(9, T["accent"], weight="bold"))]]
    for r in credits:
        paras.append(
            [
                (r["title"], style(8, T["text"], weight="bold")),
                (f" · {r['author']} · {r['licence']} · Wikimedia Commons", style(8)),
            ]
        )
    paras.append(
        [
            (
                "Photos resized and cropped; CC BY-SA images remain CC BY-SA. Tour glyphs, era badges, arrows and "
                "gradients: original drawings, project licence. Fan-made portfolio project, not affiliated with U2, "
                "their management or their label.",
                style(8),
            )
        ]
    )
    text(p, "p09_credits", 632, 272, 624, 416, paras)
    footer(p, 40, 560)
    return p


# ---------------------------------------------------------------- writing
def write_page(p, order):
    folder = DEF / "pages" / p.name
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "visuals").mkdir(parents=True)
    page = {
        "$schema": S_PAGE,
        "name": p.name,
        "displayName": p.display,
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
        "objects": {
            "background": props(color=color(T["bg"]), transparency=lit(0)),
            "outspace": props(color=color(T["bg"]), transparency=lit(0)),
        },
    }
    if p.hidden:
        page["visibility"] = "HiddenInViewMode"
    if p.drill:
        page["type"] = "Drillthrough"
        page["pageBinding"] = {
            "name": f"{p.name}_binding",
            "type": "Drillthrough",
            "referenceScope": "Default",
            "parameters": [{"name": f"{p.name}_param", "boundFilter": f"{p.name}_drill", "fieldExpr": p.drill}],
        }
        page["filterConfig"] = {
            "filters": [
                {"name": f"{p.name}_drill", "field": p.drill, "type": "Categorical", "howCreated": "Drillthrough"}
            ]
        }
    data_visuals = [
        v["name"]
        for v in p.visuals
        if v["visual"]["visualType"] not in ("image", "textbox", "actionButton", "pageNavigator", "shape")
    ]
    if len(data_visuals) > 1:
        page["visualInteractions"] = [
            {"source": s, "target": d, "type": "DataFilter"} for s in data_visuals for d in data_visuals if s != d
        ]
    (folder / "page.json").write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
    for v in p.visuals:
        vf = folder / "visuals" / v["name"]
        vf.mkdir()
        (vf / "visual.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
    order.append(p.name)


def write_report(page_names):
    rj = json.loads((DEF / "report.json").read_text(encoding="utf-8"))
    rj["themeCollection"]["customTheme"] = {
        "name": "u2-theme.json",
        "reportVersionAtImport": rj["themeCollection"]["baseTheme"]["reportVersionAtImport"],
        "type": "RegisteredResources",
    }
    items = [{"name": "u2-theme.json", "path": "u2-theme.json", "type": "CustomTheme"}]
    for stale in RES.iterdir():  # drop images no visual uses any more, so fabric/ matches the workspace
        if stale.is_file() and stale.name != "u2-theme.json" and stale.name not in REGISTERED:
            stale.unlink()
    for f in sorted(REGISTERED):
        shutil.copyfile(IMAGES / f, RES / f)
        items.append({"name": f, "path": f, "type": "Image"})
    pk = [p for p in rj["resourcePackages"] if p["name"] != "RegisteredResources"]
    pk.append({"name": "RegisteredResources", "type": "RegisteredResources", "items": items})
    rj["resourcePackages"] = pk
    rj["publicCustomVisuals"] = sorted(set(rj.get("publicCustomVisuals", [])) | {HTML, DENEB})
    (DEF / "report.json").write_text(json.dumps(rj, indent=4, ensure_ascii=False), encoding="utf-8")
    ext = {
        "$schema": S_EXT,
        "name": "extension",
        "entities": [{"name": e, "measures": ms} for e, ms in EXT_MEASURES.items()],
    }
    (DEF / "reportExtensions.json").write_text(json.dumps(ext, indent=2, ensure_ascii=False), encoding="utf-8")
    pages = {"$schema": S_PAGES, "pageOrder": page_names, "activePageName": page_names[0]}
    (DEF / "pages" / "pages.json").write_text(json.dumps(pages, indent=2), encoding="utf-8")
    # remove page folders that are no longer generated
    for d in (DEF / "pages").iterdir():
        if d.is_dir() and d.name not in page_names:
            shutil.rmtree(d)


GLYPH_PATHS = read_csv(IMAGES / "glyph_paths.csv")
TOURS_SEED = read_csv(ROOT / "seeds" / "tours.csv")
SPIKE_JPEG = ""

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spike-jpeg", help="path of a tiny JPEG inlined as base64 in the spike measure")
    a = ap.parse_args()
    if a.spike_jpeg:
        SPIKE_JPEG = __import__("base64").b64encode(Path(a.spike_jpeg).read_bytes()).decode()
    order = []
    builders = [
        page_overview,
        page_road,
        page_songs,
        page_albums,
        page_setlists,
        page_sphere,
        page_song_detail,
        page_show_detail,
        page_about,
        page_spike,
    ]
    for b in builders:
        write_page(b(), order)
    write_report(order)
    print(
        "pages:",
        order,
        "| registered images:",
        len(REGISTERED),
        "| extension measures:",
        sum(len(v) for v in EXT_MEASURES.values()),
    )

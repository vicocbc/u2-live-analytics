"""Generate the PBIR pages of rpt_u2_live from the wireframes (docs/design/wireframes.md).

Why a generator: no visual was ever created in Desktop to copy from, and ~60 visuals share the same formatting.
Every visual gets a stable name (folder name), position on the 8 px grid, alt text and tab order.
Writes into fabric/rpt_u2_live.Report/:
  definition/report.json            theme (RegisteredResources/u2-theme.json), registered images, custom visuals
  definition/pages/<page>/...       page.json + visuals/<visual>/visual.json
  StaticResources/RegisteredResources/<image files>
No report-level measures: every measure a visual uses lives in the semantic model sm_u2_live (Power BI "Publish to
web" rejects reports with report-level measures). The report-support measures (HTML blocks, titles, colours, ranks)
are owned by the data-analyst: SPEC-05 "Report-support measures (Publish to web)", display folders Report/pNN.
Usage: python scripts/gen_report.py
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


def meas(entity, prop):
    """Reference to a model measure (sm_u2_live)."""
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


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


def placeholder(name):
    """Model measure 'ph <name>' (forwards to [<name>]; kept so the text cards keep their binding)."""
    return meas("fact_show", f"ph {name}")


# ---------------------------------------------------------------- visual builder
class Page:
    def __init__(self, name, display, drill=None, hidden=False):
        self.name, self.display, self.drill, self.hidden = name, display, drill, hidden
        self.visuals, self.z = [], 0
        self.filter_pairs = None  # None: every data visual filters every other; else only these (source, target)

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


def wrap(field, suffix):
    """Model measure '<measure> · <suffix>': presentation wrapper (HTML typography or clipping) around a measure."""
    return meas(FS, f"{field['Measure']['Property']} · {suffix}")


def card_text(page, vname, x, y, w, h, field, alt=None):
    """A text measure (headline, callout, note) in HTML Content Secure, through its model wrapper measure
    '<measure> · <vname>' (typography and clipping, so the visual never shows a scrollbar)."""
    return html(page, vname, x, y, w, h, wrap(field, vname), alt=alt or "Text", clip=False)


def html(page, vname, x, y, w, h, field, alt, filters=None, clip=True, links=False):
    """HTML Content Secure visual. clip=True binds the model measure '<measure> · <vname>' (fixed-height,
    overflow-hidden wrapper) instead of the measure itself."""
    if clip:
        field = wrap(field, vname)
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
                        "fontSize": lit(9),
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
            "layout": props(cellPadding=lit(0)),  # 8 tabs share the width: no gaps, so every label stays whole
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


def title_measure(name):
    """Model measure with a visual title stating the cut and the total, e.g. 'All 384 cities, most shows first'."""
    return meas(FS, name)


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
    glyph = (IMAGES / "glyph_zoo_tv.svg").read_text(encoding="utf-8").strip().replace('"', "'")
    m = meas("fact_show", "Spike HTML")
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
    """Model measure: three KPI tiles (icon, number, delta vs previous era)."""
    return meas(FS, "KPI Tiles p01")


def color_measure(name):
    """Model measure returning a hex colour for conditional formatting."""
    return meas(FS, name)


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


def photo_card_measure(name):
    """Model measure: HTML photo card (base64 photo, gradient, number, caption, credit)."""
    return meas(FS, name)


def page_header(p, x=40, w=600, nav_w=None, h=152):
    """Navigation, then the model measure 'Header pNN' (headline up to two lines and intro up to three lines in one
    HTML block, so a one-line headline leaves no gap above the intro)."""
    nav(p, x, 6, nav_w or min(w, 720))
    html(
        p, f"{p.name[:3]}_headline", x, 54, w, h, meas(FS, f"Header {p.name[:3]}"), alt="Page headline and introduction"
    )


def measure_filter(field, more_than, name, kind=1):
    """Visual filter: measure > more_than (Advanced filter)."""
    ent = field["Measure"]["Expression"]["SourceRef"]["Entity"]
    return {
        "name": name,
        "field": field,
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [{"Name": "m", "Entity": ent, "Type": 0}],
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


def topn_filter(field, by, n, name):
    """Exact Top N: model rank measure 'Rank <k> <column> by <measure>' (ties broken by name), filter rank <= n."""
    c = field["Column"]
    m = by["Measure"]["Property"]
    RANK_COUNT[0] += 1
    rank = meas(FS, f"Rank {RANK_COUNT[0]} {c['Property']} by {m}")
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
    page_header(p, w=580, nav_w=760)
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
    top_color = color_measure("Top Song Bar Color")
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
        title=title_measure("Title p01 top10"),
        filters=[topn_filter(col("dim_song", "song_title"), meas(FP, "Performances"), 10, "top10")],
        fill=fill_by(top_color),
        margin=75,
    )
    footer(p, 40, 840)
    return p


# ---------------------------------------------------------------- page 2
def page_road():
    p = Page("p02_on_the_road", "Road")
    page_header(p, w=720, h=96)
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
    city = meas(FS, "Top City Card p02")
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
        title=title_measure("Title p02 cities"),
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
        title=title_measure("Title p02 shows"),
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
        alt="The most played song and how often",
    )
    page_header(p, x=552, w=704)
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
        title=title_measure("Title p03 songs"),
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
        title=title_measure("Title p03 rarities"),
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
        title=title_measure("Title p03 covers"),
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
        title=title_measure("Title p03 guests"),
        widths=[300, 60],
    )
    footer(p, 552, 704)
    return p


# ---------------------------------------------------------------- page 4
def page_albums():
    p = Page("p04_albums_on_stage", "Albums")
    page_header(p, w=736)
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
    card_text(p, "p04_area_note", 400, 206, 376, 24, placeholder("Annotation p04"))
    studio = basic_filter(col("dim_album", "album_type"), ["studio"], "studio")
    share = meas(FP, "Album Share (no zeros)")
    cell = meas(FP, "Album Share Cell")
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
        title=title_measure("Title p04 albums"),
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
    card = photo_card_measure("Photo Card p04")
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
    album = meas(FS, "Promoted Album Label")
    has_album = meas(FS, "Has Promoted Album")
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
        title=title_measure("Title p04 tours"),
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
    page_header(p, w=760)
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
        title=title_measure("Title p05 heatmap"),
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
        title=title_measure("Title p05 variety"),
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
        title=title_measure("Title p05 openers"),
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
    res = meas(FS, "Residency Callouts p06")
    html(p, "p06_residency_callouts", 32, 568, 470, 128, res, alt="Residency: shows, songs a night, Achtung Baby share")
    page_header(p, x=560, w=696)

    h2h = meas(FS, "Head to Head p06")
    html(p, "p06_head_to_head", 560, 212, 696, 188, h2h, alt="Residency versus touring: songs a night, songs, share")
    text(p, "p06_compare_label", 560, 414, 120, 18, [[("COMPARE WITH", style(9, T["muted"], weight="bold"))]])
    slicer(p, "p06_compare_slicer", 664, 404, 240, 36, col("dim_tour", "tour_name_display"), "Tours to compare with")
    card_text(p, "p06_note", 920, 410, 336, 28, placeholder("Annotation p06"))
    year_dec = meas(FS, "Show Year Decimal")
    songs = meas(FS, "Songs in Show p06")
    dot_colour = meas(FS, "Show Dot Colour p06")
    title = meas(FS, "Title p06 every show")
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
    nav(p, 40, 6, 656)
    back_button(p, 704, 12)
    card = meas(FS, "Song Card p07")
    one_song = meas(FS, "Is One Song")
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
        title=title_measure("Title p07 shows"),
    )

    pos = meas(FS, "Position p07")
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
    nav(p, 40, 6, 656)
    back_button(p, 704, 12)
    # songs in setlist order; a set header is printed whenever the set changes from the previous position

    ticket = meas(FS, "Ticket p08")
    html(p, "p08_ticket", 40, 56, 840, 616, ticket, alt="Ticket for the selected show: tour, date, venue, setlist")
    link = meas(FS, "Setlist Link p08")
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
    author = meas(FS, "Author p09")
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
    lim = meas(FS, "Limitations p09")
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


# ---------------------------------------------------------------- page 10
FSP, FSB = "fact_setlist_prediction", "fact_setlist_backtest"


def page_next_tour():
    """Page 10 (SPEC-09 §9.8, Q12): the predicted 2027 setlist, the new material, how good the model was in the
    backtest, and (from the first show on) predicted vs played. Left: story column with the setlist ticket (anchor).
    Right: new songs, backtest, in-tour tracker."""
    p = Page("p10_next_tour", "2027")  # short tab label: 8 tabs share navs as narrow as 656 px
    lw, rx, rw = 656, 736, 520  # left column width (x 40), right column x and width
    nav(p, 40, 6, 696)  # wider than the column: with a selected tab, 656 px cut "Overview" (T-52)
    header = meas(FS, "Header p10")
    html(p, "p10_headline", 40, 54, lw, 144, header, alt="Page headline and introduction")

    # ---- predicted setlist ticket (anchor): header band with the tour glyph and numbers, setlist in two columns

    ticket = meas(FS, "Ticket p10")
    html(
        p,
        "p10_setlist_ticket",
        40,
        208,
        lw,
        480,
        ticket,
        alt="Predicted setlist of the next tour in order, main set and encore, with each song's chance; new songs "
        "tagged NEW",
    )

    # ---- new material: all 25 songs of the 2026 releases with their chance
    release = meas(FS, "Release p10")
    picked = meas(FS, "In Setlist p10")
    song_colour = meas(FS, "Song Colour p10")
    new_title = meas(FS, "Title p10 new songs")
    chance = named(meas(FSP, "Predicted Probability"), "Chance")
    new_fields = [
        named(release, "Release"),
        named(col("dim_song", "song_title"), "Song"),
        chance,
        named(picked, "Setlist"),
    ]
    table(
        p,
        "p10_new_songs_table",
        rx,
        16,
        rw,
        216,
        new_fields,
        "All 25 songs of the 2026 album and EPs by release, with each song's chance; songs in the predicted setlist "
        "in amber and marked picked; right-click a song for its story",
        sort=[(release, "Ascending"), (chance, "Descending")],
        filters=[basic_filter(col("dim_song", "release_role_2027"), ["promoted_album", "companion_release"], "new")],
        title=new_title,
        widths=[104, 176, 92, 78],  # 450 px: room for the vertical scrollbar, no horizontal one; 78 fits "✓ picked"
        extra_objects={
            "values": [
                *props(
                    wordWrap=lit(False),
                    backColorPrimary=color(T["bg"]),
                    backColorSecondary=color(T["bg"]),
                    fontColorPrimary=color(T["text"]),
                    fontColorSecondary=color(T["text"]),
                ),
                {
                    "properties": {"fontColor": {"solid": {"color": {"expr": song_colour}}}},
                    "selector": {
                        "data": [{"dataViewWildcard": {"matchingOption": 1}}],
                        "metadata": "dim_song.song_title",
                    },
                },
            ],
            "columnFormatting": [data_bars(f"{FSP}.Predicted Probability")],
        },
    )

    ties = meas(FS, "Ties Note p10")
    card_text(p, "p10_ties_note", rx, 236, rw, 36, ties, alt="Note on tied new songs")

    # ---- how good is this? backtest
    good = meas(FS, "Backtest Intro p10")
    html(p, "p10_backtest_intro", rx, 280, rw, 56, good, alt="How good is the model: lead over the simple baseline")

    # backtest precision per method as labelled HTML bars (the native bar chart did not render at this size, T-52)

    bars = meas(FS, "Backtest Bars p10")
    html(
        p,
        "p10_backtest_bars",
        rx,
        340,
        rw,
        112,
        bars,
        alt="Backtest precision on the album tours since Elevation: the model against the three simple baselines",
    )
    ei = meas(FS, "Closest Analog Note p10")
    card_text(p, "p10_analog_note", rx, 456, rw, 36, ei, alt="Note on the closest analog tour")

    # ---- from the first show on: predicted vs played, and how the chances move (empty until the first show)
    started = meas(FS, "Tour Started p10")
    tracker = meas(FS, "Tracker Intro p10")
    html(p, "p10_tracker_intro", rx, 500, rw, 44, tracker, alt="Once the tour starts: predicted versus played")

    def line(vname, x, y_field, alt, title, series=None, filters=None):
        roles = {"Category": [named(col("dim_date", "date"), "Date")], "Y": [y_field]}
        obj = {
            "lineStyles": props(lineChartType=lit("straight"), strokeWidth=lit(2), showMarker=lit(True)),
            "valueAxis": props(
                show=lit(True), gridlineShow=lit(False), labelColor=color(T["muted"]), start=lit(0), end=lit(1)
            ),
            "categoryAxis": props(
                show=lit(True), gridlineShow=lit(False), labelColor=color(T["muted"]), fontSize=lit(9)
            ),
        }
        if series:
            roles["Series"] = [series]
            obj["legend"] = props(show=lit(True), position=lit("Top"), labelColor=color(T["muted"]), fontSize=lit(8))
        else:
            obj["dataPoint"] = props(fill=color(T["accent"]))
        return p.add(
            vname,
            "lineChart",
            x,
            548,
            (rw - 16) // 2,
            140,
            roles=roles,
            alt=alt,
            title=title,
            filters=filters,
            objects=obj,
            vco={"background": props(show=lit(False))},
        )

    line(
        "p10_hit_rate_line",
        rx,
        named(meas(FSP, "Hit Rate"), "Predicted songs played"),
        "Per show of the tour: share of the predicted songs that were played (empty before the first show)",
        "Predicted vs played, per show",
    )
    line(
        "p10_chance_line",
        rx + (rw + 16) // 2,
        named(meas(FSP, "Predicted Probability"), "Average chance"),
        "Average chance of the picked songs after each show, new versus older songs (empty before the first show)",
        "How the chances move (click a new song)",
        series=named(col(FSP, "model_part"), "Songs"),
        filters=[
            bool_filter(col(FSP, "predicted_in_setlist"), True, "picked"),
            measure_filter(started, 0, "started"),
        ],
    )
    # the prediction story and the backtest are separate stories: only the new-song table filters the chance chart
    p.filter_pairs = {("p10_new_songs_table", "p10_chance_line")}
    footer(p, 40, lw, note="Prediction model and backtest: SPEC-09")
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
            {
                "source": s,
                "target": d,
                "type": "DataFilter" if p.filter_pairs is None or (s, d) in p.filter_pairs else "NoFilter",
            }
            for s in data_visuals
            for d in data_visuals
            if s != d
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
    (DEF / "report.json").write_text(json.dumps(rj, indent=2, ensure_ascii=False), encoding="utf-8")
    # no report-level measures (Publish to web rejects them): every measure lives in sm_u2_live
    (DEF / "reportExtensions.json").unlink(missing_ok=True)
    pages = {"$schema": S_PAGES, "pageOrder": page_names, "activePageName": page_names[0]}
    (DEF / "pages" / "pages.json").write_text(json.dumps(pages, indent=2), encoding="utf-8")
    # remove page folders that are no longer generated
    for d in (DEF / "pages").iterdir():
        if d.is_dir() and d.name not in page_names:
            shutil.rmtree(d)


GLYPH_PATHS = read_csv(IMAGES / "glyph_paths.csv")

if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
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
        page_next_tour,
    ]
    for b in builders:
        write_page(b(), order)
    # shown before About in the navigation
    order.remove("p10_next_tour")
    order.insert(order.index("p09_about"), "p10_next_tour")
    write_report(order)
    print(
        "pages:",
        order,
        "| registered images:",
        len(REGISTERED),
    )

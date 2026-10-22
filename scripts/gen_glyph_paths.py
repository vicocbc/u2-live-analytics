"""Convert the tour glyph SVGs to single path strings for Deneb (Vega-Lite point marks with a custom `shape`).

Reads docs/design/images/glyph_*.svg (circle, ellipse, rect, path; optional rotate() on ellipses) and writes
docs/design/images/glyph_paths.csv with, per tour_name:
  path_48   - one SVG path in the glyphs' 48 x 48 box (stroke-only, no fill)
  path_unit - the same path scaled to the [-1, 1] box Vega-Lite expects for custom point shapes
Usage: python scripts/gen_glyph_paths.py
"""

import csv
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "design" / "images"

# tour_name (setlist.fm value, as in seeds/tours.csv) -> glyph file slug
TOURS = {
    "Early Days": "early_days",
    "U2-3": "u2_3",
    "11 O'Clock Tick Tock": "11_oclock_tick_tock",
    "Boy": "boy",
    "October Tour": "october",
    "Pre-War Tour": "pre_war",
    "War": "war",
    "The Unforgettable Fire": "unforgettable_fire",
    "A Conspiracy of Hope": "conspiracy_of_hope",
    "Joshua Tree Promo Tour": "joshua_tree_promo",
    "The Joshua Tree": "joshua_tree_1987",
    "Lovetown": "lovetown",
    "Zoo TV": "zoo_tv",
    "Popmart Tour": "popmart",
    "Elevation": "elevation",
    "How to Dismantle an Atomic Bomb Promo Tour": "atomic_bomb_promo",
    "Vertigo": "vertigo",
    "U2 360°": "u2_360",
    "iNNOCENCE + eXPERIENCE Tour": "innocence_experience",
    "The Joshua Tree Tour 2017": "joshua_tree_2017",
    "eXPERIENCE + iNNOCENCE Tour": "experience_innocence",
    "The Joshua Tree Tour 2019": "joshua_tree_2019",
    "U2:UV Achtung Baby Live at Sphere": "sphere",
    "Carnival De Luz Promo": "carnaval_de_luz_promo",
    "(No tour)": "no_tour",
}
NS = "{http://www.w3.org/2000/svg}"
NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def fmt(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def ellipse(cx, cy, rx, ry, rot=0.0):
    """Two arcs; rotation about the centre via the arc x-axis-rotation and rotated end points."""
    a = math.radians(rot)
    dx, dy = rx * math.cos(a), rx * math.sin(a)
    return (
        f"M{fmt(cx - dx)} {fmt(cy - dy)}A{fmt(rx)} {fmt(ry)} {fmt(rot)} 1 0 {fmt(cx + dx)} {fmt(cy + dy)}"
        f"A{fmt(rx)} {fmt(ry)} {fmt(rot)} 1 0 {fmt(cx - dx)} {fmt(cy - dy)}Z"
    )


def rect(x, y, w, h, r=0.0):
    if not r:
        return f"M{fmt(x)} {fmt(y)}h{fmt(w)}v{fmt(h)}h{fmt(-w)}Z"
    return (
        f"M{fmt(x + r)} {fmt(y)}h{fmt(w - 2 * r)}a{fmt(r)} {fmt(r)} 0 0 1 {fmt(r)} {fmt(r)}v{fmt(h - 2 * r)}"
        f"a{fmt(r)} {fmt(r)} 0 0 1 {fmt(-r)} {fmt(r)}h{fmt(-(w - 2 * r))}a{fmt(r)} {fmt(r)} 0 0 1 {fmt(-r)} {fmt(-r)}"
        f"v{fmt(-(h - 2 * r))}a{fmt(r)} {fmt(r)} 0 0 1 {fmt(r)} {fmt(-r)}Z"
    )


def element_paths(svg_file):
    root = ET.parse(svg_file).getroot()
    out = []
    for el in root.iter():
        tag = el.tag.replace(NS, "")
        g = lambda k, d=0.0, el=el: float(el.get(k, d))  # noqa: E731
        if tag == "path":
            out.append(el.get("d"))
        elif tag == "circle":
            out.append(ellipse(g("cx"), g("cy"), g("r"), g("r")))
        elif tag == "ellipse":
            rot = 0.0
            m = re.search(r"rotate\((" + NUM + r")", el.get("transform", ""))
            if m:
                rot = float(m.group(1))
            out.append(ellipse(g("cx"), g("cy"), g("rx"), g("ry"), rot))
        elif tag == "rect":
            out.append(rect(g("x"), g("y"), g("width"), g("height"), g("rx")))
    return "".join(out)


ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def tokenize(d):
    """Path tokens; arc flags are single characters (compact forms like 'a9 9 0 0118 0' are legal SVG)."""
    tokens, pos, cmd, k = [], 0, None, 0
    while pos < len(d):
        c = d[pos]
        if c in " ,\t\n":
            pos += 1
        elif c.isalpha():
            cmd, k = c, 0
            tokens.append(c)
            pos += 1
        elif cmd and cmd.upper() == "A" and k % 7 in (3, 4):
            tokens.append(c)
            pos += 1
            k += 1
        else:
            m = re.match(NUM, d[pos:])
            tokens.append(m.group(0))
            pos += len(m.group(0))
            k += 1
    return tokens


def to_unit(d):
    """Scale a path from the 48 box to [-1, 1]: absolute x' = (x - 24) / 24, relative dx' = dx / 24."""
    tokens = tokenize(d)
    out, cmd, i, args = [], None, 0, []
    arity = ARITY
    while i < len(tokens):
        t = tokens[i]
        if re.fullmatch(r"[A-Za-z]", t):
            cmd = t
            out.append(cmd)
            i += 1
            if cmd in "Zz":
                continue
        n = arity[cmd.upper()]
        args = [float(x) for x in tokens[i : i + n]]
        i += n
        rel = cmd.islower()
        u = cmd.upper()
        new = []
        for k, v in enumerate(args):
            if u == "A" and k in (2, 3, 4):  # rotation and flags unchanged
                new.append(v)
            elif (u == "A" and k in (0, 1)) or rel:  # radii scale
                new.append(v / 24)
            else:
                new.append((v - 24) / 24)
        out.append(" ".join(fmt(v) if not (u == "A" and k in (3, 4)) else str(int(v)) for k, v in enumerate(new)) + " ")
    return "".join(out).replace(" M", "M").strip()


rows = []
for tour, slug in TOURS.items():
    d48 = element_paths(IMAGES / f"glyph_{slug}.svg")
    rows.append({"tour_name": tour, "glyph_file": f"glyph_{slug}.svg", "path_48": d48, "path_unit": to_unit(d48)})
with open(IMAGES / "glyph_paths.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["tour_name", "glyph_file", "path_48", "path_unit"])
    w.writeheader()
    w.writerows(rows)
print(len(rows), "paths written")

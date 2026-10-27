"""Renders a plan as an in-game-style card: equipment, inventory and route maps (HTML).

Usage:
  python card.py plan.json --rsn NAME [--title "Optimal herb run"] [--out file.html]

Reads the same plan JSON as `check.py plan`. Items may carry an optional
"note" (shown on hover), e.g. {"item": "Ectophial", "note": "Stage 3: Ghosts Ahoy"};
equipment entries may be a name or {"item": ..., "note": ...}.

An optional "route" adds an overview map and one map per leg:
  "route": [{"title": "Ardougne herb patch", "method": "Ardougne cloak teleport",
             "arrive": [2665, 3374, 0], "target": [2667, 3375, 0],
             "note": "patch is right there", "locked": "Stage 3", "short": "Ardougne"}]
"arrive" is where the method lands (transport.py find), "target" is the
destination (wiki.py coords). Optional: "locked" marks a leg the account
can't use yet; "mapid" picks the wiki map for underground legs (wiki.py
coords prints it; defaults to the dungeon map for y >= 6400). A leg without
"target" is listed as text only.

Each item is drawn by status against the snapshot: owned and in place, in the
bank ("bank" badge), or missing (greyed out). The output is one self-contained
HTML file (icons embedded), printed as its path.
"""
import argparse
import base64
import html
import json
import re
import sys
from pathlib import Path

import check
import maps
import wiki

# Equipment screen layout as in game: (row, column) per wiki equipment slot.
EQUIP_LAYOUT = {
    "head": (0, 1),
    "cape": (1, 0), "neck": (1, 1), "ammo": (1, 2),
    "weapon": (2, 0), "body": (2, 1), "shield": (2, 2),
    "legs": (3, 1),
    "hands": (4, 0), "feet": (4, 1), "ring": (4, 2),
}
SLOT_LABEL = {"neck": "amulet", "hands": "gloves", "feet": "boots"}
DEFAULT_OUT = (Path.home() / "Documents" if (Path.home() / "Documents").exists() else Path.home()) / "osrs-agent-cards"

CSS = """
body { background:#1e1a14; color:#e8dcc0; font:14px/1.4 system-ui, sans-serif; margin:24px; }
h1 { font-size:20px; margin:0 0 4px; } .sub { color:#b8a888; margin-bottom:18px; }
.panels { display:flex; gap:24px; flex-wrap:wrap; align-items:flex-start; }
.panel { background:#3e3529; border:3px solid #5a4d3c; border-radius:6px; padding:10px; box-shadow:inset 0 0 0 2px #2a241b; }
.panel h2 { font-size:13px; text-transform:uppercase; letter-spacing:.08em; color:#ff981f; margin:0 0 8px; text-align:center; }
.inv { display:grid; grid-template-columns:repeat(4, 42px); gap:4px 8px; }
.equip { display:grid; grid-template-columns:repeat(3, 42px); grid-template-rows:repeat(5, 42px); gap:6px 14px; }
.slot { width:42px; height:38px; position:relative; display:flex; align-items:center; justify-content:center; }
.equip .slot { background:#2e281f; border:1px solid #1a1611; border-radius:4px; }
.equip .slot.empty::after { content:attr(data-slot); font-size:9px; color:#6b5e4a; }
.slot img { image-rendering:pixelated; max-width:36px; max-height:32px; }
.qty { position:absolute; top:-2px; left:1px; font:bold 11px/1 monospace; text-shadow:1px 1px 0 #000; }
.qty.k { color:#fff; } .qty.m { color:#00ff80; } .qty.n { color:#ffff00; }
.missing img { filter:grayscale(.85) brightness(.8); opacity:.75; }
.missing { outline:1px dashed #a33; outline-offset:-2px; border-radius:4px; }
.badge { position:absolute; bottom:-3px; right:-4px; font-size:8px; font-weight:bold; padding:0 3px; border-radius:3px; text-transform:uppercase; }
.badge.bank { background:#2a62c9; color:#fff; } .badge.equip { background:#2a8c4a; color:#fff; }
.legend { margin-top:18px; color:#b8a888; font-size:12px; display:flex; gap:18px; flex-wrap:wrap; }
.legend span::before { content:""; display:inline-block; width:10px; height:10px; margin-right:5px; vertical-align:-1px; border-radius:2px; }
.l-own::before { background:#e8dcc0; } .l-bank::before { background:#2a62c9; }
.l-equip::before { background:#2a8c4a; } .l-miss::before { border:1px dashed #a33; }
.over { color:#ff5050; font-weight:bold; }
.credits { margin-top:18px; color:#7d705a; font-size:11px; }
"""


def entry(e):
    return {"item": e, "qty": 1} if isinstance(e, str) else {"qty": 1, **e}


def qty_label(n):
    if n < 100000:
        return str(n), "n"
    if n < 10000000:
        return "{}K".format(n // 1000), "k"
    return "{}M".format(n // 1000000), "m"


ICON_PATHS = False


def icon_uri(name, qty):
    try:
        path = wiki.icon_file(name, qty)
    except (wiki.WikiError, OSError):
        return None
    if ICON_PATHS:
        return path.as_posix()
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def slot_html(name, qty, status, note, show_qty, slot_key=None):
    uri = icon_uri(name, qty)
    tip = {"own": "", "bank": " — withdraw from bank", "equip": " — equip from inventory/bank",
           "missing": " — NOT OWNED"}[status]
    title = "{}{}{}".format(name + (" x{}".format(qty) if qty > 1 else ""), tip, " — " + note if note else "")
    img = '<img src="{}" alt="{}">'.format(uri, html.escape(name)) if uri else '<span style="font-size:9px">{}</span>'.format(html.escape(name))
    q = ""
    if show_qty:
        text, cls = qty_label(qty)
        q = '<span class="qty {}">{}</span>'.format(cls, text)
    badge = '<span class="badge {0}">{0}</span>'.format(status) if status in ("bank", "equip") else ""
    attrs = ' data-slot="{}"'.format(slot_key) if slot_key else ""
    return '<div class="slot{}" title="{}"{}>{}{}{}</div>'.format(
        " missing" if status == "missing" else "", html.escape(title), attrs, img, q, badge)


def render(plan, snap, title):
    containers = check.container_items(snap)

    equip_cells = {}
    for e in map(entry, plan.get("equipment", [])):
        try:
            slot = check.wiki_equip_slot(e["item"])
        except wiki.WikiError:
            slot = None
        if slot not in EQUIP_LAYOUT:
            print("warning: no equipment slot for {!r}; left off the card".format(e["item"]), file=sys.stderr)
            continue
        if slot in equip_cells:
            print("warning: {!r} clashes with an earlier item in the {} slot; left off the card".format(e["item"], slot), file=sys.stderr)
            continue
        where = check.find_item(containers, e["item"])
        status = "own" if "equipment" in where else ("equip" if where else "missing")
        equip_cells[slot] = slot_html(e["item"], 1, status, e.get("note"), False)

    equip = []
    for slot, (row, col) in EQUIP_LAYOUT.items():
        cell = equip_cells.get(slot) or '<div class="slot empty" data-slot="{}"></div>'.format(SLOT_LABEL.get(slot, slot))
        equip.append(cell.replace('<div class="slot', '<div style="grid-row:{};grid-column:{}" class="slot'.format(row + 1, col + 1), 1))

    inv, used = [], 0
    for e in map(entry, plan.get("inventory", [])):
        where = check.find_item(containers, e["item"])
        have = sum(n for loc, n in where.items() if loc != "equipment")
        status = "own" if where.get("inventory", 0) >= e["qty"] else ("bank" if have >= e["qty"] else "missing")
        if e.get("stackable") or e.get("noted") or e["qty"] == 1:
            inv.append(slot_html(e["item"], e["qty"], status, e.get("note"), e["qty"] > 1))
            used += 1
        else:
            inv.extend(slot_html(e["item"], 1, status, e.get("note"), False) for _ in range(e["qty"]))
            used += e["qty"]
    inv.extend('<div class="slot"></div>' for _ in range(max(0, 28 - used)))

    slots = '<span class="{}">{}/28 slots</span>'.format("over" if used > 28 else "", used)
    route = maps.route_html(plan["route"]) if plan.get("route") else ""
    return """<!doctype html><html><head><meta charset="utf-8"><title>{title}</title><style>{css}</style></head><body>
<h1>{title}</h1>
<div class="sub">{rsn} ({type}) · snapshot {age} · {slots}</div>
<div class="panels">
<div class="panel"><h2>Worn equipment</h2><div class="equip">{equip}</div></div>
<div class="panel"><h2>Inventory</h2><div class="inv">{inv}</div></div>
</div>
<div class="legend"><span class="l-own">in place</span><span class="l-equip">owned, equip it</span><span class="l-bank">in bank, withdraw</span><span class="l-miss">not owned (hover for how to get it)</span></div>
{route}
<div class="credits">Icons and map tiles: OSRS Wiki. Transport data: Shortest Path plugin (BSD-2). Paths: walking routes over the game collision map; dashed straight arrows mark legs with no walking path.</div>
</body></html>""".format(title=html.escape(title), css=CSS + maps.CSS, rsn=html.escape(snap.get("rsn", "?")),
                         type=snap.get("accountType"), age=check.age(snap.get("capturedAt")), slots=slots,
                         equip="".join(equip), inv="".join(inv), route=route)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", help="plan JSON (same format as check.py plan), or - for stdin")
    parser.add_argument("--rsn")
    parser.add_argument("--title", default="Loadout")
    parser.add_argument("--out", help="output HTML path (default: {}/<rsn>-<title>.html)".format(DEFAULT_OUT))
    parser.add_argument("--exclude", action="append", default=[], metavar="CONTAINER")
    parser.add_argument("--icon-paths", action="store_true",
                        help="reference cached icon files by path instead of embedding them (smaller; local viewing only)")
    parser.add_argument("--inline", action="store_true",
                        help="no page background or margins, for viewers that frame the card themselves")
    args = parser.parse_args(argv)
    global ICON_PATHS
    ICON_PATHS = args.icon_paths
    maps.EMBED = not args.icon_paths

    try:
        plan = json.loads(sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8"))
        snap = check.load_snapshot(args.rsn)
        for key in args.exclude:
            snap.get("containers", {}).pop(key, None)
        page = render(plan, snap, args.title)
        if args.inline:
            page = page.replace("body { background:#1e1a14; color:#e8dcc0; font:14px/1.4 system-ui, sans-serif; margin:24px; }",
                                "body { color:#e8dcc0; margin:0; } .wrap { background:#1e1a14; padding:16px; border-radius:8px; }")
            page = page.replace("<body>", '<body><div class="wrap">').replace("</body>", "</div></body>")
    except (check.CheckError, wiki.WikiError, json.JSONDecodeError) as e:
        print("error: {}".format(e), file=sys.stderr)
        return 1

    slug = re.sub(r"[^a-z0-9]+", "-", "{}-{}".format(snap.get("rsn", ""), args.title).lower()).strip("-")
    out = Path(args.out) if args.out else DEFAULT_OUT / (slug + ".html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

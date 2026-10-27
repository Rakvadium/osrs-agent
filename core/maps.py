"""Route maps built from the OSRS Wiki's map tiles, with markers, labels and walking paths.

Used by card.py for plans with a "route". Each leg is drawn on its own map:
where the teleport lands, where you're going, and the walking path between
them (pathfind.py over the game's collision map). When no walking path is
found (stairs, a transport, an unmapped area), a straight dashed arrow shows
the direction instead, and the leg says so. An overview map numbers every
leg's destination.

Tiles: https://maps.runescape.wiki/osrs/versions/<version>/tiles/rendered/<mapid>/<zoom>/<plane>_<x>_<y>.png
are 256 px, at 2**zoom px per game square (zoom -1..3), so tile (tx, ty)
covers game squares x in [tx*S, (tx+1)*S) and y in [ty*S, (ty+1)*S),
S = 256 / 2**zoom, with north at the top.
"""
import base64
import html
import math
import re
import urllib.error
import urllib.request

import pathfind
import wiki

TILE_ROOT = "https://maps.runescape.wiki/osrs/versions/{version}/tiles/rendered/{mapid}/{zoom}/{plane}_{x}_{y}.png"
TILE_DIR = wiki.CACHE_DIR / "tiles"
DAY = 24 * 3600

CSS = """
.route { margin-top:16px; }
.route h2.title { font-size:15px; color:#ff981f; text-transform:uppercase; letter-spacing:.08em; margin:0 0 10px; }
.legs { display:grid; grid-template-columns:repeat(auto-fill, minmax(min(340px, 100%), 1fr)); gap:16px; margin-top:16px; }
.leg { background:#3e3529; border:3px solid #5a4d3c; border-radius:6px; overflow:hidden; min-width:0; }
.leg .head { padding:8px 10px 6px; }
.leg .head b { color:#ff981f; } .leg .head .how { color:#e8dcc0; } .leg .head .note { color:#b8a888; font-size:12px; }
.leg .lock { display:inline-block; font-size:10px; font-weight:bold; background:#7a2e2e; color:#fff; border-radius:3px; padding:0 5px; margin-left:6px; vertical-align:1px; }
.map { background:#0e2a3a; }
.map svg { display:block; width:100%; height:auto; }
.map image { image-rendering:pixelated; }
.map text { font:bold 12px system-ui, sans-serif; paint-order:stroke; stroke:#000; stroke-width:3px; }
.overview .map { border:3px solid #5a4d3c; border-radius:6px; overflow:hidden; max-width:700px; }
/* Maps scale down on phones; enlarge the overview's labels so they stay readable. */
@media (max-width: 600px) { .overview .map text { font-size:20px; stroke-width:5px; } }
"""

_version = None
EMBED = True


def map_version():
    """The wiki's current map tile version, read from any page with a map."""
    global _version
    if _version is None:
        data = wiki.fetch_json(wiki.API, {"action": "parse", "page": "Allotment patch/Patches", "prop": "text", "format": "json"}, ttl=DAY)
        m = re.search(r"maps\.runescape\.wiki/osrs/versions/([^/]+)/tiles", data["parse"]["text"]["*"])
        if not m:
            raise wiki.WikiError("Could not find the wiki's map version")
        _version = m.group(1)
    return _version


def tile_src(mapid, zoom, plane, tx, ty):
    """Cached tile as an <img> src (data URI or file path), or None for empty ocean/void."""
    version = map_version()
    path = TILE_DIR / version / str(mapid) / str(zoom) / "{}_{}_{}.png".format(plane, tx, ty)
    missing = path.with_suffix(".none")
    if missing.exists():
        return None
    if not path.exists():
        url = TILE_ROOT.format(version=version, mapid=mapid, zoom=zoom, plane=plane, x=tx, y=ty)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": wiki.USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                missing.parent.mkdir(parents=True, exist_ok=True)
                missing.touch()
                return None
            raise
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if EMBED:
        return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
    return path.as_posix()


class View:
    """A W x H pixel window onto the map, centred on a game coordinate."""

    def __init__(self, cx, cy, zoom, width, height, plane=0, mapid=0):
        self.s = 2 ** zoom
        self.zoom, self.w, self.h, self.plane, self.mapid = zoom, width, height, plane, mapid
        self.x0 = cx * self.s - width / 2
        self.y0 = -cy * self.s - height / 2

    def px(self, x, y):
        """Pixel centre of game square (x, y) in the view."""
        return x * self.s - self.x0 + self.s / 2, -y * self.s - self.y0 - self.s / 2

    def tiles_svg(self):
        """The map tiles covering the view, as SVG <image> elements in view pixels."""
        out = []
        for tx in range(math.floor(self.x0 / 256), math.floor((self.x0 + self.w) / 256) + 1):
            for ty in range(math.floor(-(self.y0 + self.h) / 256), math.floor(-self.y0 / 256) + 1):
                src = tile_src(self.mapid, self.zoom, self.plane, tx, ty)
                if src:
                    out.append('<image href="{}" x="{:.0f}" y="{:.0f}" width="256" height="256"/>'.format(
                        src, tx * 256 - self.x0, -(ty + 1) * 256 - self.y0))
        return "".join(out)


def fit_zoom(points, width, height, margin_squares=10, max_zoom=3):
    """Highest zoom at which every point fits in the window with a margin."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    span_x, span_y = max(xs) - min(xs) + 2 * margin_squares, max(ys) - min(ys) + 2 * margin_squares
    for zoom in range(max_zoom, -2, -1):
        if span_x * 2 ** zoom <= width and span_y * 2 ** zoom <= height:
            return zoom
    return -1


def arrow_svg(view, a, b, color="#ffd23f"):
    (x1, y1), (x2, y2) = view.px(*a[:2]), view.px(*b[:2])
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 14:
        return ""
    # Stop short of the target marker so the head stays visible.
    k = (length - 11) / length
    x2s, y2s = x1 + (x2 - x1) * k, y1 + (y2 - y1) * k
    return ('<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" stroke="#000" stroke-width="6" stroke-linecap="round" opacity=".55"/>'
            '<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" stroke="{}" stroke-width="3" stroke-dasharray="7 5" '
            'stroke-linecap="round" marker-end="url(#head)"/>').format(x1, y1, x2s, y2s, x1, y1, x2s, y2s, color)


def path_svg(view, points, color="#ffd23f"):
    """A walking path through `points` (game squares), with an arrowhead at the end."""
    pts = " ".join("{:.1f},{:.1f}".format(*view.px(*p[:2])) for p in points)
    return ('<polyline points="{p}" fill="none" stroke="#000" stroke-width="6" stroke-linejoin="round" stroke-linecap="round" opacity=".55"/>'
            '<polyline points="{p}" fill="none" stroke="{c}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" '
            'marker-end="url(#head)"/>').format(p=pts, c=color)


def marker_svg(view, p, label, color, number=None, anchor="start"):
    """A marker with its label beside it ("start"/"end") or centred above/below it ("above"/"below")."""
    x, y = view.px(*p[:2])
    width = 12 + 7 * len(label)  # ~7 px per character
    if anchor in ("above", "below"):
        if (anchor == "above" and y < 24) or (anchor == "below" and y > view.h - 24):
            anchor = "below" if anchor == "above" else "above"
        tx, ty, text_anchor = min(max(x, width / 2), view.w - width / 2), (y - 14 if anchor == "above" else y + 22), "middle"
    else:
        # Flip the label to the other side when it would run off the map.
        if anchor == "start" and x + width > view.w:
            anchor = "end"
        elif anchor == "end" and x - width < 0:
            anchor = "start"
        tx, ty, text_anchor = (x + 12 if anchor == "start" else x - 12), y + 4, anchor
    num = '<text x="{:.1f}" y="{:.1f}" text-anchor="middle" fill="#000" style="stroke:none;font-size:11px">{}</text>'.format(x, y + 4, number) if number is not None else ""
    return ('<circle cx="{:.1f}" cy="{:.1f}" r="8" fill="{}" stroke="#000" stroke-width="2"/>{}'
            '<text x="{:.1f}" y="{:.1f}" text-anchor="{}" fill="{}">{}</text>').format(
        x, y, color, num, tx, ty, text_anchor, color, html.escape(label))


def svg(view, body, tiles=""):
    """One self-scaling map image: tiles underneath, markers and paths on top.
    The viewBox keeps everything aligned at any rendered width."""
    return ('<svg viewBox="0 0 {w:.0f} {h:.0f}" role="img">'
            '<defs><marker id="head" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
            '<path d="M0,0 L10,5 L0,10 z" fill="#ffd23f" stroke="#000" stroke-width="1"/></marker></defs>{t}{b}</svg>').format(
        w=view.w, h=view.h, t=tiles, b=body)


def squares(a, b):
    """Run distance in game squares (diagonal steps count as one)."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


UNDERGROUND_Y = 6400


def mapid(leg):
    """The wiki map a leg is drawn on: as given (wiki.py coords prints it), else
    the dungeon map (-1) for underground coordinates, else the surface (0)."""
    if "mapid" in leg:
        return leg["mapid"]
    return -1 if leg["target"][1] >= UNDERGROUND_Y else 0


def plane_of(p):
    return p[2] if len(p) > 2 else 0


def text_leg_html(i, leg, reason):
    lock = '<span class="lock">{}</span>'.format(html.escape(leg["locked"])) if leg.get("locked") else ""
    return ('<div class="leg"><div class="head"><b>{i}. {title}</b>{lock}<br><span class="how">{method}</span> · '
            '<span class="note">{reason}{note}</span></div></div>').format(
        i=i, title=html.escape(leg["title"]), lock=lock, method=html.escape(leg.get("method", "")),
        reason=html.escape(reason), note=" · " + html.escape(leg["note"]) if leg.get("note") else "")


def leg_html(i, leg, width=340, height=230):
    if not leg.get("target"):
        return text_leg_html(i, leg, "no map: destination coordinates unknown")
    target, arrive = leg["target"], leg.get("arrive") or leg["target"]
    plane = plane_of(target)
    floor_change = plane_of(arrive) != plane
    dist = squares(arrive, target)
    path = None
    if dist >= 3 and not floor_change:
        try:
            path = pathfind.find_path(tuple(arrive[:2]) + (plane,), tuple(target[:2]) + (plane,))
        except OSError:
            path = None
    framed = (path or []) + [arrive, target]
    xs, ys = [p[0] for p in framed], [p[1] for p in framed]
    zoom = fit_zoom(framed, width, height)
    view = View((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, zoom, width, height, plane, mapid(leg))
    # Put each label on the far side from the other marker: beside them on
    # north-south legs, above/below on east-west legs, so labels clear the arrow.
    if abs(arrive[0] - target[0]) > abs(arrive[1] - target[1]):
        arrive_side, target_side = ("above", "below") if arrive[1] > target[1] else ("below", "above")
    else:
        arrive_side = "end" if arrive[0] > target[0] else "start"
        target_side = "start" if arrive_side == "end" else "end"
    body = ""
    if path:
        body += path_svg(view, pathfind.simplify(path))
    elif dist >= 3:
        body += arrow_svg(view, arrive, target)
    if dist >= 3:
        body += marker_svg(view, arrive, leg.get("arrive_label", "Arrive"), "#6ec6ff", anchor=arrive_side)
    body += marker_svg(view, target, leg.get("target_label", leg["title"]), "#ffd23f", number=i, anchor=target_side)
    lock = '<span class="lock">{}</span>'.format(html.escape(leg["locked"])) if leg.get("locked") else ""
    if floor_change:
        run = "changes floor (stairs or ladder); arrow shows direction only, drawn on the destination floor"
    elif dist < 3:
        run = "lands on the spot"
    elif path:
        steps = len(path) - 1
        run = "{} steps, ~{:.0f}s running".format(steps, -(-steps // 2) * 0.6)
    else:
        run = "~{} squares, straight line (no walking path found)".format(dist)
    return ('<div class="leg"><div class="head"><b>{i}. {title}</b>{lock}<br><span class="how">{method}</span> · '
            '<span class="note">{run}{note}</span></div>'
            '<div class="map">{svg}</div></div>').format(
        i=i, title=html.escape(leg["title"]), lock=lock, method=html.escape(leg.get("method", "")), run=run,
        note=" · " + html.escape(leg["note"]) if leg.get("note") else "", svg=svg(view, body, view.tiles_svg()))


class ScaledView:
    """Marker coordinates for a View that's drawn shrunk by `scale` (labels stay full size)."""

    def __init__(self, view, scale):
        self.view, self.scale = view, scale
        self.w, self.h = view.w * scale, view.h * scale

    def px(self, x, y):
        px, py = self.view.px(x, y)
        return px * self.scale, py * self.scale


def overview_html(legs, width=700, max_height=420, margin=40):
    """Numbers every surface destination on one map. `legs` is [(number, leg)];
    underground legs are left to their own maps."""
    legs = [(i, leg) for i, leg in legs if leg.get("target") and mapid(leg) == 0]
    if not legs:
        return ""
    points = [leg["target"] for _, leg in legs]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    zoom = fit_zoom(points, width, max_height, margin_squares=margin, max_zoom=1)
    s = 2 ** zoom
    # When even the widest zoom is too big, draw at that zoom and shrink the tiles.
    natural_w = max(width, (max(xs) - min(xs) + 2 * margin) * s)
    natural_h = max(200, (max(ys) - min(ys) + 2 * margin) * s)
    scale = min(1.0, width / natural_w, max_height / natural_h)
    view = View(cx, cy, zoom, natural_w, natural_h)
    marks = ScaledView(view, scale)
    body = "".join(marker_svg(marks, leg["target"], leg.get("short", leg["title"]), "#ffd23f", number=i)
                   for i, leg in legs)
    tiles = '<g transform="scale({:.4f})">{}</g>'.format(scale, view.tiles_svg())
    return '<div class="overview"><div class="map">{}</div></div>'.format(svg(marks, body, tiles))


def route_html(legs, title="Route"):
    """Overview plus one map per leg; `title=None` when a report heading already introduces it."""
    heading = '<h2 class="title">{}</h2>'.format(html.escape(title)) if title else ""
    return '<div class="route">{}{}<div class="legs">{}</div></div>'.format(
        heading, overview_html(list(enumerate(legs, 1))), "".join(leg_html(i, leg) for i, leg in enumerate(legs, 1)))

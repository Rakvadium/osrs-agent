"""Walking paths over the game's collision map.

Usage:
  python pathfind.py 1585 3053 1586 3099          # x1 y1 x2 y2 [--plane 0]

Data: the collision map and door/gate transports of the Shortest Path
RuneLite plugin (https://github.com/Skretzo/shortest-path, BSD-2-Clause),
cached for 30 days. The map stores 64x64-square regions; per square, 4 bits:
can step north, can step east, wall on north edge, wall on east edge. A
diagonal step needs both cardinal steps around it open, as in game. Doors and
gates are separate "Open ..." transports and are added as extra steps when
they have no requirements.

Paths cover walking on one plane only: stairs, ladders, shortcuts and
teleports are left to the plan's own legs.
"""
import argparse
import heapq
import io
import sys
import zipfile

import wiki

SOURCE = "https://raw.githubusercontent.com/Skretzo/shortest-path/master/src/main/resources/"
CACHE = wiki.CACHE_DIR.parent / "shortest-path"
MONTH = 30 * 24 * 3600
FLAG_NORTH, FLAG_EAST = 0, 1
MAX_NODES = 400000

_zip = None
_regions = {}
_doors = None


def _collision_zip():
    global _zip
    if _zip is None:
        path = CACHE / "collision-map.zip"
        import time
        import urllib.request
        if not path.exists() or time.time() - path.stat().st_mtime > MONTH:
            req = urllib.request.Request(SOURCE + "collision-map.zip", headers={"User-Agent": wiki.USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        _zip = zipfile.ZipFile(io.BytesIO(path.read_bytes()))
    return _zip


def _region(rx, ry):
    key = (rx, ry)
    if key not in _regions:
        try:
            _regions[key] = _collision_zip().read("{}_{}".format(rx, ry))
        except KeyError:
            _regions[key] = b""
    return _regions[key]


def flag(x, y, z, f):
    data = _region(x >> 6, y >> 6)
    i = ((z * 64 * 64) + (y & 63) * 64 + (x & 63)) * 4 + f
    return (i >> 3) < len(data) and (data[i >> 3] >> (i & 7)) & 1 == 1


def n(x, y, z): return flag(x, y, z, FLAG_NORTH)
def e(x, y, z): return flag(x, y, z, FLAG_EAST)
def s(x, y, z): return n(x, y - 1, z)
def w(x, y, z): return e(x - 1, y, z)


def walkable(x, y, z):
    return n(x, y, z) or s(x, y, z) or e(x, y, z) or w(x, y, z)


STEPS = [
    (0, 1, lambda x, y, z: n(x, y, z)),
    (1, 0, lambda x, y, z: e(x, y, z)),
    (0, -1, lambda x, y, z: s(x, y, z)),
    (-1, 0, lambda x, y, z: w(x, y, z)),
    (1, 1, lambda x, y, z: n(x, y, z) and e(x, y + 1, z) and e(x, y, z) and n(x + 1, y, z)),
    (-1, 1, lambda x, y, z: n(x, y, z) and w(x, y + 1, z) and w(x, y, z) and n(x - 1, y, z)),
    (1, -1, lambda x, y, z: s(x, y, z) and e(x, y - 1, z) and e(x, y, z) and s(x + 1, y, z)),
    (-1, -1, lambda x, y, z: s(x, y, z) and w(x, y - 1, z) and w(x, y, z) and s(x - 1, y, z)),
]


def doors():
    """Same-plane, requirement-free 'Open/Pass' transports (doors, gates): {(x, y, z): [(x, y, z), ...]}."""
    global _doors
    if _doors is None:
        _doors = {}
        text = wiki.fetch_text(SOURCE + "transports/transports.tsv", CACHE / "transports.tsv", ttl=MONTH)
        for line in text.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            cols = line.split("\t") + [""] * 10
            origin, dest, action = cols[0].split(), cols[1].split(), cols[2]
            if len(origin) != 3 or len(dest) != 3 or any(c.strip() for c in cols[3:8]):
                continue
            a, b = tuple(map(int, origin)), tuple(map(int, dest))
            if a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 3 and action.split(" ")[0] in ("Open", "Pass", "Go-through", "Walk-through", "Climb-over", "Squeeze-through"):
                _doors.setdefault(a, []).append(b)
    return _doors


def nearest_walkable(x, y, z, radius=3):
    """The walkable square closest to (x, y), for targets that are objects (patches, trees, ...)."""
    if walkable(x, y, z):
        return (x, y, z)
    best = None
    for r in range(1, radius + 1):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) == r and walkable(x + dx, y + dy, z):
                    d = dx * dx + dy * dy
                    if best is None or d < best[0]:
                        best = (d, (x + dx, y + dy, z))
        if best:
            return best[1]
    return None


def find_path(start, goal):
    """Squares from start to goal (both (x, y, plane)), or None if unreachable on foot.

    The goal snaps to the nearest walkable square, since destinations are often
    objects that can't be stood on. Each step (straight or diagonal) costs 1, as in game.
    """
    z = start[2]
    if goal[2] != z:
        return None
    start = nearest_walkable(*start)
    end = nearest_walkable(*goal)
    if not start or not end:
        return None
    door_edges = doors()

    def h(p):
        return max(abs(p[0] - end[0]), abs(p[1] - end[1]))

    came = {start: None}
    cost = {start: 0}
    heap = [(h(start), 0, start)]
    expanded = 0
    while heap:
        _, g, cur = heapq.heappop(heap)
        if cur == end:
            path = []
            while cur:
                path.append(cur)
                cur = came[cur]
            return path[::-1]
        if g > cost[cur]:
            continue
        expanded += 1
        if expanded > MAX_NODES:
            return None
        x, y, _ = cur
        nexts = [(x + dx, y + dy, z) for dx, dy, ok in STEPS if ok(x, y, z)]
        nexts += door_edges.get(cur, [])
        for nxt in nexts:
            ng = g + 1
            if ng < cost.get(nxt, 1 << 30):
                cost[nxt] = ng
                came[nxt] = cur
                heapq.heappush(heap, (ng + h(nxt), ng, nxt))
    return None


def simplify(path):
    """Keeps only the squares where the walking direction changes."""
    if not path or len(path) < 3:
        return path
    out = [path[0]]
    for prev, cur, nxt in zip(path, path[1:], path[2:]):
        if (cur[0] - prev[0], cur[1] - prev[1]) != (nxt[0] - cur[0], nxt[1] - cur[1]):
            out.append(cur)
    out.append(path[-1])
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("coords", nargs=4, type=int, metavar="N", help="x1 y1 x2 y2")
    parser.add_argument("--plane", type=int, default=0)
    args = parser.parse_args(argv)
    x1, y1, x2, y2 = args.coords
    path = find_path((x1, y1, args.plane), (x2, y2, args.plane))
    if not path:
        print("No walking path found (blocked, different area, or needs stairs/transport).")
        return 1
    steps = len(path) - 1
    print("{} steps (~{:.0f}s running, 2 squares per 0.6s tick)".format(steps, -(-steps // 2) * 0.6))
    print("turns: " + " -> ".join("{} {}".format(p[0], p[1]) for p in simplify(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

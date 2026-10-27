"""Teleport and transport destinations with coordinates and requirements.

Usage:
  python transport.py find "Ardougne cloak"     # teleport items, spells, fairy rings, quetzals, ...
  python transport.py find "AJP"                # fairy ring codes match with or without spaces

Data: the transport tables of the Shortest Path RuneLite plugin
(https://github.com/Skretzo/shortest-path, BSD-2-Clause), cached for 7 days.
Coordinates are game tiles "x y plane". Item requirements are game item IDs;
varbit requirements are internal unlock flags (quest/diary progress).
"""
import argparse
import re
import sys

import wiki

SOURCE = "https://raw.githubusercontent.com/Skretzo/shortest-path/master/src/main/resources/transports/"
FILES = [
    "teleportation_items", "teleportation_spells", "teleportation_minigames", "teleportation_portals_poh",
    "fairy_rings", "quetzal_whistle", "quetzals", "spirit_trees", "gnome_gliders", "charter_ships",
    "boats", "ships", "canoes", "minecarts", "hot_air_balloons", "magic_carpets", "magic_mushtrees",
    "teleportation_levers", "teleportation_portals", "wilderness_obelisks",
]


def load(name):
    """Rows of one transport table as dicts keyed by its header columns."""
    path = wiki.CACHE_DIR / "transports" / (name + ".tsv")
    text = wiki.fetch_text(SOURCE + name + ".tsv", path)
    header, rows = None, []
    for line in text.splitlines():
        if line.startswith("#"):
            cols = [c.strip() for c in line.lstrip("# ").split("\t")]
            if header is None and any(c in ("Destination", "Origin") for c in cols):
                header = cols
            continue
        if header and line.strip():
            rows.append(dict(zip(header, (c.strip() for c in line.split("\t")))))
    return rows


def point(text):
    parts = (text or "").split()
    return tuple(int(p) for p in parts) if len(parts) == 3 and all(p.lstrip("-").isdigit() for p in parts) else None


def find(query):
    """Transports whose display text or table name matches `query`."""
    q = re.sub(r"\s+", "", query.lower())
    results = []
    for name in FILES:
        for row in load(name):
            label = row.get("Display info") or row.get("menuOption menuTarget objectID") or ""
            haystack = re.sub(r"\s+", "", (label + name).lower())
            if q in haystack:
                results.append({
                    "table": name,
                    "label": label,
                    "destination": point(row.get("Destination")),
                    "origin": point(row.get("Origin")),
                    "skills": row.get("Skills", ""),
                    "items": row.get("Items", ""),
                    "quests": row.get("Quests", ""),
                    "varbits": row.get("Varbits", ""),
                })
    return results


def cmd_find(args):
    results = find(args.query)
    if not results:
        print("No transport matches {!r}".format(args.query))
        return
    for r in results[: args.limit]:
        reqs = "; ".join("{}: {}".format(k, r[k]) for k in ("skills", "quests", "items", "varbits") if r[k])
        dest = " ".join(map(str, r["destination"])) if r["destination"] else "?"
        origin = " from " + " ".join(map(str, r["origin"])) if r["origin"] else ""
        print("- [{}] {} -> {}{}{}".format(r["table"], r["label"] or "(unlabelled)", dest, origin, " | " + reqs if reqs else ""))
    if len(results) > args.limit:
        print("  ... {} more (use --limit)".format(len(results) - args.limit))


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("find", help="search transports by name, item or fairy ring code")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=15)
    p.set_defaults(func=cmd_find)
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

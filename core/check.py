"""Checks wiki requirements against a character snapshot from the RuneLite plugin.

Usage:
  python check.py status [--rsn NAME]
  python check.py quest "Fairytale II" [--rsn NAME]
  python check.py has "Dramen staff" "Knife" [--rsn NAME]
  python check.py plan plan.json [--rsn NAME]      (see PLAN_FORMAT below; "-" reads stdin)

Snapshots are read from %USERPROFILE%/.runelite/plugin-data/osrs-agent/snapshots
(override with OSRS_AGENT_SNAPSHOTS). --rsn may be omitted when only one
character has a snapshot.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import wiki

SNAPSHOT_DIR = Path(os.environ.get("OSRS_AGENT_SNAPSHOTS")
                    or Path.home() / ".runelite" / "plugin-data" / "osrs-agent" / "snapshots")
# Where an item can be used without a bank trip, then storage.
LOCATIONS = ["equipment", "inventory", "runePouch", "lootingBag", "bank", "seedVault", "tackleBox", "groupStorage"]


class CheckError(Exception):
    pass


def norm(name):
    """Matches names across the wiki and RuneLite ('A/B' vs 'A - B', '&' vs 'and')."""
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("&", "and"))


def load_snapshot(rsn):
    if not SNAPSHOT_DIR.exists():
        raise CheckError("No snapshots at {}. Run RuneLite with the osrs-agent plugin and log in.".format(SNAPSHOT_DIR))
    files = sorted(SNAPSHOT_DIR.glob("*.json"))
    if rsn:
        files = [f for f in files if f.stem == re.sub(r"[^a-z0-9]+", "_", rsn.lower())]
        if not files:
            raise CheckError("No snapshot for {!r} in {}".format(rsn, SNAPSHOT_DIR))
    elif len(files) != 1:
        names = ", ".join(f.stem for f in files) or "none"
        raise CheckError("Pass --rsn; snapshots available: {}".format(names))
    return json.loads(files[0].read_text(encoding="utf-8"))


def list_snapshots():
    files = sorted(SNAPSHOT_DIR.glob("*.json")) if SNAPSHOT_DIR.exists() else []
    if not files:
        raise CheckError("No snapshots at {}. Run RuneLite with the osrs-agent plugin and log in.".format(SNAPSHOT_DIR))
    for f in files:
        snap = json.loads(f.read_text(encoding="utf-8"))
        print("- {} ({}), captured {}".format(snap.get("rsn"), snap.get("accountType"), age(snap.get("capturedAt"))))


def age(iso):
    if not iso:
        return "never"
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    minutes = int((datetime.now(timezone.utc) - then).total_seconds() // 60)
    if minutes < 60:
        return "{}m ago".format(minutes)
    if minutes < 48 * 60:
        return "{}h ago".format(minutes // 60)
    return "{}d ago".format(minutes // 1440)


def print_header(snap):
    print("Snapshot: {} ({}), captured {}".format(snap["rsn"], snap.get("accountType"), age(snap.get("capturedAt"))))


# --- quest -------------------------------------------------------------------

def quest_state(snap, name):
    by_norm = {norm(k): v for k, v in snap.get("quests", {}).items()}
    return by_norm.get(norm(name))


# "[?]" = not in the snapshot's quest list (a misc requirement like Kudos, or a name mismatch).
MARK = {"FINISHED": "[done]", "IN_PROGRESS": "[started]", "NOT_STARTED": "[todo]", None: "[?]"}


def skill_gaps(snap, skills):
    out = []
    for s in skills:
        have = snap.get("skills", {}).get(s["skill"].lower(), {}).get("level")
        if have is None:
            out.append("[?] {} {} (skill not in snapshot)".format(s["level"], s["skill"]))
        elif have < s["level"]:
            tags = ["boostable" if s["boostable"] else "not boostable"]
            if not s["required_to_start"]:
                tags.append("not needed to start")
            out.append("[todo] {} {}: have {}, need +{} ({})".format(s["level"], s["skill"], have, s["level"] - have, ", ".join(tags)))
    return out


def cmd_quest(args, snap):
    q = wiki.quest_data(args.name)
    req = q["requirements"]
    state = quest_state(snap, q["title"])
    print("\n# {} {}".format(MARK[state], q["title"]))
    if state == "FINISHED":
        print("Already complete.")
        return

    blockers = 0
    print("\nQuest prerequisites (completed branches collapsed; [?] = not a quest the snapshot tracks, check manually):")
    if not req["quests"]:
        print("- none")
    skip_below = None
    unfinished = []
    for node in req["quests"]:
        if skip_below is not None and node["depth"] > skip_below:
            continue
        skip_below = None
        s = quest_state(snap, node["name"])
        print("  " * node["depth"] + "{} {}{}".format(MARK[s], node["name"], " ({})".format(node["note"]) if node["note"] else ""))
        if s == "FINISHED":
            skip_below = node["depth"]
        else:
            blockers += 1
            unfinished.append(node["name"])

    print("\nSkills for this quest:")
    gaps = skill_gaps(snap, req["skills"])
    print("\n".join("- " + g for g in gaps) if gaps else "- all met")
    blockers += len(gaps)

    # The wiki's tree lists only quests; their own skill requirements come from each page.
    deep = []
    highest = {s["skill"]: s["level"] for s in req["skills"]}
    for name in unfinished:
        try:
            sub = wiki.quest_data(name)
        except wiki.WikiError:
            continue
        for s in sub["requirements"]["skills"]:
            highest[s["skill"]] = max(highest.get(s["skill"], 0), s["level"])
        for g in skill_gaps(snap, sub["requirements"]["skills"]):
            deep.append("{} (for {})".format(g, sub["title"]))
    if deep:
        print("\nSkills for unfinished prerequisites:")
        print("\n".join("- " + d for d in deep))
        blockers += len(deep)

    targets = []
    for skill, level in sorted(highest.items(), key=lambda kv: -kv[1]):
        have = snap.get("skills", {}).get(skill.lower(), {}).get("level", 0)
        if have < level:
            targets.append("{} {} (have {})".format(level, skill, have))
    if targets:
        print("\nLevels to reach for the whole chain: " + ", ".join(targets))

    if req["quest_points"]:
        have = snap.get("questPoints", 0)
        ok = have >= req["quest_points"]
        print("\nQuest points: {} {} (have {})".format("[done]" if ok else "[todo]", req["quest_points"], have))
        blockers += 0 if ok else 1

    for title, lines in (("Other requirements (check manually)", req["other"]),
                         ("Items required", q["items_required"]),
                         ("Ironman notes", q["ironman_concerns"])):
        if lines:
            print("\n{}:".format(title))
            print("\n".join("- " + l for l in lines))

    print("\nBlockers found: {}".format(blockers))


# --- has ---------------------------------------------------------------------

def bank_unknown(snap):
    return "bank" not in snap.get("containers", {}) and "bank" not in snap.get("excluded", [])


def container_items(snap):
    containers = dict(snap.get("containers", {}))
    if snap.get("runePouch"):
        containers["runePouch"] = {"capturedAt": snap.get("capturedAt"), "items": snap["runePouch"]}
    return containers


def cmd_has(args, snap):
    containers = container_items(snap)
    print("\nStorage captured: " + ", ".join(
        "{} {}".format(k, age(containers[k].get("capturedAt")) if k in containers else "never") for k in ("inventory", "equipment", "bank")))

    for wanted in args.items:
        exact, similar = [], {}
        for loc in LOCATIONS:
            for item in containers.get(loc, {}).get("items", []):
                if norm(item["name"]) == norm(wanted):
                    exact.append("{} x{}{}{}".format(loc, item["quantity"], " (noted)" if item.get("noted") else "",
                                                       " slot " + item["slot"] if loc == "equipment" and item.get("slot") else ""))
                elif norm(wanted) in norm(item["name"]):
                    similar.setdefault(item["name"], []).append(loc)
        if exact:
            print("- [have] {}: {}".format(wanted, "; ".join(exact)))
        else:
            print("- [missing] {}{}".format(wanted, " (bank never captured; open it in-game)" if bank_unknown(snap) else ""))
        for name, locs in list(similar.items())[:5]:
            print("    similar: {} in {}".format(name, ", ".join(sorted(set(locs)))))


def find_item(containers, name):
    """Quantity of an item per location, exact name match (ignoring punctuation/case)."""
    found = {}
    for loc in LOCATIONS:
        for item in containers.get(loc, {}).get("items", []):
            if norm(item["name"]) == norm(name):
                found[loc] = found.get(loc, 0) + item["quantity"]
    return found


# --- status ------------------------------------------------------------------

def cmd_status(args, snap):
    containers = container_items(snap)
    skills = snap.get("skills", {})
    def val(key):
        return "unknown" if snap.get(key) is None else snap[key]
    world_types = snap.get("worldTypes")
    members = "unknown" if world_types is None else ("yes" if "MEMBERS" in world_types else "NO (free-to-play world)")
    print("Combat {}, total level {}, quest points {}, world {} (members: {})".format(
        val("combatLevel"), val("totalLevel"), val("questPoints"), val("world"), members))
    print("Skills: " + ", ".join("{} {}".format(k, v["level"]) for k, v in skills.items()))
    done = [region + ":" + tier for region, tiers in snap.get("diaries", {}).items() for tier, t in tiers.items() if t.get("complete")]
    print("Diaries complete: " + (", ".join(done) or "none"))
    for key in ("equipment", "inventory"):
        c = containers.get(key)
        if not c:
            print("{}: never captured".format(key.capitalize()))
            continue
        extra = " ({} free of {})".format(c["freeSlots"], c["capacity"]) if c.get("capacity") else ""
        items = ", ".join("{}{}{}".format(i["name"], " x{}".format(i["quantity"]) if i["quantity"] > 1 else "",
                                          " [{}]".format(i["slot"]) if key == "equipment" else "") for i in c["items"])
        print("{}{}: {}".format(key.capitalize(), extra, items or "empty"))
    if snap.get("runePouch"):
        print("Rune pouch: " + ", ".join("{} x{}".format(i["name"], i["quantity"]) for i in snap["runePouch"]))
    stored = ["{} ({} items, {})".format(k, len(containers[k]["items"]), age(containers[k].get("capturedAt")))
              for k in ("bank", "seedVault", "lootingBag", "tackleBox", "groupStorage") if k in containers]
    print("Storage: " + (", ".join(stored) or "none captured"))
    if bank_unknown(snap):
        print("WARNING: bank never captured. Item checks cannot see banked items; ask the user to open their bank in-game.")


# --- plan --------------------------------------------------------------------

PLAN_FORMAT = """\
{
  "requirements": [                       # each group needs ANY ONE option to pass
    {"why": "Fairy ring access", "any_of": [
      {"equipment": ["Dramen staff"]},     # must be owned (any location); worn during the trip
      {"equipment": ["Lunar staff"]},
      {"diaries": ["lumbridge:elite"]}
    ]},
    {"why": "Plant ranarr", "any_of": [{"skills": {"Farming": 32}}]}
  ],
  "inventory": [                          # the loadout to carry; slots counted against 28
    {"item": "Seed dibber"},
    {"item": "Ranarr seed", "qty": 4, "stackable": true},
    {"item": "Ultracompost", "qty": 4}
  ],
  "equipment": ["Dramen staff", "Explorer's ring 2"]
}
Option keys: items ([name] or [{"item", "qty"}], owned anywhere), equipment ([name]),
skills ({skill: level}), quests ([name], finished), quests_started ([name], started or finished),
diaries (["region:tier"]), quest_points (int)."""


def check_option(snap, containers, option):
    """Returns a list of unmet reasons for one any_of option (empty = met)."""
    unmet = []
    for entry in option.get("items", []) + [{"item": e} for e in option.get("equipment", [])]:
        name, qty = (entry, 1) if isinstance(entry, str) else (entry["item"], entry.get("qty", 1))
        have = sum(find_item(containers, name).values())
        if have < qty:
            unmet.append("need {} x{}, have {}{}".format(name, qty, have, " (bank never captured)" if bank_unknown(snap) else ""))
    for skill, level in option.get("skills", {}).items():
        have = snap.get("skills", {}).get(skill.lower(), {}).get("level", 0)
        if have < level:
            unmet.append("need {} {}, have {}".format(level, skill, have))
    for name in option.get("quests", []):
        state = quest_state(snap, name)
        if state != "FINISHED":
            unmet.append("quest {} is {}".format(name, state or "unknown to the snapshot"))
    for name in option.get("quests_started", []):
        state = quest_state(snap, name)
        if state not in ("IN_PROGRESS", "FINISHED"):
            unmet.append("quest {} not started{}".format(name, "" if state else " (unknown to the snapshot)"))
    for key in option.get("diaries", []):
        region, _, tier = key.lower().partition(":")
        if not snap.get("diaries", {}).get(region, {}).get(tier, {}).get("complete"):
            unmet.append("diary {} not complete".format(key))
    if option.get("quest_points") and snap.get("questPoints", 0) < option["quest_points"]:
        unmet.append("need {} quest points, have {}".format(option["quest_points"], snap.get("questPoints", 0)))
    return unmet


def describe_option(option):
    parts = []
    for key, value in option.items():
        parts.append("{}: {}".format(key, ", ".join("{} {}".format(k, v) for k, v in value.items()) if isinstance(value, dict)
                                     else ", ".join(v if isinstance(v, str) else "{} x{}".format(v["item"], v.get("qty", 1)) for v in value)
                                     if isinstance(value, list) else value))
    return "; ".join(parts)


def cmd_plan(args, snap):
    raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as e:
        raise CheckError("plan is not valid JSON ({}). Format:\n{}".format(e, PLAN_FORMAT))
    containers = container_items(snap)
    blockers = 0

    print("\n## Requirements")
    for group in plan.get("requirements", []):
        results = [(opt, check_option(snap, containers, opt)) for opt in group.get("any_of", [])]
        met = next((opt for opt, unmet in results if not unmet), None)
        if met is not None:
            print("- [met] {} (via {})".format(group.get("why", "?"), describe_option(met)))
            continue
        blockers += 1
        print("- [BLOCKED] {}".format(group.get("why", "?")))
        for opt, unmet in results:
            print("    option {}: {}".format(describe_option(opt), "; ".join(unmet)))

    print("\n## Equipment")
    worn = {i["slot"]: i["name"] for i in containers.get("equipment", {}).get("items", [])}
    used_slots = {}
    for name in plan.get("equipment", []):
        where = find_item(containers, name)
        try:
            slot = wiki_equip_slot(name)
        except wiki.WikiError:
            slot = None
        if slot is None:
            print("- [CHECK] {}: wiki has no equipment slot for it; confirm it can be worn".format(name))
        elif slot in used_slots:
            blockers += 1
            print("- [CLASH] {} and {} both use the {} slot".format(name, used_slots[slot], slot))
            continue
        used_slots[slot] = name
        if "equipment" in where:
            print("- [worn] {}".format(name))
        elif where:
            print("- [equip] {}: from {}{}".format(name, ", ".join(where), _replaces(worn, slot)))
        else:
            blockers += 1
            print("- [MISSING] {}: not owned{}".format(name, " (bank never captured)" if bank_unknown(snap) else ""))

    print("\n## Inventory")
    total = 0
    for entry in plan.get("inventory", []):
        name, qty = entry["item"], entry.get("qty", 1)
        slots = 1 if entry.get("stackable") or entry.get("noted") or qty == 1 else qty
        total += slots
        where = find_item(containers, name)
        have = sum(n for loc, n in where.items() if loc != "equipment")
        in_inv = where.get("inventory", 0)
        if in_inv >= qty:
            status = "[carried]"
        elif have >= qty:
            status = "[withdraw] from " + ", ".join(l for l in where if l not in ("inventory", "equipment"))
        else:
            blockers += 1
            status = "[MISSING] have {} of {}".format(have, qty)
        print("- {} {} x{} ({} slot{})".format(status, name, qty, slots, "" if slots == 1 else "s"))
    print("Inventory slots used: {}/28{}".format(total, "  [OVER CAPACITY]" if total > 28 else ""))
    blockers += 1 if total > 28 else 0

    print("\n## Verdict: {}".format("READY" if blockers == 0 else "BLOCKED ({} blocker{})".format(blockers, "" if blockers == 1 else "s")))


def wiki_equip_slot(name):
    title = wiki.resolve_title(name)
    rows = wiki.bucket("infobox_bonuses", ["equipment_slot"], "page_name", title)
    slot = next((r["equipment_slot"] for r in rows if r.get("equipment_slot")), None)
    # Two-handed weapons occupy the shield slot too; treat them as the weapon slot.
    return {"2h": "weapon"}.get(slot, slot)


def _replaces(worn, slot):
    current = worn.get((slot or "").upper())
    return ", replacing worn {}".format(current) if current else ""


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="account overview: levels, diaries, worn/carried items, storage freshness")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("plan", help="validate a plan's requirements and loadout in one pass",
                       description=PLAN_FORMAT, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", help="plan JSON file, or - for stdin")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("quest", help="quest prerequisites, skills and quest points vs the snapshot")
    p.add_argument("name")
    p.set_defaults(func=cmd_quest)

    p = sub.add_parser("has", help="where each item is: equipped, inventory, bank, ... or missing")
    p.add_argument("items", nargs="+")
    p.set_defaults(func=cmd_has)

    for p in sub.choices.values():
        p.add_argument("--rsn", help="character name (optional with a single snapshot)")
        p.add_argument("--exclude", action="append", default=[], metavar="CONTAINER",
                       help="ignore a container, e.g. --exclude bank for ultimate ironmen")

    p = sub.add_parser("snapshots", help="list characters that have snapshots")
    p.set_defaults(func=None)

    args = parser.parse_args(argv)
    try:
        if args.func is None:
            list_snapshots()
            return 0
        snap = load_snapshot(args.rsn)
        for key in args.exclude:
            snap.get("containers", {}).pop(key, None)
        snap["excluded"] = args.exclude
        print_header(snap)
        if args.exclude:
            print("Excluded containers: " + ", ".join(args.exclude))
        args.func(args, snap)
    except (CheckError, wiki.WikiError) as e:
        print("error: {}".format(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Compact, cached lookups against the OSRS Wiki for planning agents.

Usage: python wiki.py <command> <name> [options]   (see --help)

Output is plain text trimmed for an agent's context window. Responses are
cached on disk (default 7 days, prices 5 minutes); pass --refresh to bypass.
"""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

API = "https://oldschool.runescape.wiki/api.php"
PRICES = "https://prices.runescape.wiki/api/v1/osrs"
# The wiki asks API clients to identify themselves.
USER_AGENT = "osrs-agent planning tool (personal use; RuneLite snapshot + wiki lookups)"
CACHE_DIR = Path.home() / ".cache" / "osrs-agent" / "wiki"
WEEK = 7 * 24 * 3600

refresh = False


class WikiError(Exception):
    pass


def fetch_json(url, params, ttl=WEEK):
    full = url + "?" + urllib.parse.urlencode(params)
    path = CACHE_DIR / (hashlib.sha1(full.encode()).hexdigest() + ".json")
    if not refresh and path.exists() and time.time() - path.stat().st_mtime < ttl:
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def fetch_text(url, path, ttl=WEEK):
    """Downloads `url` to the cache file `path` (refreshed after `ttl` seconds); returns its text."""
    if not refresh and path.exists() and time.time() - path.stat().st_mtime < ttl:
        return path.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def api(**params):
    return fetch_json(API, {"format": "json", **params})


def lua_str(s):
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def bucket(name, fields, where_field, value, limit=50):
    query = "bucket({}).select({}).where({}, {}).limit({}).run()".format(
        lua_str(name), ",".join(lua_str(f) for f in fields), lua_str(where_field), lua_str(value), limit)
    data = api(action="bucket", query=query)
    if "error" in data:
        raise WikiError(data["error"])
    return data.get("bucket", [])


def resolve_title(name):
    """Exact page (following redirects) if it exists, else the top search hit."""
    data = api(action="query", titles=name, redirects=1)
    for page in data.get("query", {}).get("pages", {}).values():
        if "missing" not in page and "invalid" not in page:
            return page["title"]
    hits = search(name, 1)
    if not hits:
        raise WikiError("No wiki page found for {!r}".format(name))
    return hits[0]


def search(text, limit=5):
    data = api(action="query", list="search", srsearch=text, srlimit=limit)
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]


# --- wikitext / HTML cleanup -------------------------------------------------

def clean_wikitext(text):
    text = re.sub(r"<sup[^>]*>.*?</sup>", "", text, flags=re.S)
    text = re.sub(r"\[\[File:[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("'''", "").replace("''", "")
    return re.sub(r"[ \t]+", " ", text).strip()


class _TextExtractor(HTMLParser):
    SKIP = {"style", "script", "sup"}
    BLOCK = {"p", "div", "br", "h2", "h3", "h4", "h5", "tr", "ul", "ol", "dl", "table"}
    VOID = {"br", "img", "hr", "wbr", "meta", "link", "input", "source", "col", "area"}

    def __init__(self):
        super().__init__()
        self.out = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        if self.skip_depth or tag in self.SKIP or "mw-editsection" in cls or "navbox" in cls:
            if tag not in self.VOID:
                self.skip_depth += 1
            return
        if tag == "li":
            self.out.append("\n- ")
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if self.skip_depth and tag not in self.VOID:
            self.skip_depth -= 1

    def handle_data(self, data):
        # Source newlines are insignificant in HTML; structure comes from tags.
        if not self.skip_depth:
            self.out.append(data.replace("\n", " "))

    def text(self):
        text = "".join(self.out)
        # Chart configs are embedded as raw JSON text; drop them.
        text = re.sub(r'\{"type":"[a-z]+","options":.*', "", text)
        text = re.sub(r"[ \t\xa0]+", " ", text)
        text = re.sub(r"[ |]*\n[ |]*", "\n", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()


def html_to_text(html):
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()


# --- quests ------------------------------------------------------------------

SKILL_RE = re.compile(r'data-skill="([^"]+)" data-level="(\d+)"')
QP_RE = re.compile(r"(\d+)\s*\[?\[?(?:Quest points\|)?\s*quest points", re.I)
LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def parse_quest_requirements(text):
    """Turns the wiki's requirements bullet list into structured data.

    Returns {"quests": [{"name", "depth", "note"}], "skills": [{"skill",
    "level", "boostable", "required_to_start"}], "quest_points", "other"}.
    Quest depth 1 is a direct prerequisite; deeper entries are prerequisites
    of the entry above them, as nested on the wiki.
    """
    result = {"quests": [], "skills": [], "quest_points": None, "other": []}
    quest_header_depth = None
    for raw in text.splitlines():
        m = re.match(r"^(\*+)\s*(.*)$", raw.strip())
        depth, body = (len(m.group(1)), m.group(2)) if m else (0, raw.strip())
        if not body:
            continue

        if quest_header_depth is not None and depth <= quest_header_depth:
            quest_header_depth = None
        if "following quests" in body.lower():
            quest_header_depth = depth
            continue
        if quest_header_depth is not None:
            link = LINK_RE.search(body)
            if link:
                note = clean_wikitext(body.replace(link.group(0), "")).strip(" -:()")
                result["quests"].append({"name": link.group(1).strip(), "depth": depth - quest_header_depth, "note": note})
                continue

        # A single prerequisite is written inline: "Completion of [[Cook's Assistant]]".
        single = re.match(r"^(?:Completion of|Completed)\s+" + LINK_RE.pattern, body, re.I)
        if single:
            result["quests"].append({"name": single.group(1).strip(), "depth": 1, "note": ""})
            continue

        skill = SKILL_RE.search(body)
        if skill and skill.group(1).lower() == "quest points":
            result["quest_points"] = int(skill.group(2))
            continue
        if skill:
            result["skills"].append({
                "skill": skill.group(1),
                "level": int(skill.group(2)),
                "boostable": "requirement is boostable" in body,
                "required_to_start": "can be started without this requirement" not in body,
            })
            continue

        qp = QP_RE.search(body)
        if qp and result["quest_points"] is None:
            result["quest_points"] = int(qp.group(1))
            continue

        cleaned = clean_wikitext(body)
        if cleaned:
            result["other"].append(cleaned)
    return result


def quest_data(name):
    title = resolve_title(name)
    rows = bucket("quest", ["page_name", "requirements", "items_required", "ironman_concerns", "start_point"], "page_name", title, 1)
    if not rows:
        raise WikiError("{!r} has no quest data on the wiki (is it a quest?)".format(title))
    row = rows[0]
    return {
        "title": title,
        "requirements": parse_quest_requirements(row.get("requirements", "")),
        "items_required": clean_list(row.get("items_required", "")),
        "ironman_concerns": clean_list(row.get("ironman_concerns", "")),
        "start_point": clean_wikitext(row.get("start_point", "")),
    }


def clean_list(text):
    return [line for line in (clean_wikitext(l.lstrip("*").strip()) for l in text.splitlines()) if line]


# --- commands ----------------------------------------------------------------

def ge_mapping():
    """Item ID -> GE metadata. Only items tradeable on the GE are present."""
    return {str(m["id"]): m for m in fetch_json(PRICES + "/mapping", {})}


def cmd_item(args):
    title = resolve_title(args.name)
    # infobox_item's members/tradeable fields are unpopulated; the GE mapping covers them.
    rows = bucket("infobox_item", ["item_name", "item_id", "weight", "quest", "examine"], "page_name", title)
    if not rows:
        raise WikiError("{!r} has no item infobox".format(title))
    mapping = ge_mapping()
    slots = {b.get("equipment_slot") for b in bucket("infobox_bonuses", ["equipment_slot"], "page_name", title) if b.get("equipment_slot")}
    print("# " + title)
    print("Equip slot: " + (", ".join(sorted(slots)) + " (wear it to free an inventory slot)" if slots else "not equippable"))
    for row in rows:
        ids = row.get("item_id") or []
        ge = next((mapping[i] for i in ids if i in mapping), None)
        trade = "GE-tradeable, members={}, buy limit {}".format(ge.get("members"), ge.get("limit", "?")) if ge else "not on the GE"
        print("- {} (id {}): {}; weight {}kg".format(row.get("item_name"), ", ".join(ids) or "?", trade, row.get("weight", "?")))
        if row.get("quest") and row["quest"] != "No":
            print("  quest item: " + clean_wikitext(row["quest"]))
        if row.get("examine"):
            print("  examine: " + clean_wikitext(row["examine"]))


def cmd_quest(args):
    q = quest_data(args.name)
    req = q["requirements"]
    print("# " + q["title"])
    if q["start_point"]:
        print("Start: " + q["start_point"])
    print("\nQuest prerequisites:" + ("" if req["quests"] else " none"))
    for node in req["quests"]:
        print("  " * node["depth"] + "- " + node["name"] + (" ({})".format(node["note"]) if node["note"] else ""))
    print("\nSkills:" + ("" if req["skills"] else " none"))
    for s in req["skills"]:
        flags = ["boostable" if s["boostable"] else "not boostable"]
        if not s["required_to_start"]:
            flags.append("not required to start")
        print("- {} {} ({})".format(s["level"], s["skill"], ", ".join(flags)))
    if req["quest_points"]:
        print("\nQuest points: {}".format(req["quest_points"]))
    for title, lines in (("Other requirements", req["other"]), ("Items required", q["items_required"]), ("Ironman notes", q["ironman_concerns"])):
        if lines:
            print("\n{}:".format(title))
            for line in lines:
                print("- " + line)


def recipes_for(title):
    rows = bucket("recipe", ["production_json", "uses_facility"], "page_name", title)
    out = []
    for row in rows:
        prod = json.loads(row.get("production_json") or "{}")
        mats = ", ".join("{} x{}".format(m["name"], m.get("quantity", 1)) for m in prod.get("materials", []))
        skills = ", ".join("{} {}{}".format(s["level"], s["name"], "" if s.get("boostable") == "Yes" else " (not boostable)") for s in prod.get("skills", []))
        facility = ", ".join(f for f in row.get("uses_facility") or [] if f)
        parts = ["makes {} x{}".format(prod.get("output", {}).get("name", title), prod.get("output", {}).get("quantity", 1))]
        if mats:
            parts.append("from " + mats)
        if prod.get("tools"):
            parts.append("tools: " + prod["tools"])
        if facility:
            parts.append("at " + facility)
        if skills:
            parts.append("needs " + skills)
        if prod.get("members"):
            parts.append("members")
        out.append("; ".join(parts))
    return out


def cmd_recipe(args):
    title = resolve_title(args.name)
    lines = recipes_for(title)
    print("# " + title)
    print("\n".join("- " + l for l in lines) if lines else "No recipe on the wiki. Try: wiki.py page {!r}".format(title))


def cmd_sources(args):
    title = resolve_title(args.name)
    print("# Sources of " + title)

    shops = bucket("storeline", ["sold_by", "store_buy_price", "store_currency", "store_stock", "store_notes"], "sold_item", title)
    print("\nShops:" + ("" if shops else " none"))
    for s in shops[: args.limit]:
        note = clean_wikitext(s.get("store_notes") or "")
        price = s.get("store_buy_price")
        price = "{} {}".format(price, s.get("store_currency")) if price and price != "N/A" else "price not listed (see the shop page)"
        print("- {}: {} (stock {}){}".format(s["sold_by"], price, s.get("store_stock"), " - " + note if note else ""))

    drops = bucket("dropsline", ["page_name", "drop_json"], "item_name", title, 500)
    parsed = [json.loads(d["drop_json"]) for d in drops if d.get("drop_json")]
    print("\nDrops:" + ("" if parsed else " none"))
    for d in sorted(parsed, key=lambda d: rarity_value(d.get("Rarity")), reverse=True)[: args.limit]:
        level = d.get("Drop level")
        how = d.get("Drop type") or "combat"
        print("- {} ({}{}): {} x{}".format(d.get("Dropped from"), how, " lvl " + level if level and level != "N/A" else "", d.get("Rarity"), d.get("Drop Quantity")))
    if len(parsed) > args.limit:
        print("  ... {} more (use --limit)".format(len(parsed) - args.limit))

    recipes = recipes_for(title)
    print("\nRecipes:" + ("" if recipes else " none"))
    for r in recipes:
        print("- " + r)

    if not (shops or parsed or recipes):
        print("\nNo structured sources. The page intro usually explains how to get it:")
        print(page_text(title, None, args.max_chars))


def rarity_value(rarity):
    if not rarity:
        return 0
    if rarity.lower() == "always":
        return 1
    m = re.match(r"([\d.,]+)\s*/\s*([\d.,]+)", rarity)
    if m:
        try:
            return float(m.group(1).replace(",", "")) / float(m.group(2).replace(",", ""))
        except ZeroDivisionError:
            return 0
    return 0


def section_params(title, section):
    """Parse-API params ({"page", "section"}) selecting a section by heading (fuzzy)."""
    sections = api(action="parse", page=title, prop="sections", redirects=1).get("parse", {}).get("sections", [])
    match = next((s for s in sections if s["line"].lower() == section.lower()), None) \
        or next((s for s in sections if section.lower() in s["line"].lower()), None)
    if not match:
        names = ", ".join(s["line"] for s in sections)
        raise WikiError("No section {!r} on {!r}. Sections: {}".format(section, title, names))
    # Transcluded sections ("T-2") live on another page; fetch them from there.
    if match["index"].startswith("T-"):
        return {"page": match["fromtitle"].replace("_", " "), "section": match["index"][2:]}
    return {"page": title, "section": match["index"]}


def page_text(title, section, max_chars):
    params = {"action": "parse", "page": title, "prop": "text", "disablelimitreport": 1, "redirects": 1}
    params.update({"section": 0} if section is None else section_params(title, section))
    data = api(**params)
    if "error" in data:
        raise WikiError(data["error"].get("info", "parse failed"))
    text = html_to_text(data["parse"]["text"]["*"])
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated; use --max-chars or a narrower --section)"
    return text


def cmd_page(args):
    title = resolve_title(args.name)
    if args.sections:
        sections = api(action="parse", page=title, prop="sections", redirects=1).get("parse", {}).get("sections", [])
        print("# " + title)
        for s in sections:
            print("  " * (int(s["toclevel"]) - 1) + "- " + s["line"])
        return
    text = page_text(title, args.section, args.max_chars)
    print("# {}{}".format(title, " > " + args.section if args.section else ""))
    print(text)


def cmd_price(args):
    title = resolve_title(args.name)
    rows = bucket("infobox_item", ["item_name", "item_id"], "page_name", title)
    print("# " + title)
    for row in rows:
        for item_id in row.get("item_id") or []:
            data = fetch_json(PRICES + "/latest", {"id": item_id}, ttl=300).get("data", {}).get(item_id)
            if not data:
                print("- {} (id {}): not traded on the GE".format(row.get("item_name"), item_id))
                continue
            print("- {} (id {}): buy {} / sell {} gp".format(row.get("item_name"), item_id, data.get("high"), data.get("low")))


ICON_DIR = CACHE_DIR / "icons"


def icon_file(name, quantity=1):
    """Downloads (once) and returns the path of an item's inventory icon.

    Stackable items have one icon per stack size ("Coins 10000.png"); the
    largest variant not above `quantity` is used, as in game.
    """
    title = resolve_title(name)
    rows = bucket("infobox_item", ["item_name", "image"], "page_name", title)
    row = next((r for r in rows if wiki_norm(r.get("item_name", "")) == wiki_norm(name)), rows[0] if rows else {})
    images = row.get("image") or ["File:{}.png".format(title)]

    def stack_size(image):
        m = re.search(r" (\d+)\.png$", image)
        return int(m.group(1)) if m else 0
    sized = sorted((i for i in images if stack_size(i) <= quantity), key=stack_size)
    image = (sized or images)[-1]

    path = ICON_DIR / (re.sub(r"[^A-Za-z0-9._-]+", "_", image[len("File:"):]))
    if path.exists():
        return path
    info = api(action="query", titles=image, prop="imageinfo", iiprop="url")
    page = next(iter(info.get("query", {}).get("pages", {}).values()), {})
    url = (page.get("imageinfo") or [{}])[0].get("url")
    if not url:
        raise WikiError("No icon on the wiki for {!r}".format(name))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


MAP_RE = re.compile(r'<a[^>]*mw-kartographer-map[^>]*>')


def map_points(title, section=None):
    """Map pins embedded in a page (or one section): [{"x", "y", "plane", "mapid", "context"}].

    `context` is the text of the table row or paragraph the map sits in, so
    pins on list pages (one map per patch, shop, ...) can be told apart.
    """
    params = {"action": "parse", "page": title, "prop": "text", "disablelimitreport": 1, "redirects": 1}
    if section is not None:
        params.update(section_params(title, section))
    data = api(**params)
    if "error" in data:
        raise WikiError(data["error"].get("info", "parse failed"))
    html = data["parse"]["text"]["*"]
    points = []
    for chunk in re.split(r"<tr[ >]|<p>", html):
        for m in MAP_RE.finditer(chunk):
            attrs = dict(re.findall(r'data-([a-z]+)="([^"]*)"', m.group(0)))
            if "lat" not in attrs or "lon" not in attrs:
                continue
            context = re.sub(r"\s+", " ", html_to_text(MAP_RE.sub("", chunk.split("<a class=\"mw-kartographer")[0]))).strip(" |-")
            points.append({"x": int(float(attrs["lon"])), "y": int(float(attrs["lat"])), "plane": int(attrs.get("plane", 0)),
                           "mapid": int(attrs.get("mapid", 0)), "context": context[:120]})
    return points


def cmd_coords(args):
    title = resolve_title(args.name)
    points = map_points(title, args.section)
    print("# Map pins on {}{}".format(title, " > " + args.section if args.section else ""))
    if not points:
        print("none (try another page or --section)")
    for p in points:
        print("- {} {} {}{}  {}".format(p["x"], p["y"], p["plane"], "" if p["mapid"] == 0 else " (map {})".format(p["mapid"]), p["context"]))


def wiki_norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def cmd_icon(args):
    print(icon_file(args.name, args.qty))


def cmd_search(args):
    for title in search(args.name, args.limit):
        print("- " + title)


def main(argv=None):
    global refresh
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, help_text):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("name", help="page, item, or quest name (fuzzy)")
        p.add_argument("--refresh", action="store_true", help="ignore the cache")
        p.set_defaults(func=func)
        return p

    add("item", cmd_item, "item ID, members, tradeable, weight")
    add("quest", cmd_quest, "quest requirements as a prerequisite tree")
    add("recipe", cmd_recipe, "how the item is made")
    p = add("sources", cmd_sources, "shops, drops and recipes for an item")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--max-chars", type=int, default=2000)
    p = add("page", cmd_page, "a page's intro, or one section of it")
    p.add_argument("--section", help="section heading (fuzzy)")
    p.add_argument("--sections", action="store_true", help="list section headings")
    p.add_argument("--max-chars", type=int, default=4000)
    add("price", cmd_price, "current Grand Exchange price")
    p = add("coords", cmd_coords, "game coordinates of the map pins on a page (patches, shops, spots, ...)")
    p.add_argument("--section", help="section heading (fuzzy)")
    p = add("icon", cmd_icon, "download an item's inventory icon; prints the file path")
    p.add_argument("--qty", type=int, default=1, help="stack size, picks the matching stack icon")
    p = add("search", cmd_search, "find page titles")
    p.add_argument("--limit", type=int, default=5)

    args = parser.parse_args(argv)
    refresh = args.refresh
    try:
        args.func(args)
    except WikiError as e:
        print("error: {}".format(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

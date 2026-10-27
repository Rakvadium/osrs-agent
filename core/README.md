# core: wiki lookups and snapshot checks

These scripts are the deterministic tools the planning skills call. They need only Python 3.8+ and its standard library, with nothing to install.

## `wiki.py`: OSRS Wiki lookups

Results are short plain text for an agent to read. Names are fuzzy: an exact page title is used if one exists, otherwise the top search result.

```
python wiki.py item "Dramen staff"      # ID, GE-tradeable/members/buy limit, weight, quest item
python wiki.py quest "Fairytale II"     # prerequisite quest tree, skills (boostable / needed to start), items, ironman notes
python wiki.py recipe "Dramen staff"    # materials, tools, facility, skill levels
python wiki.py sources "Dramen branch"  # shops, drops (most common first), recipes; falls back to the page intro
python wiki.py page "Fairy ring" --sections
python wiki.py page "Fairy ring" --section "Using fairy rings"
python wiki.py price "Rune scimitar"    # live GE buy/sell
python wiki.py search "fairy ring codes"
```

- **Data sources:** structured data comes from the wiki's [Bucket API](https://oldschool.runescape.wiki/w/RuneScape:Bucket), and prices come from the [Real-time Prices API](https://prices.runescape.wiki).
- **Cache:** responses are stored in `~/.cache/osrs-agent/wiki/` for 7 days, or 5 minutes for prices. Add `--refresh` to any command to bypass the cache.

## `transport.py`: where teleports land

```
python transport.py find "Ardougne cloak"   # -> 2665 3374 0, with item/diary requirements
python transport.py find "ALQ"              # fairy ring codes, with or without spaces
```

Searches teleport items, spells, fairy rings, quetzals, spirit trees, gnome gliders, charter ships, boats and more. Each result gives the arrival coordinates (`x y plane`) and the requirements. The data is the transport tables of the [Shortest Path](https://github.com/Skretzo/shortest-path) RuneLite plugin (BSD-2-Clause), cached for 7 days.

`wiki.py coords "<page>" [--section ...]` gives the other half: the coordinates of the map pins on a wiki page, such as each farming patch on `Farming/Patch locations`.

## `card.py`: plan image cards

```
python card.py plan.json --rsn NAME --title "Optimal herb run"
```

Renders the plan's loadout as an in-game-style card: the equipment screen and a 28-slot inventory grid with wiki icons, including stack-size icons and quantity labels. Each item is drawn by its status against the snapshot: in place, owned (equip it), in the bank (withdraw it), or not owned (greyed out). An item's optional `"note"` shows on hover. The output is a single self-contained HTML file; the script prints its path. Use `--icon-paths --inline` for a lighter file, for viewers that display local images and frame the card themselves.

`wiki.py icon "<item>" [--qty N]` downloads one icon and prints its cached path.

**Route maps:** with a `"route"` in the plan (`python card.py --help` shows the format), the card adds an overview map numbering every destination, plus one map per leg. Each leg map shows where the teleport lands, the destination, and a dashed arrow with the run distance in squares. Each map zooms to fit its leg. Tiles come from the wiki's map (`maps.runescape.wiki`) and are cached under `~/.cache/osrs-agent/wiki/tiles/`. Arrows are straight lines that show direction, not the walking path around walls.

## `check.py`: compare requirements against your snapshot

```
python check.py quest "Fairytale II" [--rsn NAME]
python check.py has "Dramen staff" "Knife" [--rsn NAME]
```

- **`quest`** walks the wiki's prerequisite tree against your quest states. Branches you've already completed are collapsed. It reports missing skill levels for the quest and for each unfinished prerequisite, plus quest points, and ends with a blocker count.
- **`has`** reports where each item is (equipment, inventory, rune pouch, looting bag, bank, seed vault, tackle box, group storage) or `[missing]`. It also lists similarly named items, so variants are visible. If the bank was never captured, it says so instead of reporting the item as missing.

By default, snapshots are read from `%USERPROFILE%/.runelite/plugin-data/osrs-agent/snapshots/`; set `OSRS_AGENT_SNAPSHOTS` to read from elsewhere. `--rsn` is optional when only one character has a snapshot.

# Gates: requirements that are easy to miss

Use this as a **checklist of what to look up**, not a source of facts. Confirm each matching gate with the `wiki.py` command shown, because the wiki is the source of truth. When you find a gate that's missing here, tell the user so it can be added.

## Travel

| Method | Gates to check | Look up |
|---|---|---|
| Fairy rings | A dramen or lunar staff **worn** (not needed after the Lumbridge elite diary); the quest chain Restless Ghost, Priest in Peril, Nature Spirit, Lost City and Fairytale I finished, plus Fairytale II progressed until "granted permission" | The staff rule: `wiki.py page "Dramen staff"`. The quests: `wiki.py page "Fairy ring" --section "Using fairy rings"` |
| Spirit trees | Quest unlock; some destinations have their own requirements | `wiki.py page "Spirit tree"` |
| Gnome gliders | Quest unlock; some destinations unlock separately | `wiki.py page "Gnome glider"` |
| Teleport spells | Magic level, runes (count the rune pouch and elemental staves), and the right spellbook. Ancient and Lunar spellbooks are quest-locked | `wiki.py page "<spell name>"` |
| Teleport jewellery and items | Charges left (the item name shows them); some need a quest or diary for certain destinations | `wiki.py page "<item>"` |
| Quest-specific items (ectophial, ...) | Quest completion; some need recharging | `wiki.py item "<item>"` |
| Charter ships and boats | Coins; some ports need a quest | `wiki.py page "Charter ship"` |
| Canoes | Woodcutting level per canoe type | `wiki.py page "Canoe"` |
| Walking into Morytania | Priest in Peril to pass the Paterdomus temple | `wiki.py quest "Priest in Peril"` |
| Entrana | No weapons or armour can be brought onto the island | `wiki.py page "Entrana"` |
| Wilderness | Risk of losing items; hardcore accounts risk their status | Say this in the plan |
| Members-only areas | A members world (the snapshot's `worldTypes` includes `MEMBERS`) | |

## Activities

| Activity | Gates to check | Look up |
|---|---|---|
| Farming runs (herb, tree, fruit tree, ...) | The wiki's run guide has the full patch list, best teleport per patch, and the recommended inventory | `wiki.py page "Farming runs" --sections` |
| Farming patches | Farming level per seed; some patches are quest- or diary-locked; tools (spade, dibber, rake, secateurs) may be in tool leprechaun storage | `wiki.py page "<patch name>"`, `wiki.py item "<seed>"` |
| Skilling guilds | Skill level; some allow boosts and some don't | `wiki.py page "<guild>"` |
| Bosses and slayer monsters | Slayer level or task, quest unlocks, required protective items | `wiki.py page "<monster>"` |
| Anything made | Recipe skill level, tools and facility | `wiki.py recipe "<item>"` |

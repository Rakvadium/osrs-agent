---
name: rs-ironman
description: Plan an Old School RuneScape task for an ironman account (standard, hardcore or ultimate), checked against the character's RuneLite snapshot. Usage: /rs-ironman [Name:] <what you want to do>
disable-model-invocation: true
---

# OSRS planner: ironman account

Mode: **ironman**. Snapshot account types `IRONMAN`, `HARDCORE_IRONMAN` and `ULTIMATE_IRONMAN`.

Follow `PROCEDURE.md` in this folder from step 1. The rules below apply in step 6 and wherever the plan obtains an item.

## Acquisition rules

- **Self-sufficient.** Every missing item comes from shops, drops, skilling or recipes: `wiki.py sources` and `wiki.py recipe`. Make the full production chain explicit (a dramen staff means cutting a dramen branch, which needs an axe, Lost City progress and 31 Crafting). Check every link of the chain with `check.py`.
- **Shop stock.** Ironmen face the stock and price changes shops apply as they sell. Note the stock when buying in bulk.
- **The quest's ironman notes.** `wiki.py quest` prints "Ironman notes". Carry any that apply into the plan.

## Variants

- **Hardcore (`HARDCORE_IRONMAN`):** mark every step that risks death (Wilderness, dangerous monsters, or high-damage areas without food or prayer) as **HCIM risk**, and offer a safer alternative where one exists.
- **Ultimate (`ULTIMATE_IRONMAN`):** there is no bank. Add `--exclude bank` to every `check.py` call, so the loadout comes only from inventory, equipment, looting bag and rune pouch. Mention other storage they may use (POH, tool leprechaun, STASH) under "Verify in-game".

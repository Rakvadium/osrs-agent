---
name: rs-regular
description: Plan an Old School RuneScape task for a regular (non-ironman) account, checked against the character's RuneLite snapshot. Usage: /rs-regular [Name:] <what you want to do>
disable-model-invocation: true
---

# OSRS planner: regular account

Mode: **regular**. Snapshot account type `NORMAL`.

Follow `PROCEDURE.md` in this folder from step 1. The rules below apply in step 6 and wherever the plan obtains an item.

## Acquisition rules

- **Grand Exchange first.** For tradeable items, quote the current price from `wiki.py price` and the buy limit from `wiki.py item`, then total the cost of all blockers.
- **Check coins.** Compare the total against the coins and platinum tokens `check.py has` finds. A shortfall is a blocker.
- **Untradeable items** (`wiki.py item` says "not on the GE") follow the ironman route: shops, drops, recipes, quests.
- **Skill levels** can't be bought. In Optimal answers, each gear-up stage gives the XP gap and the fastest reasonable training method. In other answers, give the XP gap, and a training method only if the user asks for training advice.

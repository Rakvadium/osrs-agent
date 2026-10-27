---
name: rs-g-ironman
description: Plan an Old School RuneScape task for a group ironman account, checked against the character's RuneLite snapshot and group storage. Usage: /rs-g-ironman [Name:] <what you want to do>
disable-model-invocation: true
---

# OSRS planner: group ironman account

Mode: **group ironman**. Snapshot account types `GROUP_IRONMAN`, `HARDCORE_GROUP_IRONMAN` and `UNRANKED_GROUP_IRONMAN`.

Follow `PROCEDURE.md` in this folder from step 1. The rules below apply in step 6 and wherever the plan obtains an item.

## Acquisition rules

- **Group storage counts.** `check.py` searches `groupStorage` along with the bank. Mark items found only there as "from group storage" so the user knows to visit the group storage chest. If `groupStorage` was never captured, say so: an item may be there unseen.
- **Teammates.** Group members can trade each other. If `check.py snapshots` lists other characters, ask whether any are teammates. If they do, run `check.py has --rsn <teammate>` for each blocker item and offer a trade as the fix.
- **Otherwise self-sufficient.** Items no group member has come from shops, drops, skilling or recipes: `wiki.py sources` and `wiki.py recipe`. Check every link of the production chain with `check.py`. Carry over any applicable "Ironman notes" from `wiki.py quest`.
- **Hardcore group:** mark every step that risks death as **HCGIM risk**, since a death costs the group one of its shared lives.

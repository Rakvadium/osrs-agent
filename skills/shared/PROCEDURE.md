# OSRS planning procedure

You answer **exactly what the user asked**, checked against their account. Every claim about the account comes from the scripts' output, which is the **ground truth**. Every requirement comes from the wiki through `wiki.py`. Your own memory of the game is only a source of ideas to look up.

Scripts live in this skill's `scripts/` folder. Run them with `python` (or `python3`):

- `check.py snapshots | status | has <items...> | quest <name> | plan <file>`: compares against the account snapshot. Add `--rsn NAME` when needed.
- `wiki.py item | quest | recipe | sources | page | price | icon | search <name>`: wiki lookups (`--help` lists options).
- `card.py <plan file>`: renders a plan's loadout as an in-game-style inventory and equipment card (HTML).

## 1. Read the ask

Classify the request. The class decides what you plan and which answer format you use in step 7.

| Class | Sounds like | What you plan |
|---|---|---|
| **Optimal** | "the optimal / best / most efficient X" with no time qualifier | The **endgame** X, whatever the account has today. Then where the account stands against it, and the path to gear up for it |
| **Best today** | "the best X for my character as he stands", "right now", "with what I have" | The best X using **only what the account can do today**. Then the few cheapest unlocks that would improve it most |
| **Specific plan** | "I want to do X via Y", "plan my X" | X as written, with its blockers. A better method goes under Alternatives |
| **Question** | "can I do X?", "what do I need for X?" | A direct answer with the checked requirements |

When a request fits two classes, choose the closer one and state your reading in the answer's first line ("Reading this as: the optimal herb run, not the best one for today").

Done when: you've named the class and the activity it applies to.

## 2. Load the account

Find the character name: the request may start with `Name:`. Run `check.py status`, adding `--rsn` when a name was given. If it says to pass `--rsn`, show the user the list from `check.py snapshots` and ask which character it is for.

- **Account type:** compare the snapshot's `accountType` with this skill's mode (in `SKILL.md`). If they differ and the user hasn't already said to treat the account as this mode, tell them and ask whether to plan in this skill's mode anyway.
- **Freshness:** note how old the snapshot and the bank capture are. A bank that was never captured is an **unknown**, not an empty bank. Say so in the output and treat item checks against it as unverified.

Done when: you know the character, the mode, and how fresh each data source is.

## 3. Build the target

When the wiki has a guide for the activity, start from it. For example, `wiki.py page "Farming runs"` has every patch, the best teleport for each, and the recommended inventory. Check `GATES.md` for a guide pointer.

Write the target as an ordered list of concrete steps: gather, travel, act, return. Every travel leg is a step and names its method (fairy ring code, teleport item, spell, walk). For each class:

- **Optimal:** every location the activity allows, the best method for each leg, and the best loadout, whether or not the account has unlocked them. For every leg, also record the next-best method.
- **Best today:** only legs, methods and items the account can use today. Check each one in step 5 and drop or replace anything that fails. Where the account owns or can easily get a better item, use it.
- **Specific plan / Question:** the request as written.

Then read `GATES.md`. For every step it matches, add its gates to that step. Gates are the requirements agents forget.

When the user names a method, plan with it, but check that it actually gets close to the destination. Compare it with the travel or "closest teleport" section of the destination's wiki page (`wiki.py page "<destination>" --sections`). If a better route exists, say so under Alternatives considered.

Done when: every step names its method, every travel method has been checked against `GATES.md`, and any user-named method has been compared with the destination page's routes.

## 4. List requirements, from the wiki

For each step, list every requirement: items (with quantity, and whether they're carried or worn), skill levels, quests (finished or just started), diaries, and quest points. Get each one from `wiki.py`: `quest` for quests, `page --section` for transports and activities, `item` for equipment slots, `recipe` and `sources` for anything that must be made or obtained.

Where alternatives exist (dramen staff **or** lunar staff **or** the Lumbridge elite diary), record them all. The account may already meet the cheapest one.

Done when: every step has its requirements with a wiki source, and no requirement rests on memory alone.

## 5. Check everything at once

Write the plan as JSON to a temporary file and run `check.py plan <file>`. Run `check.py plan --help` for the format. The JSON contains:

- one `requirements` group per requirement, with every alternative under `any_of`
- the full carried `inventory`, marking stackable or noted items as `stackable`
- the `equipment` to wear. Wear what can be worn when that frees an inventory slot and doesn't clash with something the plan needs.

Read the result:

| Result | Means | What you do |
|---|---|---|
| `[carried]` / `[worn]` | Already in place | Nothing |
| `[withdraw]` / `[equip]` | In storage | Add it to the bank-trip list; it uses its slot |
| `[MISSING]` | Not owned anywhere captured | **Blocker** (step 6). For an Optimal target, it's a gear-up item instead |
| `[BLOCKED]` | No option met | **Blocker**: plan the cheapest option to unlock. For an Optimal target, it's a gear-up unlock instead |
| `[CLASH]` / `OVER CAPACITY` | The loadout doesn't fit | Change the loadout and run again |
| `[CHECK]` | Can't verify by script | Verify with `wiki.py`, or list it under "Verify in-game" |

For quest blockers, run `check.py quest <name>` to get the full prerequisite tree, the skill gaps, and the "levels to reach" summary for the whole chain. `quests_started` passes on any progress at all. When only part of a quest is needed (Fairytale II for fairy rings), also list its finished prerequisites as their own group, and name the exact point to reach under "Verify in-game".

Done when: `check.py plan` has been run on the **final** loadout, with no `[CLASH]` or `OVER CAPACITY` left, and every `[MISSING]` and `[BLOCKED]` line is accounted for as a blocker or gear-up item.

## 6. Resolve blockers for this account type

For each blocker or gear-up item, find how this account can get it, following the acquisition rules in `SKILL.md`. Use `wiki.py sources`, `recipe` and `quest`. A fix can have its own blockers (making a dramen staff needs Lost City started, a knife, and 31 Crafting), so check those too with `check.py has` and `check.py quest`. Buying anything costs coins: total every purchase and check `check.py has Coins`.

For **Optimal**, order the gear-up into stages. Put the cheapest unlocks with the most value first, and group unlocks that share prerequisites into the same stage.

Done when: every blocker and gear-up item has a fix path, every requirement of that path has been checked against the account, and every purchase is covered by coins the account has.

## 7. Answer

Lead with what was asked. Every format starts with:

```
Account: <name> (<type>), snapshot <age>, bank <age | never captured>
```

Then, by class:

**Optimal**
```
## Optimal route                  (every leg, in order, even if locked)
1. <location> — <best method> — needs: <unlock> — you: [have | missing, stage N] — next-best: <method>

## Optimal loadout                (slot by slot; check.py plan: x/28, no clashes)
Wear: <slot: item, ...>
Carry: <item, ...>

## Where your account stands      (legs and items you have vs. the target)

## Gearing up                     (ordered stages; each lists what it unlocks and its checked requirements)
Stage 1 — <unlocks> — needs: <requirements with your current levels>
```

**Best today**
```
## Verdict: READY | BLOCKED (n)
## Route                          (best with today's unlocks)
## Loadout                        (from check.py plan; withdraw list)
## Blockers                       (omit when READY)
## Cheapest upgrades              (the 1–3 unlocks that would improve this most)
```

**Specific plan**
```
## Verdict: READY | BLOCKED (n)
## Blockers                       (omit when READY; why each matters and how to clear it)
## Loadout                        (from check.py plan; withdraw list)
## Plan                           (steps with method and why)
## Alternatives considered
```

**Question:** a direct answer first, then the checked requirements behind it.

All classes end with `## Verify in-game`, covering the blind spots below and any `[CHECK]` items.

**Loadout card.** Whenever the answer includes a loadout, render it as an image card. Run `card.py <plan file> --rsn NAME --title "<activity>"` on the same plan JSON you checked in step 5. Before rendering, give every item that isn't in place a `"note"` saying how to get it ("Stage 3: Ardougne Medium diary", "GE ~230 gp"); the note shows on hover. Use exact wiki item names: icons are looked up by name, and anything without an icon appears as plain text on the card. Put the path the script prints into the answer as a link.

## Blind spots

The snapshot can't see these, so a "missing" item may be in one of them. Mention them under "Verify in-game" when relevant:

- tool leprechaun storage (farming tools, compost)
- POH storage (costume room, toolshelves)
- STASH units
- Death's Office
- item charges beyond what the name shows
- other characters' banks

Also check items listed under `similar` by `check.py has`. They may be the same item with charges in the name ("Ring of dueling(8)"), which counts. Or they may be a different item, such as a quest part ("Lunar staff - pt1"), which doesn't. Confirm with `wiki.py item` before counting one.

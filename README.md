# osrs-agent

Ask an AI assistant for an Old School RuneScape plan, like "farm run with these seeds via fairy ring AJP", and get one checked against **your actual account**. The plan includes the blockers it found, with why each matters and how to clear it.

```
RuneLite + plugin ──writes──▶ snapshot .json ◀──reads── /rs-ironman in Claude Code or Kiro
                                                   └──▶ OSRS Wiki (cached lookups)
```

| Folder | What it is |
|---|---|
| [`plugin/`](plugin/README.md) | RuneLite plugin that exports your levels, quests, diaries, inventory, equipment and bank |
| [`core/`](core/README.md) | `wiki.py` (wiki lookups and item icons), `check.py` (requirement and loadout checks against the snapshot), and `card.py` (in-game-style loadout image cards) |
| `skills/` | The `/rs-regular`, `/rs-ironman` and `/rs-g-ironman` skills, plus the shared `PROCEDURE.md` and `GATES.md` |
| `install.py` | Copies the skills into Claude Code and/or Kiro |

## Setup

1. **Plugin:** follow [plugin/README.md](plugin/README.md). Log in once and open your bank.
2. **Skills:** run `python install.py`. This installs for Claude Code and Kiro, for all projects. Use `--tool claude` or `--tool kiro` for just one, and `--uninstall` to remove them. Re-run the script after editing anything in `skills/` or `core/`.
3. **Requirement:** Python 3.8+ (standard library only).

## Use

In Claude Code or Kiro, type the skill for the account type, optionally the character name, then the request:

```
/rs-ironman Zezima: farm run with ranarr seeds, using fairy ring AJR
/rs-regular get me set up for Barrows
/rs-g-ironman Zezima: what do I need for Dragon Slayer II?
```

The skill follows a fixed procedure. It loads the snapshot, breaks the request into steps, looks up each step's requirements on the wiki, checks them all with `check.py plan`, and works out how to clear each blocker for your account type. It then answers with a verdict, blockers, loadout and route.

## Improving it

- **Missed requirement:** add the gate to [`skills/shared/GATES.md`](skills/shared/GATES.md). It lists what to look up, not the facts themselves.
- **Planning process:** change [`skills/shared/PROCEDURE.md`](skills/shared/PROCEDURE.md).
- **Account-type rules:** change the `SKILL.md` for that account type.

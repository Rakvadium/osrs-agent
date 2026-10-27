# Quickstart

Setup takes about 15 minutes the first time. Afterwards it's two steps: start the client, then ask.

What you get: ask Kiro or Claude Code something like `/rs-regular YourName: best setup for birdhouse runs`, and get a plan checked against **your** account. It covers what blocks you, the exact loadout, and a route with maps and walking paths. It also produces a plan card, a single page you can open on your phone.

## 1. Install the prerequisites (once)

| Tool | Version | Get it | Check it |
|---|---|---|---|
| Java | **17 or newer** (21 recommended) | [adoptium.net](https://adoptium.net), "Temurin 21 LTS" | `java -version` |
| Python | 3.8 or newer | [python.org](https://www.python.org/downloads/). On Windows, tick **"Add python.exe to PATH"** in the installer | `python --version` (Mac/Linux: `python3 --version`) |
| Git | any | [git-scm.com](https://git-scm.com) | `git --version` |
| An AI assistant | — | [Kiro](https://kiro.dev) or Claude Code | — |

Open a new terminal after installing, so it finds the new commands.

## 2. Get the project (once)

```
git clone <the repo link you were given> osrs-agent
cd osrs-agent
```

## 3. Install the skills (once, and after every update)

From the `osrs-agent` folder:

```
python install.py --tool kiro      # Kiro
python install.py --tool claude    # Claude Code
python install.py                  # both
```

On Mac/Linux, use `python3`. This copies the `/rs-regular`, `/rs-ironman` and `/rs-g-ironman` skills into your assistant's skills folder, so they work in any project. Restart Kiro or Claude Code afterwards so it picks them up.

## 4. Start RuneLite with the plugin (every time you play)

The plugin isn't on the RuneLite Plugin Hub, so it runs in a development copy of RuneLite. This doesn't use the Jagex Launcher.

```
cd plugin
.\gradlew run       # Windows (PowerShell)
gradlew.bat run     # Windows (Command Prompt)
./gradlew run       # Mac/Linux
```

The first run downloads Gradle and RuneLite, which takes a few minutes; later runs take seconds. A RuneLite window opens. Keep the terminal open: closing the RuneLite window stops it.

## 5. Log in

**Jagex account (first time only):**
1. In RuneLite's right-hand sidebar, click the **Jagex account** icon.
2. Click **Add Jagex Account** and finish the login in the popup, including any authenticator code. Let the popup close by itself.
3. Pick your character in the sidebar, then click **Play Now**.

On later launches, just pick your character and click **Play Now**. With an old-style (non-Jagex) account, log in on the normal login screen.

## 6. Open your bank once

The game only shows the bank while it's open, so the plugin can't record it until then. After that it's remembered between sessions. Your snapshot is saved here and updates while you play:

- Windows: `%USERPROFILE%\.runelite\plugin-data\osrs-agent\snapshots\<yourname>.json`
- Mac/Linux: `~/.runelite/plugin-data/osrs-agent/snapshots/<yourname>.json`

## 7. Ask

In Kiro or Claude Code, type the skill for your account type, your character name, then the request:

```
/rs-regular YourName: What's the best setup and route for birdhouse runs?
/rs-ironman YourName: As my character stands today, what's the best way to train Thieving?
/rs-regular YourName: Can I do Barrows yet?
/rs-g-ironman YourName: I want to kill blue dragons in the Heroes' Guild basement, plan my trip.
```

How you phrase it matters:
- **"Optimal" or "best"** gets the endgame version, with a path to unlock it.
- **"As I stand today" or "right now"** gets the best you can do now.
- **"I want to do X"** gets that plan with its blockers.
- **"Can I…?"** gets a direct answer.

**What to expect while it works:**
- **Command approvals.** The assistant runs small Python scripts from the skill's `scripts/` folder: `check.py` (your account), `wiki.py` (wiki lookups), `transport.py`, `pathfind.py` and `card.py`. Kiro and Claude Code ask before running commands. Approve them, or mark `python` commands as trusted so it stops asking.
- **Time.** A full answer takes a few minutes and several dozen lookups. Lookups are cached for a week, so repeat questions are faster.
- **Model choice in Kiro.** Pick a Claude model rather than "Auto". Planning takes a strong model, and it's worth the extra credits.
- **If Kiro can't run the skill's scripts** (for example, it refuses files outside the open project), install the skills into the repo instead with `python install.py --tool kiro --scope project`, then open the `osrs-agent` folder in Kiro and ask from there.

Every answer with a loadout or route also produces a **plan card** in `Documents/osrs-agent-cards/`. It's one HTML file with the whole answer, inventory panels and maps, and it works offline. Send it to your phone to use while you play.

## Troubleshooting

| Problem | Fix |
|---|---|
| `java` / `python` "not recognized" | Install it (step 1), then open a **new** terminal. On Windows, try `py` instead of `python`. |
| Gradle fails with "Unsupported class file major version" or won't start | Your Java is older than 17. Install Temurin 21 and check `java -version`. |
| `./gradlew: Permission denied` (Mac/Linux) | Run `chmod +x gradlew` in the `plugin` folder. |
| "Unable to add Jagex account: Login did not return an id token" | The login popup closed before it finished. Click **Add Jagex Account** again and complete it. |
| No snapshot file appears | Make sure you're fully logged into the game (not the login screen), then wait a few seconds. |
| The answer says your bank was "never captured" | Open your bank in game once. |
| The skill isn't found (`/rs-regular` does nothing) | Re-run `python install.py`, then restart Kiro or Claude Code. |
| "Pass --rsn; snapshots available: …" | Put your character name before the request: `/rs-regular YourName: …`. |

## Updating

```
git pull
python install.py --tool kiro
```

Restart the RuneLite client so it picks up any plugin changes.

## Privacy

- **Stays on your computer:** the plugin only reads your own account and writes a file to your computer. It never sends anything anywhere itself.
- **Shared with your AI provider:** when you ask a question, the assistant reads your snapshot, so its contents (levels, quests, items) go to the AI provider as part of the conversation.
- **Other connections:** wiki lookups go to the OSRS Wiki, and map and transport data comes from the OSRS Wiki and GitHub.

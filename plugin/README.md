# OSRS Agent Snapshot (RuneLite plugin)

## What it does

This plugin keeps an up-to-date record of your account in a file on your computer. The file covers your levels, quests, achievement diaries, what you're carrying and wearing, and what's in your bank. The planning assistant in this repo reads that file. When you ask it for a plan, it can then check what you actually have and haven't done instead of guessing. For example, it can tell you that you need a dramen staff before you can use fairy rings.

The plugin works in the background: there's nothing to click and no overlay. It only reads your account and saves it to your computer. It never sends anything over the internet, and it never acts in the game for you.

## How to use it

**Starting the client** (the plugin isn't on the Plugin Hub, so the normal RuneLite launcher won't load it)
1. Install Java 17 or newer (21 recommended). Open a terminal in this `plugin` folder and run `./gradlew run` (`.\gradlew run` in PowerShell, `gradlew.bat run` in Command Prompt). The first run downloads RuneLite and takes a minute. This *is* "launching the client in developer mode": no IDE is needed.
2. A RuneLite window opens with the plugin loaded. Closing the window stops it.

**Logging in with a Jagex account** (first time only)
1. In the client's right-hand sidebar, click the Jagex account icon.
2. Click **Add Jagex Account** and log in through the popup window.
3. Pick your character in the sidebar, then click **Play Now** on the login screen.

On later launches, run `./gradlew run`, pick your character and click **Play Now**. More detail: [Using Jagex Accounts](https://github.com/runelite/runelite/wiki/Using-Jagex-Accounts).

**Each time you play**
1. Log in as usual. Your levels, quests, diaries, inventory and equipment are saved automatically.
2. **Open your bank once.** The game only shows the bank's contents while it's open, so the plugin can only record your bank after you've opened it. Do the same for the seed vault, looting bag, tackle box or group storage if you want them included.
3. Play normally. The file updates a few seconds after anything changes, and at least once a minute.

**Then ask the assistant** in Claude Code or Kiro, for example: `/rs-ironman YourName: farm run with these seeds via fairy ring AJP`. It reads your latest snapshot and plans around it. See the [repo README](../README.md) to install the skills.

## Good to know

- **Bank contents carry over.** The last bank contents it saw are kept between sessions, so you don't have to reopen the bank every login. Reopen it after big bank changes made without the plugin, such as on mobile or the normal launcher, so the snapshot isn't out of date.
- **Each character gets its own file**, so alts work automatically.
- **Changes made elsewhere aren't seen.** Changes made while playing on mobile or the normal launcher won't be picked up until you log in with this client again.
- **Karamja diary:** the easy, medium and hard tiers are read from older game values. Double-check them if the assistant gets them wrong.

## Reference: the snapshot file

`%USERPROFILE%\.runelite\plugin-data\osrs-agent\snapshots\<rsn>.json`. The name is lowercased, with runs of other characters replaced by `_`.

| Field | Contents |
|---|---|
| `rsn`, `accountType`, `world`, `location` | Who and where. `accountType` comes from the ironman varbit: `NORMAL`, `IRONMAN`, `GROUP_IRONMAN`, ... |
| `skills` | Real level, boosted level and XP for every skill. |
| `quests` | Quest name mapped to `NOT_STARTED` / `IN_PROGRESS` / `FINISHED`. |
| `diaries` | `region → tier → {complete, rawValue}`. |
| `runePouch` | Runes in the rune pouch. |
| `containers` | `inventory`, `equipment`, `bank`, `seedVault`, `lootingBag`, `tackleBox`, `groupStorage`. |

Each container has a `capturedAt` timestamp. A missing container means it has never been opened with the plugin running. Items record the unnoted `id`, `name`, `quantity` and `noted`. Inventory items also record their `slot` index, and equipment items record their slot name (`WEAPON`, `RING`, ...). The inventory also records `capacity` (28) and `freeSlots`.

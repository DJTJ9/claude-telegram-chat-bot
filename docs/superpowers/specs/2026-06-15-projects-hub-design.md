# Design: Projects Hub — Vision, Brainstorming & Lifecycle Workflow

**Date:** 2026-06-15
**Goal:** Separate brainstorming/planning artifacts from bot code into a dedicated `projects-hub` repo. Add `vision:` command, project selector with inline keyboard, feature-driven brainstorming, auto-push, and bot auto-restart.

---

## Overview

A new `projects-hub` git repo acts as the central storage for all project planning artifacts (VISION.md, specs, plans). The bot gains a project selector (inline keyboard), a `vision:` command for project foundation sessions, and an enhanced `brainstorming:` flow that is driven by the feature backlog from VISION.md. After each implementation, the bot auto-pushes both the hub repo and the target project repo, and restarts itself if bot files were changed.

---

## Architecture

### Hub Repo

```
projects-hub/                        ← new git repo (cloned on Pi + PC)
  projects-registry.json             ← list of all known projects
  topics/
    <project-slug>/
      VISION.md                      ← project goal, feature backlog, architecture
      specs/                         ← YYYY-MM-DD-<topic>-design.md
      plans/                         ← YYYY-MM-DD-<topic>.md
```

Existing repos remain unchanged. Bot-specific specs/plans stay in `telegram-notion-bot/docs/superpowers/`. Only new brainstorming/vision sessions land in the hub.

### Env Vars

| Var | PC Example | Pi Example |
|-----|-----------|------------|
| `HUB_DIR` | `C:\Projekte\projects-hub` | `/home/pi/projects-hub` |
| `WORK_DIR` | `C:\Projekte\telegram-notion-bot` | `/home/pi/telegram-notion-bot` |

`WORK_DIR` unchanged. `HUB_DIR` new — bot reads it for all hub operations.

`CLAUDE.md` gets a hub section so Claude Code on PC automatically has context.

---

## Project Registry

**`projects-registry.json`** (array, in hub root):

```json
[
  {
    "slug": "dart-app",
    "name": "DartApp",
    "path": "C:\\Unity\\DartApp",
    "repo": "https://github.com/DJTJ9/dart-app",
    "description": "Dart Trainings-App"
  },
  {
    "slug": "telegram-notion-bot",
    "name": "NotionBot",
    "path": "C:\\Projekte\\telegram-notion-bot",
    "repo": "https://github.com/DJTJ9/telegram-notion-bot",
    "description": "Telegram Notion Bot"
  }
]
```

- `path`: used by PC Claude sessions (direct filesystem access)
- `repo`: used by Pi Claude sessions (temporary clone for code context if needed)
- `path` may be omitted on Pi entries if project does not exist there
- New projects added via "➕ Neues Projekt" are appended by the bot automatically

---

## Inline Keyboard — Project Selector

**Trigger:** `projekte` or `/projekte`

```
Bot: Deine Projekte:

[➕ Neues Projekt]
[🎯 DartApp]
[🤖 NotionBot]
```

**Tap on existing project:**
```
Bot: DartApp — was möchtest du tun?

[🔭 Vision]  [🧠 Brainstorming]  [📋 Pläne]
```

**Tap on "🧠 Brainstorming"** → bot reads `topics/<slug>/VISION.md`, parses unchecked `- [ ] ...` entries:
```
Bot: DartApp — welches Feature brainstormen?

[🎯 Statistik-Dashboard]
[🎯 Multiplayer-Modus]
[✏️ Neues Feature → erst Vision]
```

Tapping a feature starts `_run_brainstorming(slug, feature)`. "✏️ Neues Feature" redirects to vision: session. If no VISION.md or no unchecked features:
```
Bot: Keine offenen Features für DartApp.
     [🔭 Vision starten]
```

**Tap on "📋 Pläne"** → bot lists plans from `topics/<slug>/plans/` as text (no Claude process).

**Tap on "➕ Neues Projekt":**
```
Bot: Name des neuen Projekts?
User: MeineApp
Bot: Wo soll das Projekt angelegt werden?
     A) C:\Projekte\MeineApp  B) Anderen Pfad eingeben  C) Noch kein Pfad (nur Planung)
```
After confirmation: entry appended to registry, vision: session starts automatically.

### Callback Handling

Bot's `getUpdates` gains `allowed_updates: ["message", "callback_query"]`. New `handle_callback_query()` dispatches based on `callback_data` (structured as `<action>:<slug>:<extra>`).

---

## `vision:` Command

### Trigger
- Inline keyboard: "🔭 Vision" button
- After "➕ Neues Projekt" path confirmation
- Direct: `vision: <slug-or-name>`

### `_run_vision(slug)`

Mirrors `_run_brainstorming`. Key specifics:
- Runs Claude in `HUB_DIR`
- Reads `topics/<slug>/VISION.md` if exists → appends/updates, never overwrites
- Reads `projects-registry.json` for project metadata
- If `path` exists on current machine: passes project directory for code context
- Timeout: 3600s
- All questions via `telegram_ask.py`
- Writes/updates `topics/<slug>/VISION.md`
- Sets `_vision_active = False`, sends completion message

### VISION.md Structure

```markdown
# <ProjectName> — Vision

## Ziel
What the project achieves.

## Features (Backlog — priorisiert)
- [ ] Feature A (Grundlage)
- [ ] Feature B (baut auf A auf)
- [x] Feature C (implementiert 2026-06-15)

## Architektur
Tech stack, patterns, key decisions.

## Offene Fragen
- ...

## Entscheidungen
- Entscheidung X: weil Y (2026-06-15)
```

Checkboxes are the integration point: `[x]` = implemented (checked after brainstorming session completes), `[ ]` = in backlog (shown as buttons in brainstorming selector).

---

## `brainstorming:` Enhancements

### Context passed to Claude
1. `projects-registry.json` — all known projects
2. `topics/<slug>/VISION.md` — feature backlog + architecture of target project
3. `topics/<slug>/specs/` — prior specs for this project (cross-session context)

### Output location
- Spec → `HUB_DIR/topics/<slug>/specs/YYYY-MM-DD-<topic>-design.md`
- Plan → `HUB_DIR/topics/<slug>/plans/YYYY-MM-DD-<topic>.md`
- `scheduled_plans.json` → `HUB_DIR/scheduled_plans.json`

### Post-implementation
After plan executed: Claude checks the implemented feature off in VISION.md (`[ ]` → `[x]`).

### Scheduling (unchanged flow)
Same "Jetzt / HH:MM / Später" questions as before, appending to hub's `scheduled_plans.json`.

### For existing projects (implementation path)
After plan is written: "Jetzt implementieren / unter /plans speichern?" — same as current flow. Implementation runs in target project's `path`.

---

## Auto-Push

After every successful implementation session, Claude executes:

**1. Hub repo (always):**
```bash
git -C "$HUB_DIR" add -A
git -C "$HUB_DIR" commit -m "chore: update <slug> after <feature>"
git -C "$HUB_DIR" push
```

**2. Implementation repo (when code changed):**
```bash
git -C "<project_path>" add -A
git -C "<project_path>" commit -m "feat: implement <feature>"
git -C "<project_path>" push
```

Claude receives this as an explicit post-implementation instruction in the brainstorming prompt. No separate bot mechanism needed.

Bot sends completion message:
```
✅ DartApp · Statistik-Dashboard implementiert
📦 Code gepusht → github.com/DJTJ9/dart-app
📋 Hub aktualisiert → github.com/DJTJ9/projects-hub
```

---

## Bot Auto-Restart

**Detection:** After implementation, Claude checks whether any changed files belong to `telegram-notion-bot/` — specifically `bot.py` or `scripts/`.

**Restart script** `scripts/restart_bot.sh` (new file):
```bash
#!/bin/bash
systemctl restart telegram-bot 2>/dev/null || (pkill -f bot.py; sleep 1; python bot.py &)
```

**Before restart, bot sends:**
```
🔄 Bot-Dateien geändert — starte neu...
(Bot kurz nicht erreichbar)
```

Claude calls `scripts/restart_bot.sh` at the end of the session if bot files were modified.

---

## End-to-End Flow

```
User: projekte
  → inline keyboard: [➕ Neues Projekt] [DartApp] [NotionBot]

User: [DartApp]
  → [🔭 Vision] [🧠 Brainstorming] [📋 Pläne]

User: [🧠 Brainstorming]
  → reads VISION.md → [🎯 Statistik-Dashboard] [🎯 Multiplayer] [✏️ Neues Feature]

User: [🎯 Statistik-Dashboard]
  → _run_brainstorming("dart-app", "Statistik-Dashboard")
  → Claude reads VISION.md + registry + prior specs
  → questions via telegram_ask.py
  → writes topics/dart-app/specs/2026-06-15-statistik-dashboard-design.md
  → invokes writing-plans
  → writes topics/dart-app/plans/2026-06-15-statistik-dashboard.md
  → scheduling: "Jetzt / HH:MM / Später"
  → implements in C:\Unity\DartApp
  → checks off [x] Statistik-Dashboard in VISION.md
  → git push dart-app + git push projects-hub
  → bot-restart? no (no bot.py changed)
  → ✅ Fertig-Nachricht
```

---

## Files Changed

| Repo | File | Change |
|------|------|--------|
| `projects-hub` | `projects-registry.json` | new |
| `projects-hub` | `topics/` | new (empty, populated by sessions) |
| `telegram-notion-bot` | `bot.py` | Add `_run_vision()`, `_vision_active`, `vision:` handler, `projekte` handler, `handle_callback_query()`, update `_run_brainstorming()` for hub paths, update `HILFE_TEXT` |
| `telegram-notion-bot` | `scripts/restart_bot.sh` | new |
| `telegram-notion-bot` | `.env` / deployment | Add `HUB_DIR` |
| `~/.claude/CLAUDE.md` | Hub section | Add hub path + registry info |

---

## Error Handling

- `HUB_DIR` not set → bot logs warning, falls back to `WORK_DIR` for hub operations
- Registry missing → treat as empty list, show only "➕ Neues Projekt"
- `VISION.md` missing for project → show "Vision starten" prompt
- No unchecked features → show "Vision starten" prompt
- `git push` fails → log error, send Telegram warning, do not block completion message
- Bot restart fails → log error, send Telegram warning with manual restart hint
- Concurrent vision + brainstorming → same flag pattern as `_brainstorming_active`
- New project with no `path` → implementation deferred (plan only), no code push

---

## Not In Scope

- Syncing project code to Pi (Pi reads via repo URL for context only, does not implement)
- Cancelling a running vision/brainstorming session
- Deleting projects from registry via bot
- Multiple concurrent sessions across different projects

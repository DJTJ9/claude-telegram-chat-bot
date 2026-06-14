# Design: `brainstorming:` Telegram Command

**Date:** 2026-06-15
**Goal:** Start a full brainstorming session (spec → plan → scheduling) from Telegram, with persistent project context via `VISION.md`.

---

## Overview

A new `brainstorming:` bot command launches a headless Claude Code process that runs `superpowers:brainstorming` interactively via the existing Telegram relay (`telegram_ask.py`). All clarifying questions, design approvals, and scheduling questions arrive in Telegram. The session ends with a spec file, a plan file, an updated `VISION.md`, and a scheduled implementation.

A companion `/specs` command lists available spec slugs for use with the optional `basis:` parameter.

---

## Command Syntax

```
brainstorming: <idee>
brainstorming: <idee>, basis: <spec-slug>
```

- `<idee>` — Feature idea or app concept (free text, max 500 chars)
- `basis: <spec-slug>` — Optional. Slug of a prior spec (e.g. `telegram-relay`) that Claude reads as context before starting

---

## Components

### 1. `_brainstorming_active` flag

Global boolean in `bot.py`. Set `True` when session starts, `False` when it ends (success or failure). Prevents concurrent sessions that would cause `telegram_ask.py` responses to route to the wrong process.

### 2. `_run_brainstorming(topic, basis_slug=None)`

Mirrors `_run_teach`. Runs in a daemon thread. Key differences:

- Timeout: **7200s** (2h, vs. 3600s for teach/plan)
- Prompt includes:
  - Instruction to invoke `superpowers:brainstorming`
  - Auto-read `VISION.md` if it exists in `WORK_DIR`
  - Auto-read matching spec file if `basis_slug` provided
  - Instruction to use Telegram relay for all questions
  - Instruction to update `VISION.md` after session completes
- Sets `_brainstorming_active = False` before sending completion message
- Uses `env = {**os.environ, "CLAUDE_AUTOMATED": "1"}`

### 3. `brainstorming:` handler

Placed in the message dispatch loop, before the `else` (general chat) branch. Logic:

1. Parse `basis:` subparameter if present
2. Check `_brainstorming_active` → reply with warning if active
3. Set flag, send acknowledgement, start daemon thread

### 4. `/specs` handler

Lists `docs/superpowers/specs/*.md`. For each file:
- Parses `YYYY-MM-DD-<slug>-design.md` → extracts date and slug
- Falls back to raw filename if pattern doesn't match

Output format:
```
📋 Vorhandene Specs:

2026-06-11 · telegram-relay
2026-06-11 · deferred-implementation

Nutzung: brainstorming: <idee>, basis: <slug>
```

### 5. `VISION.md`

Created/updated by Claude at the end of each brainstorming session. Location: `WORK_DIR/VISION.md`. Structure:

```markdown
# Vision

## Implementiert
- Feature X (spec: 2026-06-15-feature-x-design.md)

## Backlog
- Idee Y — gesammelt in Session 2026-06-15

## Offene Fragen
- ...

## Entscheidungen
- Entscheidung A: weil B
```

### 6. `HILFE_TEXT` update

New section added:

```
🧠 Brainstorming
  brainstorming: <idee> — Neue Feature-Idee brainstormen
  brainstorming: <idee>, basis: <slug> — Mit vorheriger Spec als Kontext
  /specs — Alle vorhandenen Specs anzeigen
```

---

## Data Flow

```
User: "brainstorming: Chat-App mit Räumen"
  → handler: set _brainstorming_active=True
  → thread: _run_brainstorming("Chat-App mit Räumen")
      → reads VISION.md (if exists)
      → claude --dangerously-skip-permissions -p "<prompt>"
          → superpowers:brainstorming skill
              → questions via telegram_ask.py → User replies in Telegram
              → writes docs/superpowers/specs/2026-06-15-chat-app-design.md
              → invokes writing-plans
              → writes docs/superpowers/plans/2026-06-15-chat-app.md
              → scheduling questions via telegram_ask.py
              → appends to scheduled_plans.json
              → updates VISION.md
  → _brainstorming_active=False
  → send_message: "✅ Brainstorming abgeschlossen"
```

---

## Files Modified

| File | Change |
|------|--------|
| `bot.py` | Add `_brainstorming_active`, `_run_brainstorming()`, `brainstorming:` handler, `/specs` handler, update `HILFE_TEXT` |

No new files required. `VISION.md` is created by Claude during the session, not by bot.py.

---

## Error Handling

- Empty topic → usage hint, no thread started
- Session already active → warning message, no second thread
- Claude process fails → `_brainstorming_active` reset to `False`, error sent to Telegram with last 300 chars of stderr
- Timeout (7200s exceeded) → subprocess raises `TimeoutExpired` → caught, flag reset, error sent
- `basis:` slug not found → Claude receives the slug and handles gracefully (will note it's missing)
- `/specs` dir missing → "Keine Specs vorhanden."

---

## Not In Scope

- Resuming an interrupted brainstorming session (process state is not persistent)
- Cancelling a running brainstorming session mid-flight
- Multiple concurrent brainstorming sessions

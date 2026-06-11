# Deferred Implementation — Design Spec

**Date:** 2026-06-11  
**Slug:** deferred-implementation  
**Status:** Approved

## Overview

Complete all brainstorming/planning phases interactively, then defer the implementation to a scheduled time (e.g., post-token-reset at night). Implementation runs fully headless (`--dangerously-skip-permissions`). User controls scheduling via Telegram; approves nothing during implementation.

## Architecture

Three additions to `bot.py`:

- **`_plan_loop`** — daemon thread, checks `scheduled_plans.json` every 60s, fires `_run_plan()` when `scheduled_time` matches current time and `status == "pending"`
- **`_run_plan(plan_path)`** — runs `claude --dangerously-skip-permissions`, 1 retry on failure, sends Telegram notification on completion
- **New message handlers** — `/plans`, `implement-plan:`, `abort-plan:`

New data file: `scheduled_plans.json` (git-versioned, alongside `reminders.json`)

## Data Model

`scheduled_plans.json`:

```json
[
  {
    "slug": "habits-task-dialog",
    "plan_path": "docs/superpowers/plans/2026-06-12-habits-task-dialog.md",
    "scheduled_time": "02:00",
    "status": "pending"
  },
  {
    "slug": "search-feature",
    "plan_path": "docs/superpowers/plans/2026-06-12-search-feature.md",
    "scheduled_time": null,
    "status": "pending"
  }
]
```

**Status values:** `pending` | `running` | `done` | `failed`

`scheduled_time: null` = "später" — appears in `/plans` list, never auto-triggered until user sets a time.

`_plan_loop` match condition: `status == "pending"` AND `scheduled_time == current HH:MM`.

## Brainstorming Workflow Changes

After the implementation plan file is written, Claude asks two questions (via Telegram relay if `notifications_enabled: true`, else terminal):

**Question 1:** "Wann implementieren? (`jetzt` / `HH:MM` / `später`)"

- `jetzt` → call `_run_plan(plan_path)` immediately in a thread; done, no further questions
- `HH:MM` or `später` → ask Question 2

**Question 2:** "Slug für diesen Plan? (Standard: `<slug-derived-from-filename>`)"

→ Write entry to `scheduled_plans.json`, git commit

Slug derivation: strip date prefix and `-design` suffix from plan filename. `2026-06-12-habits-task-dialog.md` → `habits-task-dialog`. User can override.

`plan_path` is relative to `PROJECT_DIR` (e.g., `docs/superpowers/plans/2026-06-12-habits-task-dialog.md`). `_run_plan` uses `cwd=PROJECT_DIR` so relative paths resolve correctly.

The "jetzt" path requires no slug — `plan_path` (absolute or derived) is passed directly to `_run_plan()`.

## Bot Commands

### `/plans`
Lists all entries in `scheduled_plans.json` with `status == "pending"`:

```
📋 Geplante Implementierungen

⏰ Geplant:
• habits-task-dialog — heute 02:00
• search-feature — morgen 03:30

📌 Wartend (kein Termin):
• organizer-improvements
• suche-feature
```

Empty state: `Keine ausstehenden Pläne.`

### `implement-plan: <slug> um HH:MM`
Sets `scheduled_time` for the given slug, git commit.  
Response: `⏰ habits-task-dialog geplant für 02:00`

### `implement-plan: <slug> jetzt`
Calls `_run_plan()` immediately in a thread.  
Response: `🚀 Implementierung gestartet: habits-task-dialog`

### `abort-plan: <slug>`
Hard-deletes entry from `scheduled_plans.json`, git commit.  
Response: `🗑 habits-task-dialog entfernt`

Unknown slug error: `❌ Kein Plan mit slug xyz gefunden`

`abort-plan:` only works on `pending` entries. If status is `running`: `⚠️ Plan läuft gerade — abbrechen nicht möglich`

## Implementation Runner

```python
def _run_plan(plan_path, slug=None):
    prompt = f"Follow the implementation plan exactly: {plan_path}\nCommit all changes when done."
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]

    if slug:
        _set_plan_status(slug, "running")

    result = subprocess.run(cmd, cwd=PROJECT_DIR, timeout=3600)

    if result.returncode != 0:
        result = subprocess.run(cmd, cwd=PROJECT_DIR, timeout=3600)  # one retry

    success = result.returncode == 0
    if slug:
        _set_plan_status(slug, "done" if success else "failed")

    if success:
        send_message(f"✅ Implementierung abgeschlossen: {slug or plan_path}")
    else:
        stderr_snippet = (result.stderr or "")[-500:]
        send_message(f"❌ Implementierung fehlgeschlagen: {slug or plan_path}\n{stderr_snippet}")
```

Timeout: 3600s (1h) per attempt. Two failures → `failed` status + Telegram notification.

`_plan_loop` runs in a daemon thread identical to `_reminder_loop`:

```python
def _plan_loop():
    while True:
        time.sleep(60)
        now = datetime.now().strftime("%H:%M")
        plans = _load_plans()
        for plan in plans:
            if plan["status"] == "pending" and plan.get("scheduled_time") == now:
                send_message(f"🚀 Starte Implementierung: {plan['slug']}")
                threading.Thread(target=_run_plan, args=(plan["plan_path"], plan["slug"]), daemon=True).start()
```

## Notifications

| Event | Message |
|---|---|
| Scheduled trigger fires | `🚀 Starte Implementierung: <slug>` |
| Success | `✅ Implementierung abgeschlossen: <slug>` |
| Failure (after retry) | `❌ Implementierung fehlgeschlagen: <slug>\n<stderr>` |

`on_stop.py` hook also fires on completion — complementary, no conflict.

## Files Changed

- `bot.py` — `_plan_loop`, `_run_plan`, `_load_plans`, `_set_plan_status`, handlers for `/plans`, `implement-plan:`, `abort-plan:`
- `scheduled_plans.json` — new file, initially `[]`
- `docs/superpowers/specs/2026-06-11-deferred-implementation-design.md` — this file

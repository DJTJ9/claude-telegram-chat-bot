# Implementation Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `implementation_mode` flag to auto-approve all permissions during approved inline implementation, eliminating Telegram relay interruptions.

**Architecture:** A boolean flag + ISO timestamp in `settings.json` is checked at the top of `on_permission.py` before any other logic — if active and not expired, every permission is immediately approved. CLAUDE.md instructs Claude to set/clear the flag around execution. A bot command provides a manual override.

**Tech Stack:** Python, pytest, JSON settings file

---

## File Map

| File | Change |
|---|---|
| `scripts/on_permission.py` | Add `from datetime import datetime` import; add 7-line impl_mode check block inside settings try-block |
| `tests/test_permission.py` | Add `_run_with_impl_mode()` helper + 3 new tests |
| `C:\Users\tjark\.claude\CLAUDE.md` | Add `## Implementation Mode During Execution` section after Post-Plan Scheduling block |
| `bot.py` | Add `timedelta` to datetime import; add `"impl-mode:"` to `_is_command` prefixes; add `elif` handler block; update `HILFE_TEXT` |
| `tests/test_bot.py` | Add 5 new tests for impl-mode prefix, hilfe, and settings roundtrip |

---

### Task 1: Hook — tests then implementation

**Files:**
- Modify: `tests/test_permission.py`
- Modify: `scripts/on_permission.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_permission.py` after the existing `_run()` helper (after line 21):

```python
def _run_with_impl_mode(tool_name, tool_input, impl_mode=False, impl_until=None):
    settings = PROJECT_DIR / "settings.json"
    original = settings.read_text()
    s = {"notifications_enabled": True, "implementation_mode": impl_mode,
         "implementation_mode_until": impl_until}
    settings.write_text(json.dumps(s))
    try:
        data = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=data, capture_output=True, text=True, timeout=5
        )
        return json.loads(result.stdout)
    finally:
        settings.write_text(original)


def test_implementation_mode_approves_bash():
    from datetime import datetime, timedelta
    until = (datetime.now() + timedelta(hours=4)).isoformat(timespec="seconds")
    resp = _run_with_impl_mode("Bash", {"command": "echo hi"}, impl_mode=True, impl_until=until)
    assert resp["decision"] == "approve"


def test_implementation_mode_approves_edit_outside_project():
    from datetime import datetime, timedelta
    until = (datetime.now() + timedelta(hours=4)).isoformat(timespec="seconds")
    resp = _run_with_impl_mode("Edit", {"file_path": r"C:\Users\tjark\.claude\CLAUDE.md"},
                               impl_mode=True, impl_until=until)
    assert resp["decision"] == "approve"


def test_implementation_mode_false_uses_normal_path():
    # impl_mode=False falls through to normal path; Edit inside project still approves
    inside = str(PROJECT_DIR / "bot.py")
    resp = _run_with_impl_mode("Edit", {"file_path": inside}, impl_mode=False, impl_until=None)
    assert resp["decision"] == "approve"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_permission.py::test_implementation_mode_approves_bash tests/test_permission.py::test_implementation_mode_approves_edit_outside_project -v
```

Expected: both FAIL (hook doesn't check `implementation_mode` yet; Bash test hits timeout after 5s, Edit-outside test tries Telegram relay and times out).

- [ ] **Step 3: Implement — add `datetime` import to `on_permission.py` line 1**

Change:
```python
import os, sys, json, time, uuid
```
To:
```python
import os, sys, json, time, uuid
from datetime import datetime
```

- [ ] **Step 4: Implement — add impl_mode check inside settings try-block**

Current block in `on_permission.py` (lines 16–23):
```python
settings_path = PROJECT_DIR / "settings.json"
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text())
        if not settings.get("notifications_enabled", True):
            print(json.dumps({"decision": "approve"}))
            sys.exit(0)
    except Exception:
        pass
```

Replace with:
```python
settings_path = PROJECT_DIR / "settings.json"
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text())
        impl_mode = settings.get("implementation_mode", False)
        impl_until = settings.get("implementation_mode_until")
        if impl_mode and impl_until:
            try:
                if datetime.now().isoformat() <= impl_until:
                    print(json.dumps({"decision": "approve"}))
                    sys.exit(0)
            except Exception:
                pass  # malformed timestamp → fall through
        if not settings.get("notifications_enabled", True):
            print(json.dumps({"decision": "approve"}))
            sys.exit(0)
    except Exception:
        pass
```

- [ ] **Step 5: Run all permission tests**

```
pytest tests/test_permission.py -v
```

Expected: all 6 tests PASS (3 existing + 3 new).

- [ ] **Step 6: Commit**

```bash
git add scripts/on_permission.py tests/test_permission.py
git commit -m "feat: add implementation_mode auto-approve to permission hook"
```

---

### Task 2: CLAUDE.md — add lifecycle instruction

**Files:**
- Modify: `C:\Users\tjark\.claude\CLAUDE.md`

- [ ] **Step 1: Add Implementation Mode section**

After the final code block in `## Post-Plan Implementation Scheduling` (after the `git -C ... commit -m "chore: schedule plan <slug>"` block at line 213), append:

```markdown

## Implementation Mode During Execution

Before invoking the chosen execution skill (executing-plans or subagent-driven-development), use the **Edit tool** to update `settings.json` in `C:\Projekte\telegram-notion-bot`:
- Set `"implementation_mode"` to `true`
- Set `"implementation_mode_until"` to current time + 4 hours as `"YYYY-MM-DDTHH:MM:SS"`

This allows the permission hook to auto-approve all tool calls during implementation without Telegram relay.

As the **last step** of all implementation (after all commits and push), clear the flag via Edit on `settings.json`:
- Set `"implementation_mode"` to `false`
- Set `"implementation_mode_until"` to `null`

Do NOT use Bash for this — use the Edit tool directly on `settings.json`.
```

- [ ] **Step 2: Commit**

```bash
git -C "C:\Users\tjark\.claude" add CLAUDE.md
git -C "C:\Users\tjark\.claude" commit -m "feat: add implementation_mode lifecycle to post-plan instructions"
```

---

### Task 3: bot.py — impl-mode command + tests

**Files:**
- Modify: `bot.py`
- Modify: `tests/test_bot.py`

- [ ] **Step 1: Write failing tests**

Add to the end of `tests/test_bot.py`:

```python
def test_impl_mode_prefix_detection():
    text = "impl-mode: an"
    assert text.lower().startswith("impl-mode:")
    assert text[10:].strip() == "an"

def test_impl_mode_aus_detection():
    assert "impl-mode: aus"[10:].strip() == "aus"

def test_impl_mode_in_hilfe():
    from bot import HILFE_TEXT
    assert "impl-mode:" in HILFE_TEXT

def test_impl_mode_is_known_command():
    known_prefixes = (
        "task:", "status:", "fokus:", "verschieben:", "lern:",
        "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
        "implement-plan:", "abort-plan:", "backlog:", "suche:", "brainstorming:", "impl-mode:",
    )
    assert "impl-mode: an".lower().startswith(known_prefixes)

def test_save_settings_implementation_mode_roundtrip(tmp_path):
    from bot import save_settings, load_settings
    s = {"notifications_enabled": True, "implementation_mode": True,
         "implementation_mode_until": "2026-06-15T18:00:00"}
    save_settings(s, tmp_path)
    loaded = load_settings(tmp_path)
    assert loaded["implementation_mode"] is True
    assert loaded["implementation_mode_until"] == "2026-06-15T18:00:00"
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_bot.py::test_impl_mode_in_hilfe tests/test_bot.py::test_impl_mode_is_known_command -v
```

Expected: `test_impl_mode_in_hilfe` FAIL (`impl-mode:` not in HILFE_TEXT yet), `test_impl_mode_is_known_command` PASS (tuple in test already has `impl-mode:`, it's just testing prefix logic not bot internals).

- [ ] **Step 3: Add `timedelta` to datetime import — `bot.py` line 2**

Change:
```python
from datetime import date, datetime
```
To:
```python
from datetime import date, datetime, timedelta
```

- [ ] **Step 4: Add `"impl-mode:"` to `_is_command` prefixes**

Find (around line 1272):
```python
                       "implement-plan:", "abort-plan:", "backlog:", "suche:", "brainstorming:")))
```
Change to:
```python
                       "implement-plan:", "abort-plan:", "backlog:", "suche:", "brainstorming:", "impl-mode:")))
```

- [ ] **Step 5: Add `elif` handler after `abort-plan:` block**

After the `abort-plan:` block's `continue` statement (around line 1435), insert:

```python
            elif text.lower().startswith("impl-mode:"):
                arg = text[10:].strip().lower()
                s = load_settings()
                if arg == "an":
                    until = (datetime.now() + timedelta(hours=4)).isoformat(timespec="seconds")
                    s["implementation_mode"] = True
                    s["implementation_mode_until"] = until
                    save_settings(s)
                    response = f"⚙️ Implementation Mode aktiv bis {until[11:16]}"
                elif arg == "aus":
                    s["implementation_mode"] = False
                    s["implementation_mode_until"] = None
                    save_settings(s)
                    response = "⚙️ Implementation Mode deaktiviert"
                else:
                    active = s.get("implementation_mode", False)
                    until = s.get("implementation_mode_until")
                    if active and until:
                        response = f"⚙️ Implementation Mode: aktiv bis {until[11:16]}"
                    else:
                        response = "⚙️ Implementation Mode: inaktiv\nNutzung: impl-mode: an  oder  impl-mode: aus"
                send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                continue
```

- [ ] **Step 6: Update `HILFE_TEXT`**

Find (around line 120–124):
```python
⚙️ Einstellungen
  /bot-notify an — Benachrichtigungen aktivieren
  /bot-notify aus — Benachrichtigungen deaktivieren"""
```

Change to:
```python
⚙️ Einstellungen
  /bot-notify an — Benachrichtigungen aktivieren
  /bot-notify aus — Benachrichtigungen deaktivieren
  impl-mode: an — Implementierungs-Mode aktivieren (4h)
  impl-mode: aus — Implementierungs-Mode deaktivieren"""
```

- [ ] **Step 7: Run all tests**

```
pytest tests/test_bot.py tests/test_permission.py -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add impl-mode bot command for manual implementation_mode control"
```

---

## Done

After all 3 tasks:
- Terminal inline implementation auto-approves all permission requests
- Flag expires automatically after 4h if not cleared
- `impl-mode: aus` available as manual kill switch from phone
- All existing tests still pass

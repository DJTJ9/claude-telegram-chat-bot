# Deferred Implementation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow brainstorming sessions to schedule their implementation plan for headless execution later (e.g., nightly), triggered by the existing Telegram bot.

**Architecture:** New `scheduled_plans.json` mirrors `reminders.json` pattern. A `_plan_loop` daemon thread checks every 60s and fires `_run_plan()` when the scheduled time is reached. Three new bot commands (`/plans`, `implement-plan:`, `abort-plan:`) let the user manage the queue via Telegram. CLAUDE.md gains a post-plan scheduling section that runs at the end of every brainstorming session.

**Tech Stack:** Python 3, existing `bot.py`, `subprocess`, `threading`, `json`, `pathlib`; `pytest` for tests.

---

### Task 1: Add `PLANS_PATH` constant and data helpers to `bot.py`

**Files:**
- Modify: `bot.py:13` (constants block, after `REMINDERS_PATH`)
- Create: `tests/test_plans.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_plans.py`:

```python
import sys, os, json, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pathlib import Path
from unittest.mock import patch

def test_load_plans_missing_file(tmp_path):
    with patch("bot.PLANS_PATH", tmp_path / "scheduled_plans.json"):
        from bot import _load_plans
        assert _load_plans() == []

def test_load_plans_existing(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([{"slug": "test", "plan_path": "docs/test.md", "scheduled_time": "02:00", "status": "pending"}]))
    with patch("bot.PLANS_PATH", p):
        from bot import _load_plans
        result = _load_plans()
        assert len(result) == 1
        assert result[0]["slug"] == "test"

def test_save_and_reload_plans(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text("[]")
    plans = [{"slug": "x", "plan_path": "docs/x.md", "scheduled_time": None, "status": "pending"}]
    with patch("bot.PLANS_PATH", p):
        from bot import _save_plans, _load_plans
        _save_plans(plans)
        assert _load_plans() == plans

def test_set_plan_status(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "alpha", "plan_path": "docs/alpha.md", "scheduled_time": "02:00", "status": "pending"}
    ]))
    with patch("bot.PLANS_PATH", p), patch("subprocess.run"):
        from bot import _set_plan_status, _load_plans
        _set_plan_status("alpha", "running")
        result = _load_plans()
        assert result[0]["status"] == "running"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Projekte\telegram-notion-bot
pytest tests/test_plans.py -v
```
Expected: `ImportError` or `AttributeError` — `_load_plans` not defined yet.

- [ ] **Step 3: Add `PLANS_PATH` constant to `bot.py`**

After line 13 (`REMINDERS_PATH = Path(WORK_DIR) / "reminders.json"`), add:

```python
PLANS_PATH = Path(WORK_DIR) / "scheduled_plans.json"
```

- [ ] **Step 4: Add helper functions to `bot.py`**

After the `save_reminders` function (around line 468), add:

```python
def _load_plans():
    if PLANS_PATH.exists():
        try:
            return json.loads(PLANS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []

def _save_plans(plans):
    PLANS_PATH.write_text(json.dumps(plans, indent=2, ensure_ascii=False), encoding="utf-8")

def _set_plan_status(slug, status):
    plans = _load_plans()
    for p in plans:
        if p["slug"] == slug:
            p["status"] = status
            break
    _save_plans(plans)
    subprocess.run(["git", "-C", WORK_DIR, "add", "scheduled_plans.json"], capture_output=True)
    subprocess.run(["git", "-C", WORK_DIR, "commit", "-m", f"chore: plan {slug} -> {status}"], capture_output=True)
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_plans.py -v
```
Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_plans.py
git commit -m "feat: add PLANS_PATH and plan data helpers"
```

---

### Task 2: Create `scheduled_plans.json`

**Files:**
- Create: `scheduled_plans.json`

- [ ] **Step 1: Create the file**

Write `scheduled_plans.json` at project root with content `[]`.

- [ ] **Step 2: Commit**

```bash
git add scheduled_plans.json
git commit -m "chore: add empty scheduled_plans.json"
```

---

### Task 3: Add `_run_plan()` to `bot.py`

**Files:**
- Modify: `bot.py` (add after `_set_plan_status`)
- Modify: `tests/test_plans.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_plans.py`:

```python
def test_run_plan_success(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "alpha", "plan_path": "docs/alpha.md", "scheduled_time": "02:00", "status": "pending"}
    ]))
    sent = []
    with patch("bot.PLANS_PATH", p), \
         patch("subprocess.run") as mock_run, \
         patch("bot.send_message", lambda chat_id, text, **kw: sent.append(text)):
        mock_run.return_value = type("R", (), {"returncode": 0, "stderr": ""})()
        from bot import _run_plan
        _run_plan("docs/alpha.md", slug="alpha")
    assert any("abgeschlossen" in m for m in sent)

def test_run_plan_failure_retries(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "beta", "plan_path": "docs/beta.md", "scheduled_time": "02:00", "status": "pending"}
    ]))
    sent = []
    call_count = {"n": 0}
    def mock_run(cmd, **kw):
        if isinstance(cmd, list) and cmd and cmd[0] == "claude":
            call_count["n"] += 1
            return type("R", (), {"returncode": 1, "stderr": "error msg"})()
        return type("R", (), {"returncode": 0, "stderr": ""})()
    with patch("bot.PLANS_PATH", p), \
         patch("subprocess.run", mock_run), \
         patch("bot.send_message", lambda chat_id, text, **kw: sent.append(text)):
        from bot import _run_plan
        _run_plan("docs/beta.md", slug="beta")
    assert call_count["n"] == 2
    assert any("fehlgeschlagen" in m for m in sent)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_plans.py::test_run_plan_success tests/test_plans.py::test_run_plan_failure_retries -v
```
Expected: `AttributeError: module 'bot' has no attribute '_run_plan'`

- [ ] **Step 3: Add `_run_plan()` to `bot.py`**

After `_set_plan_status`, add:

```python
def _run_plan(plan_path, slug=None):
    prompt = (
        f"Follow the implementation plan exactly. "
        f"Plan file: {plan_path}\n"
        f"Read the plan file and implement every task step by step. Commit all changes when done."
    )
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    if slug:
        _set_plan_status(slug, "running")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            timeout=3600, cwd=WORK_DIR)
    if result.returncode != 0:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                timeout=3600, cwd=WORK_DIR)
    success = result.returncode == 0
    if slug:
        _set_plan_status(slug, "done" if success else "failed")
    label = slug or plan_path
    if success:
        send_message(MY_CHAT_ID, f"✅ Implementierung abgeschlossen: {label}")
    else:
        stderr_snippet = (result.stderr or "")[-500:]
        send_message(MY_CHAT_ID, f"❌ Implementierung fehlgeschlagen: {label}\n{stderr_snippet}")
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_plans.py::test_run_plan_success tests/test_plans.py::test_run_plan_failure_retries -v
```
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_plans.py
git commit -m "feat: add _run_plan with retry and Telegram notification"
```

---

### Task 4: Add `_plan_loop()` and start thread

**Files:**
- Modify: `bot.py` (add `_plan_loop` after `_run_plan`, update `__main__`)
- Modify: `tests/test_plans.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_plans.py`:

```python
def test_plan_loop_fires_on_matching_time(tmp_path):
    import bot
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "gamma", "plan_path": "docs/gamma.md", "scheduled_time": "03:00", "status": "pending"}
    ]))
    triggered = []
    with patch("bot.PLANS_PATH", p), \
         patch("bot.send_message"), \
         patch("bot._run_plan", lambda path, slug: triggered.append(slug)):
        plans = bot._load_plans()
        now = "03:00"
        for plan in plans:
            if plan["status"] == "pending" and plan.get("scheduled_time") == now:
                bot._run_plan(plan["plan_path"], slug=plan["slug"])
    assert "gamma" in triggered
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_plans.py::test_plan_loop_fires_on_matching_time -v
```
Expected: FAIL — `_run_plan` not patched yet / `_load_plans` missing.

- [ ] **Step 3: Add `_plan_loop()` to `bot.py`**

After `_run_plan`, add:

```python
def _plan_loop():
    while True:
        time.sleep(60)
        try:
            now = datetime.now().strftime("%H:%M")
            plans = _load_plans()
            for plan in plans:
                if plan["status"] == "pending" and plan.get("scheduled_time") == now:
                    send_message(MY_CHAT_ID, f"🚀 Starte Implementierung: {plan['slug']}")
                    threading.Thread(
                        target=_run_plan,
                        args=(plan["plan_path"], plan["slug"]),
                        daemon=True
                    ).start()
        except Exception as e:
            print(f"plan loop error: {e}")
```

- [ ] **Step 4: Start thread and reset stale "running" plans in `__main__`**

Find `if __name__ == "__main__":`. After the `_reminder_loop` thread start line, add:

```python
    threading.Thread(target=_plan_loop, daemon=True).start()
    _stale = _load_plans()
    for _p in _stale:
        if _p["status"] == "running":
            _p["status"] = "pending"
    _save_plans(_stale)
```

- [ ] **Step 5: Run test to verify it passes**

```
pytest tests/test_plans.py::test_plan_loop_fires_on_matching_time -v
```
Expected: PASS.

- [ ] **Step 6: Run full test suite**

```
pytest tests/ -v
```
Expected: all existing tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add bot.py tests/test_plans.py
git commit -m "feat: add _plan_loop daemon thread and stale-run recovery"
```

---

### Task 5: Add `/plans` command handler

**Files:**
- Modify: `bot.py` (add `_format_plans` helper + handler before `/bot-notify` block)
- Modify: `tests/test_plans.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_plans.py`:

```python
def test_format_plans_scheduled_and_waiting(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "alpha", "plan_path": "docs/alpha.md", "scheduled_time": "02:00", "status": "pending"},
        {"slug": "beta",  "plan_path": "docs/beta.md",  "scheduled_time": None,    "status": "pending"},
    ]))
    with patch("bot.PLANS_PATH", p):
        from bot import _format_plans
        output = _format_plans()
    assert "⏰" in output
    assert "alpha" in output
    assert "📌" in output
    assert "beta" in output

def test_format_plans_empty(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text("[]")
    with patch("bot.PLANS_PATH", p):
        from bot import _format_plans
        output = _format_plans()
    assert "keine" in output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_plans.py::test_format_plans_scheduled_and_waiting tests/test_plans.py::test_format_plans_empty -v
```
Expected: `AttributeError: module 'bot' has no attribute '_format_plans'`

- [ ] **Step 3: Add `_format_plans()` to `bot.py`**

After `_plan_loop`, add:

```python
def _format_plans():
    plans = [p for p in _load_plans() if p["status"] in ("pending", "running")]
    if not plans:
        return "Keine ausstehenden Pläne."
    scheduled = [p for p in plans if p.get("scheduled_time")]
    waiting   = [p for p in plans if not p.get("scheduled_time")]
    lines = ["📋 Geplante Implementierungen"]
    if scheduled:
        lines.append("\n⏰ Geplant:")
        for p in scheduled:
            lines.append(f"• {p['slug']} — {p['scheduled_time']}")
    if waiting:
        lines.append("\n📌 Wartend (kein Termin):")
        for p in waiting:
            lines.append(f"• {p['slug']}")
    return "\n".join(lines)
```

- [ ] **Step 4: Add `/plans` handler in message loop**

In the main `while True:` loop, before the `/bot-notify` handler block, add:

```python
            if text.lower() == "/plans":
                send_message(chat_id, _format_plans(), reply_markup=REPLY_KEYBOARD)
                continue
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_plans.py::test_format_plans_scheduled_and_waiting tests/test_plans.py::test_format_plans_empty -v
```
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_plans.py
git commit -m "feat: add /plans command and _format_plans helper"
```

---

### Task 6: Add `implement-plan:` command handler

**Files:**
- Modify: `bot.py` (add `_schedule_plan` helper + `elif` branch in message handler)
- Modify: `tests/test_plans.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_plans.py`:

```python
def test_schedule_plan_sets_time(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "alpha", "plan_path": "docs/alpha.md", "scheduled_time": None, "status": "pending"}
    ]))
    with patch("bot.PLANS_PATH", p), patch("subprocess.run"):
        from bot import _schedule_plan
        result = _schedule_plan("alpha", "02:00")
    assert "02:00" in result
    plans = json.loads(p.read_text())
    assert plans[0]["scheduled_time"] == "02:00"

def test_schedule_plan_unknown_slug(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text("[]")
    with patch("bot.PLANS_PATH", p):
        from bot import _schedule_plan
        result = _schedule_plan("unknown", "02:00")
    assert "gefunden" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_plans.py::test_schedule_plan_sets_time tests/test_plans.py::test_schedule_plan_unknown_slug -v
```
Expected: `AttributeError: module 'bot' has no attribute '_schedule_plan'`

- [ ] **Step 3: Add `_schedule_plan()` to `bot.py`**

After `_format_plans`, add:

```python
def _schedule_plan(slug, scheduled_time):
    plans = _load_plans()
    for plan in plans:
        if plan["slug"] == slug:
            plan["scheduled_time"] = scheduled_time
            _save_plans(plans)
            subprocess.run(["git", "-C", WORK_DIR, "add", "scheduled_plans.json"], capture_output=True)
            subprocess.run(["git", "-C", WORK_DIR, "commit", "-m", f"chore: schedule plan {slug} at {scheduled_time}"], capture_output=True)
            return f"⏰ {slug} geplant für {scheduled_time}"
    return f"❌ Kein Plan mit slug '{slug}' gefunden"
```

- [ ] **Step 4: Add `implement-plan:` handler in message loop**

In the `elif` chain (after the `termin:` block, before `hilfe`), add:

```python
            elif text.lower().startswith("implement-plan:"):
                body = text[15:].strip()
                if not body:
                    response = "Nutzung: implement-plan: <slug> um HH:MM  oder  implement-plan: <slug> jetzt"
                else:
                    slug_part, _, rest = body.partition(" ")
                    rest = rest.strip()
                    if rest.lower() == "jetzt":
                        plan_entry = next((p for p in _load_plans() if p["slug"] == slug_part), None)
                        if not plan_entry:
                            response = f"❌ Kein Plan mit slug '{slug_part}' gefunden"
                            send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                        else:
                            send_message(chat_id, f"🚀 Implementierung gestartet: {slug_part}")
                            threading.Thread(
                                target=_run_plan,
                                args=(plan_entry["plan_path"], slug_part),
                                daemon=True
                            ).start()
                        continue
                    elif rest.lower().startswith("um "):
                        scheduled_time = rest[3:].strip()
                        response = _schedule_plan(slug_part, scheduled_time)
                    else:
                        response = "Nutzung: implement-plan: <slug> um HH:MM  oder  implement-plan: <slug> jetzt"
                send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                continue
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_plans.py::test_schedule_plan_sets_time tests/test_plans.py::test_schedule_plan_unknown_slug -v
```
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_plans.py
git commit -m "feat: add implement-plan: command handler"
```

---

### Task 7: Add `abort-plan:` command handler

**Files:**
- Modify: `bot.py` (add `_abort_plan` helper + `elif` branch)
- Modify: `tests/test_plans.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_plans.py`:

```python
def test_abort_plan_removes_entry(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "alpha", "plan_path": "docs/alpha.md", "scheduled_time": "02:00", "status": "pending"}
    ]))
    with patch("bot.PLANS_PATH", p), patch("subprocess.run"):
        from bot import _abort_plan
        result = _abort_plan("alpha")
    assert "entfernt" in result
    plans = json.loads(p.read_text())
    assert plans == []

def test_abort_plan_blocked_when_running(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "beta", "plan_path": "docs/beta.md", "scheduled_time": "02:00", "status": "running"}
    ]))
    with patch("bot.PLANS_PATH", p):
        from bot import _abort_plan
        result = _abort_plan("beta")
    assert "läuft" in result
    plans = json.loads(p.read_text())
    assert len(plans) == 1

def test_abort_plan_unknown_slug(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text("[]")
    with patch("bot.PLANS_PATH", p):
        from bot import _abort_plan
        result = _abort_plan("unknown")
    assert "gefunden" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_plans.py::test_abort_plan_removes_entry tests/test_plans.py::test_abort_plan_blocked_when_running tests/test_plans.py::test_abort_plan_unknown_slug -v
```
Expected: `AttributeError: module 'bot' has no attribute '_abort_plan'`

- [ ] **Step 3: Add `_abort_plan()` to `bot.py`**

After `_schedule_plan`, add:

```python
def _abort_plan(slug):
    plans = _load_plans()
    for plan in plans:
        if plan["slug"] == slug:
            if plan["status"] == "running":
                return f"⚠️ Plan läuft gerade — abbrechen nicht möglich"
            plans = [p for p in plans if p["slug"] != slug]
            _save_plans(plans)
            subprocess.run(["git", "-C", WORK_DIR, "add", "scheduled_plans.json"], capture_output=True)
            subprocess.run(["git", "-C", WORK_DIR, "commit", "-m", f"chore: remove plan {slug}"], capture_output=True)
            return f"🗑 {slug} entfernt"
    return f"❌ Kein Plan mit slug '{slug}' gefunden"
```

- [ ] **Step 4: Add `abort-plan:` handler in message loop**

After the `implement-plan:` block, add:

```python
            elif text.lower().startswith("abort-plan:"):
                slug_part = text[11:].strip()
                if not slug_part:
                    response = "Nutzung: abort-plan: <slug>"
                else:
                    response = _abort_plan(slug_part)
                send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                continue
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_plans.py::test_abort_plan_removes_entry tests/test_plans.py::test_abort_plan_blocked_when_running tests/test_plans.py::test_abort_plan_unknown_slug -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_plans.py
git commit -m "feat: add abort-plan: command handler"
```

---

### Task 8: Update `HILFE_TEXT` and `_is_command` guard

**Files:**
- Modify: `bot.py:60-102` (HILFE_TEXT)
- Modify: `bot.py` (`_is_command` tuple in `pending_task_input` block)
- Modify: `tests/test_plans.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_plans.py`:

```python
def test_hilfe_contains_plan_commands():
    from bot import HILFE_TEXT
    assert "/plans" in HILFE_TEXT
    assert "implement-plan:" in HILFE_TEXT
    assert "abort-plan:" in HILFE_TEXT
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_plans.py::test_hilfe_contains_plan_commands -v
```
Expected: FAIL.

- [ ] **Step 3: Update `HILFE_TEXT`**

Find the `⚙️ Einstellungen` section at the end of HILFE_TEXT. Insert this section before it:

```
🤖 Pläne
  /plans — geplante Implementierungen anzeigen
  implement-plan: <slug> um HH:MM — Implementierung planen
  implement-plan: <slug> jetzt — sofort implementieren
  abort-plan: <slug> — Implementierung entfernen
```

- [ ] **Step 4: Update `_is_command` guard**

Find:
```python
                _is_command = (text.lower() in ("restart", "projekte", "moin", "abend", "woche", "hilfe", "erinnerungen")
                               or any(text.lower().startswith(p) for p in
                                      ("task:", "status:", "fokus:", "verschieben:", "lern:",
                                       "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:")))
```

Replace with:
```python
                _is_command = (text.lower() in ("restart", "projekte", "moin", "abend", "woche", "hilfe", "erinnerungen", "/plans")
                               or any(text.lower().startswith(p) for p in
                                      ("task:", "status:", "fokus:", "verschieben:", "lern:",
                                       "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
                                       "implement-plan:", "abort-plan:")))
```

- [ ] **Step 5: Run test and full suite**

```
pytest tests/ -v
```
Expected: all tests PASS including `test_hilfe_contains_plan_commands`.

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_plans.py
git commit -m "feat: update HILFE_TEXT and _is_command guard for plan commands"
```

---

### Task 9: Update `CLAUDE.md` with post-plan scheduling instructions

**Files:**
- Modify: `C:\Users\tjark\.claude\CLAUDE.md`

- [ ] **Step 1: Add the section**

Open `C:\Users\tjark\.claude\CLAUDE.md`. After the "Brainstorming via Telegram Relay" section, add:

```markdown
## Post-Plan Implementation Scheduling

At the end of any brainstorming session, AFTER the implementation plan file is written and committed, ask two questions using the same relay as above (Telegram if `notifications_enabled: true`, else terminal).

**Question 1:** "Wann implementieren? (`jetzt` / `HH:MM` / `später`)"

- **`jetzt`**: Compute current time + 1 minute as `HH:MM`. Write an entry to `C:\Projekte\telegram-notion-bot\scheduled_plans.json` (append to existing array) with `scheduled_time` = that value and `status: "pending"`. Then:
  ```bash
  git -C "C:\Projekte\telegram-notion-bot" add scheduled_plans.json
  git -C "C:\Projekte\telegram-notion-bot" commit -m "chore: schedule plan <slug> at <time>"
  ```
  Skip Question 2.
- **`HH:MM`** or **`später`**: Proceed to Question 2.

**Question 2:** "Slug für diesen Plan? (Standard: `<derived-slug>`)"

Derive slug from the plan filename: strip date prefix (`YYYY-MM-DD-`) and `.md` suffix.
Example: `2026-06-12-habits-task-dialog.md` → `habits-task-dialog`

After confirmation, append to `C:\Projekte\telegram-notion-bot\scheduled_plans.json`:
```json
{
  "slug": "<slug>",
  "plan_path": "<path relative to WORK_DIR, e.g. docs/superpowers/plans/2026-06-12-habits-task-dialog.md>",
  "scheduled_time": "<HH:MM or null if 'später'>",
  "status": "pending"
}
```

Then:
```bash
git -C "C:\Projekte\telegram-notion-bot" add scheduled_plans.json
git -C "C:\Projekte\telegram-notion-bot" commit -m "chore: schedule plan <slug>"
```
```

- [ ] **Step 2: Verify the section is present**

Read `C:\Users\tjark\.claude\CLAUDE.md` and confirm "Post-Plan Implementation Scheduling" heading exists with correct content.

- [ ] **Step 3: Commit to CLAUDE.md's repo**

```bash
git -C "C:\Users\tjark\.claude" add CLAUDE.md
git -C "C:\Users\tjark\.claude" commit -m "docs: add post-plan scheduling instructions"
```

---

## Final Verification

- [ ] Run `pytest tests/ -v` — all tests pass
- [ ] Send `/plans` to bot — responds "Keine ausstehenden Pläne."
- [ ] Manually add entry to `scheduled_plans.json` with `scheduled_time` = current time + 2 min — confirm `🚀 Starte Implementierung:` arrives within 60s
- [ ] `implement-plan: test um 03:00` → verify JSON updated, confirmation message received
- [ ] `abort-plan: test` → verify entry removed, confirmation received

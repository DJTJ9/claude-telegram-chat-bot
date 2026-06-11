# Bot Notify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/bot-notify` toggle command + Claude Code hooks for task-completion notifications and interactive Bash permission requests via Telegram.

**Architecture:** File-based IPC between Claude Code hook scripts and the running Telegram bot. Hook scripts write/poll JSON files in the project root; the bot's main loop checks for pending permission requests and handles inline-keyboard callbacks.

**Tech Stack:** Python 3, `requests`, `pathlib`, `uuid`, Telegram Bot API inline keyboards, Claude Code global hooks

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `bot.py` | Modify | Settings helpers, `/bot-notify` handler, callback handler, poll-loop check, `get_updates` timeout param |
| `scripts/on_stop.py` | Create | Stop hook — sends "task done" notification |
| `scripts/on_permission.py` | Create | PreToolUse hook — IPC handshake for Bash permission |
| `C:\Users\tjark\.claude\settings.json` | Modify | Register hooks globally for all Claude Code sessions |
| `tests/test_bot.py` | Modify | Tests for new helpers |

---

## Task 1: Add imports and settings helpers to bot.py

**Files:**
- Modify: `bot.py:1` (imports)
- Modify: `bot.py` (add helpers after `pending_task_input = {}`)
- Modify: `tests/test_bot.py` (add tests)

- [ ] **Step 1: Add failing tests**

Add to `tests/test_bot.py`:

```python
import json
from pathlib import Path
from bot import load_settings, save_settings

def test_load_settings_default(tmp_path):
    assert load_settings(tmp_path) == {"notifications_enabled": True}

def test_load_settings_reads_file(tmp_path):
    (tmp_path / "settings.json").write_text('{"notifications_enabled": false}')
    assert load_settings(tmp_path) == {"notifications_enabled": False}

def test_save_settings(tmp_path):
    save_settings({"notifications_enabled": False}, tmp_path)
    data = json.loads((tmp_path / "settings.json").read_text())
    assert data == {"notifications_enabled": False}

def test_save_load_roundtrip(tmp_path):
    save_settings({"notifications_enabled": True}, tmp_path)
    assert load_settings(tmp_path) == {"notifications_enabled": True}
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_bot.py::test_load_settings_default -v
```

Expected: `ImportError` or `AttributeError` — `load_settings` not defined yet.

- [ ] **Step 3: Add imports to bot.py**

Change line 1 of `bot.py` from:
```python
import os, re, subprocess, requests, tempfile, sys
from datetime import date
from groq import Groq
```
to:
```python
import os, re, subprocess, requests, tempfile, sys, json, uuid
from datetime import date
from pathlib import Path
from groq import Groq
```

- [ ] **Step 4: Add settings helpers to bot.py**

After the line `pending_task_input = {}` (currently around line 351), add:

```python
def load_settings(_dir=WORK_DIR):
    p = Path(_dir) / "settings.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"notifications_enabled": True}

def save_settings(s, _dir=WORK_DIR):
    (Path(_dir) / "settings.json").write_text(json.dumps(s, indent=2))
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_bot.py::test_load_settings_default tests/test_bot.py::test_load_settings_reads_file tests/test_bot.py::test_save_settings tests/test_bot.py::test_save_load_roundtrip -v
```

Expected: 4 PASSED.

- [ ] **Step 6: Run full test suite to check for regressions**

```
pytest tests/ -v
```

Expected: all PASSED.

- [ ] **Step 7: Commit**

```
git add bot.py tests/test_bot.py
git commit -m "feat: add settings helpers to bot.py"
```

---

## Task 2: Modify get_updates to accept timeout parameter

**Files:**
- Modify: `bot.py` (`get_updates` function, currently around line 304)

- [ ] **Step 1: Update `get_updates` signature**

Find:
```python
def get_updates(offset=None):
    params = {"timeout": 30, "offset": offset}
    r = requests.get(f"{BASE}/getUpdates", params=params, timeout=35)
    return r.json().get("result", [])
```

Replace with:
```python
def get_updates(offset=None, timeout=30):
    params = {"timeout": timeout, "offset": offset}
    r = requests.get(f"{BASE}/getUpdates", params=params, timeout=timeout + 5)
    return r.json().get("result", [])
```

- [ ] **Step 2: Run full test suite**

```
pytest tests/ -v
```

Expected: all PASSED (no callers change, default stays 30s).

- [ ] **Step 3: Commit**

```
git add bot.py
git commit -m "feat: add timeout param to get_updates"
```

---

## Task 3: Add /bot-notify command handler to bot.py

**Files:**
- Modify: `bot.py` (main loop command routing, around line 407)
- Modify: `bot.py` (`HILFE_TEXT` constant)
- Modify: `tests/test_bot.py`

- [ ] **Step 1: Add failing test**

Add to `tests/test_bot.py`:

```python
def test_bot_notify_in_hilfe():
    from bot import HILFE_TEXT
    assert "/bot-notify" in HILFE_TEXT
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_bot.py::test_bot_notify_in_hilfe -v
```

Expected: FAIL — `/bot-notify` not in HILFE_TEXT yet.

- [ ] **Step 3: Add /bot-notify to HILFE_TEXT**

Find the closing `"""` of `HILFE_TEXT` in `bot.py`. Add before it:

```
\n⚙️ Einstellungen
  /bot-notify an — Benachrichtigungen aktivieren
  /bot-notify aus — Benachrichtigungen deaktivieren
```

- [ ] **Step 4: Add /bot-notify handler in the main loop**

In the main loop, find `if text.lower() == "restart":` (around line 407). Add the `/bot-notify` handler BEFORE that block:

```python
            if text.lower().startswith("/bot-notify"):
                arg = text[11:].strip().lower()
                s = load_settings()
                if arg == "an":
                    s["notifications_enabled"] = True
                    save_settings(s)
                    response = "🔔 Benachrichtigungen aktiviert"
                elif arg == "aus":
                    s["notifications_enabled"] = False
                    save_settings(s)
                    response = "🔕 Benachrichtigungen deaktiviert"
                else:
                    state = "aktiviert 🔔" if s.get("notifications_enabled", True) else "deaktiviert 🔕"
                    response = f"Benachrichtigungen: {state}\nNutzung: /bot-notify an  oder  /bot-notify aus"
                send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                continue
```

- [ ] **Step 5: Run tests**

```
pytest tests/ -v
```

Expected: all PASSED.

- [ ] **Step 6: Commit**

```
git add bot.py tests/test_bot.py
git commit -m "feat: add /bot-notify toggle command"
```

---

## Task 4: Add callback query handler and poll-loop permission check to bot.py

**Files:**
- Modify: `bot.py` (module-level state + main loop)

- [ ] **Step 1: Add module-level tracking variable**

After `pending_task_input = {}`, add:

```python
_active_permission_id = None
```

- [ ] **Step 2: Replace the while-loop opening in bot.py**

Find this block (starts around line 377):

```python
    while True:
        try:
            updates = get_updates(offset)
        except requests.exceptions.ReadTimeout:
            continue
        except Exception as e:
            print(f"Polling-Fehler: {e}")
            continue
        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")

            if chat_id != MY_CHAT_ID:
                continue
```

Replace with:

```python
    while True:
        global _active_permission_id

        # Check for pending permission request from Claude Code hook
        pending_path = Path(WORK_DIR) / "pending_permission.json"
        if pending_path.exists():
            try:
                req = json.loads(pending_path.read_text())
                tool_input = req.get("input", {})
                cmd = str(tool_input.get("command", tool_input))[:200]
                msg_text = f"🔐 Permission needed:\nTool: {req['tool']}\n$ {cmd}"
                inline_kb = {"inline_keyboard": [[
                    {"text": "Ja ✅", "callback_data": f"approve_{req['request_id']}"},
                    {"text": "Nein ❌", "callback_data": f"deny_{req['request_id']}"},
                ]]}
                send_message(MY_CHAT_ID, msg_text, reply_markup=inline_kb)
                _active_permission_id = req["request_id"]
                pending_path.unlink()
            except Exception as e:
                print(f"permission check error: {e}")

        poll_timeout = 5 if _active_permission_id else 30
        try:
            updates = get_updates(offset, timeout=poll_timeout)
        except requests.exceptions.ReadTimeout:
            continue
        except Exception as e:
            print(f"Polling-Fehler: {e}")
            continue
        for update in updates:
            offset = update["update_id"] + 1

            # Handle inline keyboard callbacks (permission approve/deny)
            cb = update.get("callback_query")
            if cb:
                cb_data = cb.get("data", "")
                if cb_data.startswith("approve_") or cb_data.startswith("deny_"):
                    request_id = cb_data.split("_", 1)[1]
                    approved = cb_data.startswith("approve_")
                    resp_path = Path(WORK_DIR) / f"permission_response_{request_id}.json"
                    resp_path.write_text(json.dumps({"approved": approved, "request_id": request_id}))
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    action = "genehmigt ✅" if approved else "abgelehnt ❌"
                    send_message(MY_CHAT_ID, f"Permission {action}")
                    if _active_permission_id == request_id:
                        _active_permission_id = None
                continue  # Don't process callback_query as a message

            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")

            if chat_id != MY_CHAT_ID:
                continue
```

- [ ] **Step 3: Run full test suite**

```
pytest tests/ -v
```

Expected: all PASSED.

- [ ] **Step 4: Commit**

```
git add bot.py
git commit -m "feat: add permission check loop and callback query handler"
```

---

## Task 5: Create scripts/on_stop.py

**Files:**
- Create: `scripts/on_stop.py`

- [ ] **Step 1: Create scripts/ directory if needed**

```
mkdir scripts
```

- [ ] **Step 2: Create `scripts/on_stop.py`**

```python
import os, sys, json, requests
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

# Load .env manually
env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

TOKEN = os.environ.get("TELEGRAM_TOKEN")
MY_CHAT_ID = 8896609541

if not TOKEN:
    sys.exit(0)

settings_path = PROJECT_DIR / "settings.json"
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text())
        if not settings.get("notifications_enabled", True):
            sys.exit(0)
    except Exception:
        pass

try:
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": MY_CHAT_ID, "text": "✅ Claude Code Task abgeschlossen"},
        timeout=10,
    )
except Exception:
    pass
```

- [ ] **Step 3: Manual test — send notification**

Ensure the bot is running, then:

```
python scripts/on_stop.py
```

Expected: Telegram message "✅ Claude Code Task abgeschlossen" received on phone within a few seconds.

- [ ] **Step 4: Test with notifications disabled**

```
python -c "from pathlib import Path; Path('settings.json').write_text('{\"notifications_enabled\": false}')"
python scripts/on_stop.py
```

Expected: No Telegram message. Then re-enable:

```
python -c "from pathlib import Path; Path('settings.json').write_text('{\"notifications_enabled\": true}')"
```

- [ ] **Step 5: Commit**

```
git add scripts/on_stop.py
git commit -m "feat: add on_stop.py Claude Code Stop hook"
```

---

## Task 6: Create scripts/on_permission.py

**Files:**
- Create: `scripts/on_permission.py`

- [ ] **Step 1: Create `scripts/on_permission.py`**

```python
import os, sys, json, time, uuid
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

# Load .env manually
env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

settings_path = PROJECT_DIR / "settings.json"
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text())
        if not settings.get("notifications_enabled", True):
            print(json.dumps({"decision": "approve"}))
            sys.exit(0)
    except Exception:
        pass

try:
    data = json.loads(sys.stdin.read())
except Exception:
    print(json.dumps({"decision": "approve"}))
    sys.exit(0)

request_id = str(uuid.uuid4())[:8]
tool_name = data.get("tool_name", "Unknown")
tool_input = data.get("tool_input", {})

pending_path = PROJECT_DIR / "pending_permission.json"
pending_path.write_text(json.dumps({
    "tool": tool_name,
    "input": tool_input,
    "request_id": request_id,
}))

response_path = PROJECT_DIR / f"permission_response_{request_id}.json"
timeout = 300
start = time.time()

while time.time() - start < timeout:
    if response_path.exists():
        try:
            resp = json.loads(response_path.read_text())
            response_path.unlink()
        except Exception:
            time.sleep(0.1)
            continue
        if resp.get("approved"):
            print(json.dumps({"decision": "approve"}))
            sys.exit(0)
        else:
            print(json.dumps({"decision": "block", "reason": "Denied via Telegram"}))
            sys.exit(2)
    time.sleep(0.5)

# Timeout — auto-approve, clean up
pending_path.unlink(missing_ok=True)
print(json.dumps({"decision": "approve"}))
sys.exit(0)
```

- [ ] **Step 2: Manual test — approve flow**

Ensure bot is running, then in a separate terminal:

```
echo '{"tool_name": "Bash", "tool_input": {"command": "echo hello"}}' | python scripts/on_permission.py
```

Expected:
- Telegram message: `🔐 Permission needed: Tool: Bash $ echo hello` with [Ja ✅] [Nein ❌]
- Tap "Ja ✅" → script prints `{"decision": "approve"}`, exits 0
- Telegram confirmation: "Permission genehmigt ✅"

- [ ] **Step 3: Manual test — deny flow**

```
echo '{"tool_name": "Bash", "tool_input": {"command": "rm -rf /tmp/test"}}' | python scripts/on_permission.py
```

Tap "Nein ❌" → script prints `{"decision": "block", "reason": "Denied via Telegram"}`, exits 2.

- [ ] **Step 4: Commit**

```
git add scripts/on_permission.py
git commit -m "feat: add on_permission.py Claude Code PreToolUse hook"
```

---

## Task 7: Register hooks in Claude Code global settings

**Files:**
- Modify: `C:\Users\tjark\.claude\settings.json`

- [ ] **Step 1: Read current file**

```
cat "C:\Users\tjark\.claude\settings.json"
```

Note any existing keys to preserve.

- [ ] **Step 2: Add hooks key**

Merge the `"hooks"` key into the existing JSON. Keep all other existing keys. The hooks section must be:

```json
"hooks": {
  "Stop": [
    {
      "matcher": "",
      "hooks": [
        {
          "type": "command",
          "command": "python \"C:\\Projekte\\telegram-notion-bot\\scripts\\on_stop.py\""
        }
      ]
    }
  ],
  "PreToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "python \"C:\\Projekte\\telegram-notion-bot\\scripts\\on_permission.py\""
        }
      ]
    }
  ]
}
```

- [ ] **Step 3: Verify hooks work end-to-end**

Start a new Claude Code session. Ask Claude Code to run: `echo test`. Expected: Telegram permission message received. Tap Ja. Claude Code runs the command and finishes. Telegram "Task abgeschlossen" notification received.

- [ ] **Step 4: Commit**

```
git add "C:\Users\tjark\.claude\settings.json"
git commit -m "feat: register bot-notify hooks in Claude Code global settings"
```

---

## Self-Review Checklist

- [x] Spec: settings helpers → Task 1 ✓
- [x] Spec: `get_updates` timeout param → Task 2 ✓
- [x] Spec: `/bot-notify an/aus` handler → Task 3 ✓
- [x] Spec: poll-loop permission check → Task 4 ✓
- [x] Spec: callback query handler → Task 4 ✓
- [x] Spec: `on_stop.py` → Task 5 ✓
- [x] Spec: `on_permission.py` → Task 6 ✓
- [x] Spec: global Claude Code settings → Task 7 ✓
- [x] No TBDs or placeholders in any task ✓
- [x] `_active_permission_id` declared module-level, referenced with `global` in loop ✓
- [x] `str(uuid.uuid4())[:8]` — correct UUID string slicing ✓
- [x] `.unlink(missing_ok=True)` requires Python 3.8+ — already used in this project ✓

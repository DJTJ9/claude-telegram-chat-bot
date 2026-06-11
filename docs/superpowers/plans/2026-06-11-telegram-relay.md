# Telegram Relay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route all file-edit permission requests to Telegram and enable brainstorming Q&A via Telegram when `notifications_enabled: true`.

**Architecture:** Two independent parts. Part 1 extends the existing `PreToolUse` hook to also intercept `Edit`/`Write` tool calls, with a path-sensitivity filter so only files outside the project dir relay to Telegram. Part 2 adds a new `telegram_ask.py` script that Claude calls via Bash during brainstorming — it blocks until the user replies in Telegram, then returns the answer via stdout.

**Tech Stack:** Python 3, Telegram Bot API (via `requests`), JSON file-based IPC (same pattern as `on_permission.py`), `pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `C:\Users\tjark\.claude\settings.json` | Modify | Add `Edit` + `Write` matchers to `PreToolUse` |
| `scripts/on_permission.py` | Modify | Auto-approve Edit/Write when path is inside project dir |
| `scripts/telegram_ask.py` | Create | Send question to Telegram, block until answer, print answer |
| `bot.py` | Modify | Detect `pending_question.json`, relay to Telegram, write response when user replies |
| `C:\Users\tjark\.claude\CLAUDE.md` | Modify | Add brainstorming relay protocol instruction |
| `tests/test_permission.py` | Create | Tests for on_permission path check |
| `tests/test_telegram_ask.py` | Create | Tests for telegram_ask behavior |

---

## Task 1: Add Edit + Write PreToolUse matchers to settings.json

**Files:**
- Modify: `C:\Users\tjark\.claude\settings.json`

- [ ] **Step 1: Open settings.json and locate the PreToolUse section**

Current state of `PreToolUse`:
```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "command",
        "command": "python \"C:\\Projekte\\telegram-notion-bot\\scripts\\on_permission.py\"",
        "timeout": 320
      }
    ]
  }
]
```

- [ ] **Step 2: Add Edit and Write matchers**

Replace the `PreToolUse` array with:
```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "command",
        "command": "python \"C:\\Projekte\\telegram-notion-bot\\scripts\\on_permission.py\"",
        "timeout": 320
      }
    ]
  },
  {
    "matcher": "Edit",
    "hooks": [
      {
        "type": "command",
        "command": "python \"C:\\Projekte\\telegram-notion-bot\\scripts\\on_permission.py\"",
        "timeout": 320
      }
    ]
  },
  {
    "matcher": "Write",
    "hooks": [
      {
        "type": "command",
        "command": "python \"C:\\Projekte\\telegram-notion-bot\\scripts\\on_permission.py\"",
        "timeout": 320
      }
    ]
  }
]
```

- [ ] **Step 3: Commit**

```bash
git add "C:/Users/tjark/.claude/settings.json"
git commit -m "feat: add Edit+Write PreToolUse matchers for permission hook"
```

---

## Task 2: Path-sensitivity check in on_permission.py

**Files:**
- Modify: `scripts/on_permission.py`
- Create: `tests/test_permission.py`

The Edit tool sends `{"file_path": "...", "old_string": "...", "new_string": "..."}` as `tool_input`.
The Write tool sends `{"file_path": "...", "content": "..."}` as `tool_input`.
For both: if `file_path` resolves to inside `PROJECT_DIR`, auto-approve silently. Otherwise fall through to the Telegram relay.

- [ ] **Step 1: Write failing tests**

Create `tests/test_permission.py`:
```python
import sys, os, json
from pathlib import Path
import subprocess

PROJECT_DIR = Path(__file__).parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "on_permission.py"


def _run(tool_name, tool_input, notifications=True):
    settings = PROJECT_DIR / "settings.json"
    original = settings.read_text()
    settings.write_text(json.dumps({"notifications_enabled": notifications}))
    try:
        data = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=data, capture_output=True, text=True, timeout=5
        )
        return json.loads(result.stdout)
    finally:
        settings.write_text(original)


def test_edit_inside_project_auto_approves():
    inside_path = str(PROJECT_DIR / "bot.py")
    resp = _run("Edit", {"file_path": inside_path})
    assert resp["decision"] == "approve"


def test_write_inside_project_auto_approves():
    inside_path = str(PROJECT_DIR / "reminders.json")
    resp = _run("Write", {"file_path": inside_path})
    assert resp["decision"] == "approve"


def test_notifications_off_auto_approves_bash():
    resp = _run("Bash", {"command": "echo hi"}, notifications=False)
    assert resp["decision"] == "approve"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:\Projekte\telegram-notion-bot
pytest tests/test_permission.py -v
```

Expected: FAIL — `test_edit_inside_project_auto_approves` will hang waiting for Telegram (no path check exists yet).

- [ ] **Step 3: Write full updated scripts/on_permission.py**

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
    print(json.dumps({"decision": "block", "reason": "Hook received unparseable input"}))
    sys.exit(2)

tool_name = data.get("tool_name", "Unknown")
tool_input = data.get("tool_input", {})

# Auto-approve Edit/Write for files inside the project directory
if tool_name in ("Edit", "Write"):
    file_path_str = tool_input.get("file_path", "")
    try:
        Path(file_path_str).resolve().relative_to(PROJECT_DIR.resolve())
        print(json.dumps({"decision": "approve"}))
        sys.exit(0)
    except ValueError:
        pass  # Outside project — fall through to Telegram relay

request_id = str(uuid.uuid4())[:8]

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

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_permission.py -v
```

Expected: all three tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/on_permission.py tests/test_permission.py
git commit -m "feat: auto-approve Edit/Write inside project, relay outside project"
```

---

## Task 3: Create telegram_ask.py

**Files:**
- Create: `scripts/telegram_ask.py`
- Create: `tests/test_telegram_ask.py`

Called by Claude via Bash: `python "C:\Projekte\telegram-notion-bot\scripts\telegram_ask.py" "Frage A) ... B) ..."`
Writes `pending_question.json`, polls for `question_response_{id}.json`, prints answer to stdout.

- [ ] **Step 1: Write failing tests**

Create `tests/test_telegram_ask.py`:
```python
import sys, os, json, subprocess, threading, time
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "telegram_ask.py"


def test_notifications_off_exits_1():
    settings_path = PROJECT_DIR / "settings.json"
    original = settings_path.read_text()
    settings_path.write_text(json.dumps({"notifications_enabled": False}))
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "Test question?"],
            capture_output=True, text=True, timeout=5
        )
        assert result.returncode == 1
    finally:
        settings_path.write_text(original)


def test_returns_answer_from_response_file():
    settings_path = PROJECT_DIR / "settings.json"
    original = settings_path.read_text()
    settings_path.write_text(json.dumps({"notifications_enabled": True}))

    def write_response():
        for _ in range(40):
            pq = PROJECT_DIR / "pending_question.json"
            if pq.exists():
                req_id = json.loads(pq.read_text())["request_id"]
                (PROJECT_DIR / f"question_response_{req_id}.json").write_text(
                    json.dumps({"answer": "B"})
                )
                return
            time.sleep(0.1)

    t = threading.Thread(target=write_response)
    t.start()

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "A) opt1 B) opt2?"],
            capture_output=True, text=True, timeout=10
        )
        assert result.stdout.strip() == "B"
        assert result.returncode == 0
    finally:
        settings_path.write_text(original)
        t.join(timeout=2)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_telegram_ask.py -v
```

Expected: FAIL — script doesn't exist yet.

- [ ] **Step 3: Create scripts/telegram_ask.py**

```python
import os, sys, json, time, uuid
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

settings_path = PROJECT_DIR / "settings.json"
try:
    settings = json.loads(settings_path.read_text())
except Exception:
    settings = {}

if not settings.get("notifications_enabled", True):
    print("telegram_ask: notifications_enabled is false — relay not active", file=sys.stderr)
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: telegram_ask.py <question>", file=sys.stderr)
    sys.exit(1)

question = sys.argv[1]
request_id = str(uuid.uuid4())[:8]

pending_path = PROJECT_DIR / "pending_question.json"
pending_path.write_text(json.dumps({
    "question": question,
    "request_id": request_id,
}))

response_path = PROJECT_DIR / f"question_response_{request_id}.json"
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
        print(resp.get("answer", "A"))
        sys.exit(0)
    time.sleep(0.5)

pending_path.unlink(missing_ok=True)
print("A")
sys.exit(0)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_telegram_ask.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/telegram_ask.py tests/test_telegram_ask.py
git commit -m "feat: add telegram_ask.py for brainstorming Q&A relay"
```

---

## Task 4: Update bot.py — question relay handling

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: Add `_active_question_id` state variable**

Find in `bot.py`:
```python
_active_permission_id = None
```

Add directly below it:
```python
_active_question_id = None
```

- [ ] **Step 2: Add pending_question.json check in main loop**

Find in the `while True:` loop:
```python
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
```

After the entire block above (after the `except Exception` line), add:
```python
        pending_question_path = Path(WORK_DIR) / "pending_question.json"
        if pending_question_path.exists():
            try:
                req = json.loads(pending_question_path.read_text())
                question_text = req.get("question", "")
                send_message(MY_CHAT_ID, f"❓ Brainstorming-Frage:\n\n{question_text}")
                _active_question_id = req["request_id"]
                pending_question_path.unlink()
            except Exception as e:
                print(f"question check error: {e}")
```

- [ ] **Step 3: Shorten poll timeout when question is active**

Find:
```python
        poll_timeout = 5 if _active_permission_id else 30
```

Replace with:
```python
        poll_timeout = 5 if (_active_permission_id or _active_question_id) else 30
```

- [ ] **Step 4: Handle question answer in message handler**

Find in the message handler (after voice/text extraction, before `/bot-notify` check):
```python
            if text.lower().startswith("/bot-notify"):
```

Directly before that line, insert:
```python
            if _active_question_id:
                resp_path = (Path(WORK_DIR) / f"question_response_{_active_question_id}.json").resolve()
                if Path(WORK_DIR).resolve() not in resp_path.parents:
                    continue
                resp_path.write_text(json.dumps({"answer": text}))
                _active_question_id = None
                send_message(chat_id, f"💬 Antwort gesendet: {text}")
                continue
```

- [ ] **Step 5: Fix permission message format for Edit/Write tools**

Find in `bot.py`'s main loop, the block inside `if pending_path.exists():`:
```python
                tool_input = req.get("input", {})
                cmd = str(tool_input.get("command", tool_input))[:200]
                msg_text = f"🔐 Permission needed:\nTool: {req['tool']}\n$ {cmd}"
```

Replace with:
```python
                tool_input = req.get("input", {})
                tool_name = req.get("tool", "Unknown")
                if tool_name in ("Edit", "Write"):
                    file_path = tool_input.get("file_path", str(tool_input))[:300]
                    msg_text = f"✏️ Datei-Edit:\n{file_path}"
                else:
                    cmd = str(tool_input.get("command", tool_input))[:200]
                    msg_text = f"🔐 Permission needed:\nTool: {tool_name}\n$ {cmd}"
```

- [ ] **Step 6: Run existing tests to confirm no regressions**

```bash
pytest tests/test_bot.py -v
```

Expected: all existing tests PASS.

- [ ] **Step 7: Commit**

```bash
git add bot.py
git commit -m "feat: add question relay state and pending_question handling to bot"
```

---

## Task 5: Add brainstorming relay protocol to CLAUDE.md

**Files:**
- Modify: `C:\Users\tjark\.claude\CLAUDE.md`

- [ ] **Step 1: Append instruction block to CLAUDE.md**

Add at the end of `C:\Users\tjark\.claude\CLAUDE.md`:

```markdown
## Brainstorming via Telegram Relay

At the start of any brainstorming session, read `C:\Projekte\telegram-notion-bot\settings.json`.

If `notifications_enabled: true`:
- Do NOT output clarifying questions as terminal text
- For every clarifying question, run via Bash:
  `python "C:\Projekte\telegram-notion-bot\scripts\telegram_ask.py" "your full question with options A) ... B) ... C) ..."`
- The Bash stdout is the user's answer — process it and continue
- Apply for the entire session until the spec is written

If `notifications_enabled: false`: use normal terminal text output.
```

- [ ] **Step 2: Commit**

```bash
git add "C:/Users/tjark/.claude/CLAUDE.md"
git commit -m "feat: add brainstorming Telegram relay protocol to CLAUDE.md"
```

---

## Task 6: End-to-end smoke test

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: Manual smoke test — permission relay for file edits**

1. Ensure bot is running (`python bot.py`)
2. Enable notifications: send `/bot-notify an` to bot
3. In Claude Code: ask Claude to edit `C:\Users\tjark\.claude\CLAUDE.md`
4. Verify Telegram message appears: `✏️ Datei-Edit: C:\Users\tjark\.claude\CLAUDE.md`
5. Tap `Ja ✅` — verify Claude continues editing
6. Tap `Nein ❌` on a second attempt — verify Claude gets blocked

- [ ] **Step 3: Manual smoke test — brainstorming relay**

1. Ensure bot running, notifications on (`/bot-notify an`)
2. In Claude Code: invoke `/superpowers:brainstorming` with a small feature idea
3. Verify first clarifying question appears in Telegram as `❓ Brainstorming-Frage:`
4. Reply "A" in Telegram
5. Verify `💬 Antwort gesendet: A` confirmation appears in Telegram
6. Verify Claude Code continues with next question or next brainstorming step

- [ ] **Step 4: Verify notifications-off passthrough**

1. Send `/bot-notify aus` to bot
2. In Claude Code: ask Claude to edit `C:\Users\tjark\.claude\CLAUDE.md` → no Telegram message, auto-approved
3. In Claude Code: start brainstorming → questions appear in terminal, not Telegram

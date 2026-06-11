# Bot Notify — Design Spec

**Date:** 2026-06-11  
**Command:** `/bot-notify`

## Overview

Telegram command that toggles Claude Code notifications on/off. When enabled:
- Claude Code Stop hook sends Telegram message on task completion
- Claude Code PreToolUse hook asks permission via Telegram before running Bash commands (interactive, waits for user reply)

## Architecture

### Components

| File | Type | Purpose |
|------|------|---------|
| `settings.json` | config | persistent toggle state |
| `bot.py` | modified | command handler, poll-loop check, callback handler |
| `scripts/on_stop.py` | new | Stop hook script |
| `scripts/on_permission.py` | new | PreToolUse hook script |
| `C:\Users\tjark\.claude\settings.json` | modified | global Claude Code hooks |

### IPC Files (temporary, project root)

- `pending_permission.json` — written by hook script, deleted by bot after sending message
- `permission_response_{id}.json` — written by bot on user reply, deleted by hook script after reading

## Data Flow

### Task Completion Notification

```
Claude Code task ends
  → Stop hook fires
  → on_stop.py reads settings.json
  → if notifications_enabled: POST to Telegram sendMessage API
  → User receives: "✅ Claude Code Task abgeschlossen"
```

### Permission Request

```
Claude Code about to run Bash command
  → PreToolUse hook fires
  → on_permission.py reads tool_name + tool_input from stdin
  → writes pending_permission.json {tool, input, request_id}
  → polls permission_response_{id}.json every 500ms (max 5 min)

  Bot main loop (every poll cycle):
  → checks pending_permission.json
  → if found: send Telegram message with inline keyboard, delete file

  User taps [Ja ✅] or [Nein ❌]:
  → bot callback handler writes permission_response_{id}.json {approved: bool}
  → bot sends confirmation message

  on_permission.py finds response file:
  → approved → print {"decision": "approve"}, exit 0
  → denied  → print {"decision": "block", "reason": "Denied via Telegram"}, exit 2
  → timeout → print {"decision": "approve"}, exit 0  (auto-approve after 5 min)
```

### Toggle

```
User sends "/bot-notify an" or "/bot-notify aus"
  → bot reads settings.json
  → toggles notifications_enabled
  → writes settings.json
  → replies with status confirmation
```

## settings.json

```json
{"notifications_enabled": true}
```

Located in project root (`C:\Projekte\telegram-notion-bot\settings.json`).

## Permission Telegram Message Format

```
🔐 Permission needed:
Tool: Bash
$ rm -rf build/ && npm install

[Ja ✅]  [Nein ❌]
```

Callback data: `approve_{request_id}` / `deny_{request_id}`  
Command truncated to 200 chars if longer.

## Bot Changes (`bot.py`)

### 1. Settings helpers

```python
def load_settings():
    path = Path("settings.json")
    if path.exists():
        return json.loads(path.read_text())
    return {"notifications_enabled": True}

def save_settings(s):
    Path("settings.json").write_text(json.dumps(s, indent=2))
```

### 2. `/bot-notify` command handler

Triggered by text starting with `/bot-notify`. Parses `an`/`aus`, toggles `notifications_enabled`, confirms status.

### 3. Poll-loop addition

In main poll loop, **before** calling `get_updates`: check for `pending_permission.json`. If found, send permission message with inline keyboard and delete the file.

Also reduce `get_updates` timeout from 30s to 5s while a permission request is pending, so the user sees the Telegram message within ~5 seconds instead of up to 30.

### 4. Callback query handler

Handle `callback_query` updates with data `approve_{id}` or `deny_{id}`. Write response file, answer callback query, send confirmation message.

## Hook Scripts

Both scripts read bot token and chat ID from `.env` via `python-dotenv`.

### `scripts/on_stop.py`

1. Load `.env`
2. Read `settings.json` — if `notifications_enabled` is false, exit 0
3. POST to `https://api.telegram.org/bot{TOKEN}/sendMessage` with chat_id and "✅ Claude Code Task abgeschlossen"

### `scripts/on_permission.py`

1. Load `.env`
2. Read `settings.json` — if disabled, print `{"decision": "approve"}`, exit 0
3. Read JSON from stdin (tool_name, tool_input)
4. Generate `request_id = uuid4()[:8]`
5. Write `pending_permission.json`
6. Poll loop (500ms interval, 300s max):
   - If `permission_response_{id}.json` exists: read, delete, return decision
7. On timeout: delete `pending_permission.json`, return approve

## Claude Code Global Settings

`C:\Users\tjark\.claude\settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "python \"C:\\Projekte\\telegram-notion-bot\\scripts\\on_stop.py\""}]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "python \"C:\\Projekte\\telegram-notion-bot\\scripts\\on_permission.py\""}]
      }
    ]
  }
}
```

Global scope: applies to all Claude Code sessions on this PC.

## Error Handling

- `settings.json` missing → default `notifications_enabled: true`
- Bot not running when hook fires → permission script polls until timeout, then auto-approves
- Multiple simultaneous permission requests → request_id (uuid) prevents file collision
- Telegram API unreachable in on_stop.py → fail silently (non-zero exit ignored by Stop hook)

## Out of Scope

- Per-tool-type permission toggles (only Bash for now)
- Separate toggles for tasks vs permissions
- Notification history or audit log

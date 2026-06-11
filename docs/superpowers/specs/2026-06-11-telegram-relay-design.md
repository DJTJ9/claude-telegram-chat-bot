# Telegram Relay: Permission Gap Fix + Brainstorming Q&A

**Date:** 2026-06-11  
**Status:** Approved

## Problem

1. `PreToolUse` hook only matches `Bash`. When Claude uses `Edit`/`Write` to modify files like `C:\Users\tjark\.claude\CLAUDE.md`, no Telegram notification fires — user must approve on the PC.
2. Brainstorming clarification questions appear only in the Claude Code terminal. User cannot answer them via Telegram when away from PC.

## Part 1: Permission Gap Fix

### What changes

**`C:\Users\tjark\.claude\settings.json`**  
Add two additional `PreToolUse` hook entries — one for `Edit`, one for `Write` — both pointing to the same `on_permission.py`.

**`scripts/on_permission.py`**  
Add path-sensitivity check for Edit/Write tool calls:
- Extract `file_path` from `tool_input`
- If path is **inside** `PROJECT_DIR` → auto-approve, no Telegram message
- If path is **outside** `PROJECT_DIR` (e.g. user `.claude` dir, global settings) → relay to Telegram

Telegram message format for file edits:
```
✏️ Datei-Edit:
C:\Users\tjark\.claude\CLAUDE.md
[Ja ✅] [Nein ❌]
```

Bash tool calls are unaffected — existing logic stays.

### What does NOT change

Bot.py permission handling (callback_query for approve/deny) is unchanged. Same response-file mechanism reused.

---

## Part 2: Brainstorming Q&A Relay

### Trigger condition

Active when `notifications_enabled: true` in `C:\Projekte\telegram-notion-bot\settings.json`.  
When `false`: normal terminal dialog, no relay.

### New file: `scripts/telegram_ask.py`

Called by Claude via Bash during brainstorming:
```bash
python scripts/telegram_ask.py "Frage mit Optionen A) ... B) ... C) ..."
```

Behavior:
1. Reads `settings.json`
2. If `notifications_enabled: false` → prints error and exits 1 (script should not be called in this state; Claude only calls it when relay is active)
3. If `notifications_enabled: true`:
   - Generates `request_id` (8-char UUID prefix)
   - Writes `pending_question.json`: `{"question": "...", "request_id": "..."}`
   - Polls for `question_response_{request_id}.json` (max 300s, 0.5s interval)
   - On response: reads answer, deletes response file, prints answer to stdout, exits 0
   - On timeout: prints "A" to stdout (first option fallback), logs timeout, exits 0

### `bot.py` changes

New state variable: `_active_question_id: str | None = None`

Main loop additions (after pending_permission check):
- Check for `pending_question.json`
- If found: send question text as plain Telegram message, set `_active_question_id`, delete file

Incoming text message handling:
- If `_active_question_id` is set AND message is from `MY_CHAT_ID`:
  - Write `question_response_{_active_question_id}.json`: `{"answer": "<text>"}`
  - Clear `_active_question_id`
  - Send confirmation: `💬 Antwort gesendet: <text>`
  - Skip normal command processing for this message

### Brainstorming protocol (CLAUDE.md instruction)

Instruction added to `C:\Users\tjark\.claude\CLAUDE.md`:

> When starting a brainstorming session: read `C:\Projekte\telegram-notion-bot\settings.json`. If `notifications_enabled: true`, use `python C:\Projekte\telegram-notion-bot\scripts\telegram_ask.py "question"` via Bash for every clarifying question instead of outputting the question as text. Read the Bash output as the user's answer and continue. If `notifications_enabled: false`, use normal text output.

### Data flow

```
Claude Code
  └─ Bash: python scripts/telegram_ask.py "Frage A) ... B) ..."
       └─ writes pending_question.json
            └─ bot.py detects → sends to Telegram
                 └─ user replies "B"
                      └─ bot.py writes question_response_{id}.json
                           └─ telegram_ask.py reads → prints "B" to stdout
                                └─ Claude reads stdout → continues brainstorming
```

### Conflict handling

- Permission pending + question pending simultaneously: both files checked in sequence each loop tick. No conflict — different files, different state vars.
- User sends command while question pending: message consumed as question answer. Normal command processing skipped for that message.

---

## Files touched

| File | Change |
|------|--------|
| `C:\Users\tjark\.claude\settings.json` | Add Edit + Write PreToolUse matchers |
| `scripts/on_permission.py` | Path-sensitivity check for Edit/Write |
| `scripts/telegram_ask.py` | New file |
| `bot.py` | `_active_question_id` state + pending_question handling |
| `C:\Users\tjark\.claude\CLAUDE.md` | Brainstorming relay protocol instruction |

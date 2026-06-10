# Design: Organizer Bot Improvements

**Date:** 2026-06-10  
**Scope:** telegram-notion-bot / bot.py  

## Problem

Three pain points in daily workflow:
1. Changing task status requires opening Notion manually
2. Bot commands must be memorized — no discovery mechanism
3. Voice transcription produces "Doppelpunkt" instead of ":" breaking all commands

## Features

### 1. Voice Normalization

**Where:** `transcribe_voice()` return value, before routing.

**What:**
- New function `normalize_voice(text: str) -> str`
- Replaces spoken German punctuation names with symbols:
  - `Doppelpunkt` → `:`
  - `Komma` → `,`
  - `Punkt` → `.`
- Case-insensitive replacement
- Add Whisper `initial_prompt` to Groq call: `"task: erledigt: status: fokus: lern: idee: verschieben:"` — biases model toward colon syntax

**Why:** `.lower()` already runs in routing, so capitalized commands from Whisper are already handled. Only punctuation names need explicit normalization.

### 2. Generic Status Command

**Prefix:** `status:`

**Behavior:**
- Claude reads Tagesorganizer, fuzzy-matches task name from input text
- Derives target status from natural language keywords:
  - `erledigt / fertig / done` → `Done`
  - `in arbeit / läuft / gestartet` → `In progress`
  - `offen / zurück / nicht gestartet` → `Not started`
- Response format: `✅ Status geändert: [Task Name] → [Status]`
- On no match: `❌ Kein passender Task gefunden: "[input]"`

**Voice example:** "status Doppelpunkt sport erledigt"  
→ normalize → "status: sport erledigt"  
→ Claude → Done

**System prompt:** `STATUS_SYSTEM_PROMPT` added to bot.py alongside existing prompts.

### 3. ReplyKeyboard + `hilfe` Command

**ReplyKeyboard:**
- `send_message()` always includes `reply_markup` with persistent keyboard
- Layout (2 per row, `resize_keyboard: true`, `one_time_keyboard: false`):
  ```
  [moin]         [abend]
  [task:]        [status:]
  [woche]        [fokus:]
  [verschieben:] [hilfe]
  ```
- Keyboard hardcoded — no usage tracking needed

**`hilfe` command:**
- Returns static text with all commands and syntax
- Groups: Tagesplanung / Tasks / Projekte / Listen / Sonstiges

## Implementation Plan

### Files changed
- `bot.py` only — no new files

### Changes in order
1. Add `normalize_voice(text)` function
2. Call `normalize_voice()` after `transcribe_voice()` in main loop
3. Add `initial_prompt` to Groq Whisper call
4. Add `STATUS_SYSTEM_PROMPT`
5. Add `status:` routing branch
6. Add `HILFE_TEXT` constant
7. Add `hilfe` routing branch
8. Modify `send_message()` to accept and pass `reply_markup`
9. Build `REPLY_KEYBOARD` constant
10. Pass keyboard in all `send_message()` calls in main loop

## Success Criteria

- `status: sport erledigt` via text → task marked Done in Notion
- Voice "status Doppelpunkt sport erledigt" → same result
- Voice "task Doppelpunkt bug fixen" → task created (no "Doppelpunkt" in task name)
- Keyboard buttons visible after every bot response
- `hilfe` returns full command list

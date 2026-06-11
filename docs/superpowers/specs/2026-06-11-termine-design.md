# Design: Termine Feature

**Date:** 2026-06-11  
**Status:** Approved

## Overview

Add appointment ("Termin") support to the Notion Organizer bot. Termine are tasks with a fixed date AND time. They appear at the top of the morning workflow, above regular tasks.

## Data Model

No Notion schema changes required.

Termin = Task in Tagesorganizer where `Datum` is a **datetime** (`2026-06-15T14:00:00`).  
Regular Task = Task where `Datum` is **date-only** (`2026-06-15`).

Notion's existing `Datum` date property supports both formats in the same field.

Properties set for a Termin:
- `Name` (title) — derived from user text
- `Datum` (date, with time) — derived from user text; defaults: today, 09:00
- `Status` — `Not started`
- No `Priorität`, no `Bereich` (not needed for appointments)

## Bot Command

**Trigger:** `termin: <text>`

**Handler:** single `run_claude()` call with `TERMIN_SYSTEM_PROMPT`

```python
TERMIN_SYSTEM_PROMPT = """Du bist ein Notion-Termin-Assistent.
Lege den Termin im Tagesorganizer an (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Leite aus dem Text ab:
- Name: Bezeichnung des Termins
- Datum: ISO 8601 datetime YYYY-MM-DDTHH:MM:SS
  Falls kein Datum: heute. Falls keine Uhrzeit: 09:00.
  "morgen" = heute + 1 Tag, Wochentage relativ zu heute.
  "um 14" oder "14 Uhr" → 14:00:00, "halb drei" → 14:30:00
Antworte NUR mit einer Zeile: 📅 Termin angelegt: [Name] · [DD.MM.YYYY um HH:MM]"""
```

**Prompt:** `f"Heute ist {today}. Termin: {termin_text}"`

**Edge cases:**
- Empty `termin:` → usage hint, no Claude call
- No date in text → today
- No time in text → 09:00

## Morning Workflow (moin)

`MOIN_SYSTEM_PROMPT` updated to split today's tasks into Termine (datetime) and Tasks (date-only).

**New output format:**
```
🌅 Guten Morgen! [DD.MM.YYYY]
📁 [Projektübersicht]  ← only if project tasks exist

📅 Termine heute ([N]):      ← only if Termine exist
· HH:MM · [Name]             ← sorted by time ascending

📋 Tasks heute ([N]):        ← only if Tasks exist
· [Prio-Icon] [→Projekt] [Name]  ← sorted by Priorität (Hoch first)

🔄 Habits heute ([N]):       ← unchanged, only if due habits exist
· [Name] (alle [Intervall] Tage)
```

Prio-Icons: Hoch=🔴 Mittel=🟡 Niedrig=🟢  
Projekt-Übersicht (line 2) reflects Tasks only, not Termine.  
Sections with zero items are omitted entirely.

## Help Text

New entry in `HILFE_TEXT` under "Tasks & Habits":
```
  termin: <text> — Termin anlegen
    z.B. termin: Arzttermin morgen um 14:00
```

No new keyboard button (keyboard is already full).

## CLAUDE.md Update

Morgen-Workflow section updated: show Termine before Tasks.

## Files Changed

- `bot.py` — add `TERMIN_SYSTEM_PROMPT`, `termin:` handler, update `MOIN_SYSTEM_PROMPT`, update `HILFE_TEXT`
- `CLAUDE.md` (global) — update Morgen-Workflow description

# Design: Habits-System, task: Dialog, status: erledigt

**Date:** 2026-06-10  
**Status:** Approved

---

## Overview

Three features:
1. **Habits-System** — recurring tasks in own Notion DB, shown in Morgen-Workflow
2. **`task:` Interactive Dialog** — two-step creation with Claude-parsed free-form input
3. **`status: X erledigt`** — "erledigt" as Done alias, with Habit recurrence logic

---

## Feature 1: Habits-System

### Notion Database: "Habits"

New database in Organizer workspace with these properties:

| Property | Type | Notes |
|---|---|---|
| Name | title | Habit name |
| Intervall | number | Days between occurrences (1=daily, 7=weekly) |
| Bereich | select | Arbeit / Privat / Lernen / Gesundheit |
| Nächste Fälligkeit | date | Next due date |
| Status | status | Aktiv / Pausiert |

### Creating a Habit: `habit: <Freitext>`

- User sends e.g. `habit: Sport täglich` or `habit: Laufen alle 2 Tage, Gesundheit`
- Claude extracts: Name, Intervall (as integer days), Bereich
- Defaults: Bereich=leer, Nächste Fälligkeit=heute
- Bot confirms: "Habit 'Sport' angelegt — täglich, nächste Fälligkeit heute."

### Morgen-Workflow

Morgen-Workflow gains a "Habits heute" section after existing task list:
- Query Habits where `Nächste Fälligkeit ≤ heute` AND `Status = Aktiv`
- Sort by Bereich
- If none: section omitted

### Completing a Habit

Via `status: Sport erledigt` (see Feature 3).

---

## Feature 2: `task:` Interactive Dialog

### Flow

1. User sends `task:` (bare command or button tap)
2. Bot replies with prompt:
   > "Schreib mir: Name, Priorität (Hoch/Mittel/Niedrig), Bereich (Arbeit/Privat/Lernen/Gesundheit)"
3. Bot sets `pending_task_input[user_id] = True` in-memory
4. User sends one free-form message, e.g. `Arzttermin, hoch, gesundheit`
5. Bot sends text to Claude for field extraction
6. Bot creates task with extracted fields
7. Bot confirms: "Task 'Arzttermin' angelegt — Hoch, Gesundheit, heute."
8. State cleared from `pending_task_input`

### Defaults (when fields missing)

| Field | Default |
|---|---|
| Datum | heute |
| Priorität | Mittel |
| Bereich | leer |

### State Management

`pending_task_input: dict[user_id, bool]` — in-memory, reset after parse or on `restart`.

---

## Feature 3: `status: X erledigt`

### Keyword Mapping

`erledigt` → `Done` (case-insensitive, alongside existing status keywords)

### Dual-DB Lookup

When `erledigt` is detected:

1. Search Tagesorganizer for task named X → if found → set Status=Done
2. Search Habits for habit named X → if found:
   - Set Status=Done
   - Calculate `Nächste Fälligkeit = heute + Intervall (days)`
   - Set Status back to Aktiv (habit resets for next occurrence)
3. Both can match simultaneously — both are updated
4. Bot responds summarizing what was updated

---

## Implementation Order

1. `status: erledigt` keyword (trivial, no new DB)
2. Habits Notion DB setup + `habit:` command
3. Morgen-Workflow Habits section
4. `status: erledigt` Habit recurrence logic
5. `task:` dialog with pending state

# Design: Backlog & Task-Archiv

**Date:** 2026-06-12  
**Status:** Approved

## Overview

Two new Notion databases on the Organizer page:
- **Backlog** — tasks without a fixed date (someday/maybe items)
- **Task-Archiv** — completed tasks moved out of Tagesorganizer

## Notion Databases

### Backlog

| Property | Type | Values |
|---|---|---|
| Name | title | — |
| Status | status | `Offen` \| `Erledigt` |
| Priorität | select | `Hoch` \| `Mittel` \| `Niedrig` |
| Bereich | select | `Arbeit` \| `Privat` \| `Lernen` \| `Gesundheit` |
| Notiz | rich_text | — |

No Datum field — distinguishes backlog items from Tagesorganizer tasks.

### Task-Archiv

| Property | Type | Values |
|---|---|---|
| Name | title | — |
| Status | status | copied from source DB |
| Priorität | select | copied |
| Datum | date | copied (null for backlog items) |
| Bereich | select | copied |
| Notiz | rich_text | copied |
| Archiviert am | date | timestamp of archive operation |

Both databases are created on the Organizer page (same parent as Tagesorganizer).

## Bot Commands

### New: `backlog: <text>`

Adds a task to the Backlog DB. Triggers interactive dialog (same pattern as `task:`):
1. Bot asks for Priorität (A) Hoch B) Mittel C) Niedrig)
2. Bot asks for Bereich (A) Arbeit B) Privat C) Lernen D) Gesundheit)
3. Task created in Backlog with Status = `Offen`

### New: `backlog`

Lists all Backlog tasks with Status = `Offen`, sorted by Priorität (Hoch first). Format mirrors the Tagesorganizer morning view.

### Modified: `task:` dialog

First step added to existing `task:` interactive dialog:
> "Neuer Task oder aus Backlog? A) Neu B) Aus Backlog"

- **A) Neu**: existing flow unchanged
- **B) Aus Backlog**: bot fetches open Backlog items, user selects one by number, bot asks for Datum → task is created in Tagesorganizer with that date, original Backlog item is set to `Erledigt` (archive loop removes it)

### Modified: `status: X erledigt`

Existing command. After setting status to Done, immediately triggers archive move (see Archiving Flow below).

### Keyboard

`backlog` added as 9th ReplyKeyboard button.

## Archiving Flow

### Immediate Trigger (bot-driven)

When `status: X erledigt` is processed:
1. Find task in Tagesorganizer (or Backlog) by name
2. Copy all properties to Task-Archiv, set `Archiviert am` = now
3. Archive original page via `archived: true` in Notion API

### Background Loop (30-minute interval)

Runs alongside existing bot loops. On each tick:
1. Query Tagesorganizer for pages with `Status = Done`
2. Query Backlog for pages with `Status = Erledigt`
3. For each: check if already in Task-Archiv by matching Name + original Datum (or null for backlog)
4. If not found: copy + archive original

Deduplication prevents double entries when both immediate trigger and loop run.

### One-Time Migration

Runs once on first bot start after deployment. Identical logic to background loop. Controlled by flag in `settings.json`:

```json
{ "archive_migration_done": true }
```

Flag is written after successful migration. If absent or `false`, migration runs on startup.

## CLAUDE.md Updates

After databases are created in Notion, add to CLAUDE.md:

```
# Backlog-Datenbank
- data_source_id: <to be filled after creation>
- Properties: Name, Status (Offen|Erledigt), Priorität, Bereich, Notiz

# Task-Archiv-Datenbank  
- data_source_id: <to be filled after creation>
- Properties: Name, Status, Priorität, Datum, Bereich, Notiz, Archiviert am
```

## Out of Scope

- Deleting from Backlog (use Notion directly)
- Restoring archived tasks back to Tagesorganizer
- Filtering backlog by Bereich via bot command

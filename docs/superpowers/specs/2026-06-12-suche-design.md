# Design: suche: — Volltext-Suche über alle Organizer-DBs

**Date:** 2026-06-12  
**Status:** Approved

## Overview

Neuer Bot-Befehl `suche: <text>` durchsucht alle 5 Notion-Datenbanken nach einem Begriff (Name + Textfeld) und gibt gruppierte Treffer zurück.

## Command Interface

- Auslöser: `suche: <text>` (case-insensitive prefix)
- Leer (`suche:` ohne Begriff) → sofortiger Fehler, kein LLM-Call:
  `❓ Suchbegriff fehlt. z.B.: suche: Python`
- Kein neuer Keyboard-Button (niedrige Nutzungsfrequenz)
- Neuer Eintrag in `HILFE_TEXT` unter "Listen":
  `suche: <text> — Alle DBs durchsuchen (Tasks, Backlog, Archiv, Lernthemen, Ideen)`

## System Prompt

```python
SUCHE_SYSTEM_PROMPT = """Du bist ein Notion-Suchassistent.
Der Nutzer gibt einen Suchbegriff. Suche in allen 5 Datenbanken:

1. Tagesorganizer  (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0) — Felder: Name, Notiz
2. Backlog         (data_source_id: 0cb18d17-cf70-413d-b29d-adb4675db614) — Felder: Name, Notiz
3. Task-Archiv     (data_source_id: abb5abd8-e320-4796-bbf6-941feb9007b9) — Felder: Name, Notiz
4. Lernthemen      (data_source_id: 5a76447f-2b0a-4f6b-81bb-853f39aa04bb) — Felder: Name, Notiz
5. Spieleideen     (data_source_id: ce6783d1-54fe-421f-8d7d-aa8c34880853) — Felder: Name, Beschreibung

Für jede DB: nutze contains-Filter auf Name ODER das Textfeld (OR-Verknüpfung).
Zeige nur DBs mit Treffern. Sortiere Treffer pro DB nach Priorität falls vorhanden.

Format:
Zeile 1: "🔍 Suche: \"[Begriff]\""
Leerzeile
Je DB mit Treffern:
  "[Icon] [DB-Name] ([N])"
  Je Treffer: "  · [Status-Icon] [Name][— Datum falls gesetzt]"
  Leerzeile
Letzte Zeile: "🔍 [Gesamt] Treffer in [M] Datenbank(en)."
Falls keine Treffer: "🔍 Keine Ergebnisse für \"[Begriff]\"."

Status-Icons: Not started/Offen=⬜ In progress/In Bearbeitung=🔄 Done/Erledigt/Abgeschlossen=✅
DB-Icons: 📋 Tagesorganizer, 📦 Backlog, 🗂 Archiv, 📚 Lernthemen, 🎮 Spieleideen
Kein Markdown."""
```

## Bot Handler

Neuer Case im `handle_message`-Dispatcher, nach bestehenden `elif`-Blöcken:

```python
elif text.lower().startswith("suche:"):
    query = text[6:].strip()
    if not query:
        send_message(chat_id, "❓ Suchbegriff fehlt. z.B.: suche: Python")
        return
    run_claude_task(chat_id, SUCHE_SYSTEM_PROMPT, query)
```

## Tests

3 neue Tests in `tests/test_bot.py` (Pattern: `run_claude_task` gemockt):

| Test | Input | Erwartung |
|------|-------|-----------|
| `test_suche_leer` | `"suche:"` | `send_message` mit Fehler, kein LLM-Call |
| `test_suche_mit_text` | `"suche: Python"` | `run_claude_task(SUCHE_SYSTEM_PROMPT, "Python")` |
| `test_suche_case_insensitive` | `"SUCHE: test"` | gleicher Handler greift |

## Affected Files

- `bot.py` — 1 neue Konstante `SUCHE_SYSTEM_PROMPT`, 1 neuer `elif`-Block, 1 Zeile in `HILFE_TEXT`
- `tests/test_bot.py` — 3 neue Tests

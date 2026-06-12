# suche: Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `suche: <text>` command that searches all 5 Notion DBs (Name + Textfeld) and returns grouped results.

**Architecture:** Pure AI system-prompt approach — one new `SUCHE_SYSTEM_PROMPT` constant, one new `elif` handler in the main dispatch loop, two test additions. No new files. Follows existing `fokus:` / `termin:` pattern exactly.

**Tech Stack:** Python, existing `run_claude()` helper, Notion MCP tools (called by Claude)

---

### Task 1: Add SUCHE_SYSTEM_PROMPT constant and hilfe entry

**Files:**
- Modify: `bot.py` — after `BACKLOG_PROMOTE_SYSTEM_PROMPT` block (~line 346)
- Modify: `bot.py` — `HILFE_TEXT` string, "Listen" section (~line 95)
- Modify: `tests/test_bot.py` — add 3 tests + extend import

- [ ] **Step 1: Write the failing tests**

In `tests/test_bot.py`, update the existing import line at the top:

```python
# Change this line:
from bot import normalize_voice, REPLY_KEYBOARD, HILFE_TEXT, MOIN_SYSTEM_PROMPT, HABITS_DATA_SOURCE_ID, STATUS_SYSTEM_PROMPT, pending_task_input, load_reminders, save_reminders, REMINDER_PARSE_SYSTEM_PROMPT
# To:
from bot import normalize_voice, REPLY_KEYBOARD, HILFE_TEXT, MOIN_SYSTEM_PROMPT, HABITS_DATA_SOURCE_ID, STATUS_SYSTEM_PROMPT, pending_task_input, load_reminders, save_reminders, REMINDER_PARSE_SYSTEM_PROMPT, SUCHE_SYSTEM_PROMPT
```

Then add at the end of `tests/test_bot.py`:

```python
def test_suche_prompt_contains_all_dbs():
    for ds_id in [
        "c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0",  # Tagesorganizer
        "0cb18d17-cf70-413d-b29d-adb4675db614",  # Backlog
        "abb5abd8-e320-4796-bbf6-941feb9007b9",  # Archiv
        "5a76447f-2b0a-4f6b-81bb-853f39aa04bb",  # Lernthemen
        "ce6783d1-54fe-421f-8d7d-aa8c34880853",  # Spieleideen
    ]:
        assert ds_id in SUCHE_SYSTEM_PROMPT, f"Missing data_source_id: {ds_id}"

def test_suche_prompt_contains_no_treffer_message():
    assert "Keine Ergebnisse" in SUCHE_SYSTEM_PROMPT

def test_hilfe_contains_suche():
    assert "suche:" in HILFE_TEXT
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_bot.py::test_suche_prompt_contains_all_dbs tests/test_bot.py::test_suche_prompt_contains_no_treffer_message tests/test_bot.py::test_hilfe_contains_suche -v
```

Expected: ImportError (`SUCHE_SYSTEM_PROMPT` not defined yet)

- [ ] **Step 3: Add SUCHE_SYSTEM_PROMPT to bot.py**

In `bot.py`, after the `BACKLOG_PROMOTE_SYSTEM_PROMPT` block (the block ending with `Kein Markdown."""`), insert:

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

- [ ] **Step 4: Add suche: entry to HILFE_TEXT**

In `bot.py`, find the "Listen" section in `HILFE_TEXT`:
```
📚 Listen
  lern: <thema> — Lernthema speichern
  idee: <text> — Spielidee speichern
```

Change to:
```
📚 Listen
  lern: <thema> — Lernthema speichern
  idee: <text> — Spielidee speichern
  suche: <text> — Alle DBs durchsuchen (Tasks, Backlog, Archiv, Lernthemen, Ideen)
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_bot.py::test_suche_prompt_contains_all_dbs tests/test_bot.py::test_suche_prompt_contains_no_treffer_message tests/test_bot.py::test_hilfe_contains_suche -v
```

Expected: 3 PASSED

- [ ] **Step 6: Run full test suite**

```
pytest tests/test_bot.py -v
```

Expected: all existing tests PASSED

- [ ] **Step 7: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add SUCHE_SYSTEM_PROMPT constant and hilfe entry"
```

---

### Task 2: Add suche: handler in dispatcher

**Files:**
- Modify: `bot.py` — `_is_command` guard in `pending_task_input` block (~line 854)
- Modify: `bot.py` — main `elif` dispatch chain, before `/teach` block (~line 1066)
- Modify: `tests/test_bot.py` — add 4 handler tests

- [ ] **Step 1: Write the failing tests**

Add at end of `tests/test_bot.py`:

```python
def test_suche_prefix_detection():
    text = "suche: Python"
    assert text.lower().startswith("suche:")
    assert text[6:].strip() == "Python"

def test_suche_empty_detection():
    text = "suche:"
    assert text[6:].strip() == ""

def test_suche_case_insensitive():
    text = "SUCHE: test"
    assert text.lower().startswith("suche:")
    assert text[6:].strip() == "test"

def test_suche_is_known_command():
    known_prefixes = (
        "task:", "status:", "fokus:", "verschieben:", "lern:",
        "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
        "implement-plan:", "abort-plan:", "backlog:", "suche:",
    )
    assert "suche: Python".lower().startswith(known_prefixes)
```

- [ ] **Step 2: Run tests to verify status**

```
pytest tests/test_bot.py::test_suche_prefix_detection tests/test_bot.py::test_suche_empty_detection tests/test_bot.py::test_suche_case_insensitive tests/test_bot.py::test_suche_is_known_command -v
```

Expected: first 3 PASS (pure string logic), `test_suche_is_known_command` FAILS (tuple missing `"suche:"`)

- [ ] **Step 3: Add "suche:" to pending_task_input guard**

In `bot.py`, find the `_is_command` assignment. The last line of the prefix tuple ends with `"implement-plan:", "abort-plan:", "backlog:")))`.

Change:
```python
                      ("task:", "status:", "fokus:", "verschieben:", "lern:",
                       "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
                       "implement-plan:", "abort-plan:", "backlog:")))
```

To:
```python
                      ("task:", "status:", "fokus:", "verschieben:", "lern:",
                       "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
                       "implement-plan:", "abort-plan:", "backlog:", "suche:")))
```

- [ ] **Step 4: Add suche: elif handler**

In `bot.py`, find the block that starts with:
```python
            elif text.lower().startswith("/teach") or text.lower().startswith("teach:"):
```

Insert the following block directly before it:
```python
            elif text.lower().startswith("suche:"):
                query = text[6:].strip()
                if not query:
                    response = "❓ Suchbegriff fehlt. z.B.: suche: Python"
                else:
                    response = run_claude(query, system_prompt=SUCHE_SYSTEM_PROMPT)
```

- [ ] **Step 5: Run tests to verify they all pass**

```
pytest tests/test_bot.py::test_suche_prefix_detection tests/test_bot.py::test_suche_empty_detection tests/test_bot.py::test_suche_case_insensitive tests/test_bot.py::test_suche_is_known_command -v
```

Expected: 4 PASSED

- [ ] **Step 6: Run full test suite**

```
pytest tests/test_bot.py -v
```

Expected: all tests PASSED

- [ ] **Step 7: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add suche: dispatcher — search all 5 Notion DBs"
```

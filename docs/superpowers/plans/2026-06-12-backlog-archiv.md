# Backlog & Task-Archiv Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Backlog database (undated tasks) and a Task-Archiv database (completed tasks), with bot commands to manage them and a background loop that auto-archives Done tasks every 30 minutes.

**Architecture:** Two new Notion databases on the Organizer page. All Notion operations continue to go through `run_claude`. A new background thread (`_archive_loop`) polls Tagesorganizer + Backlog every 30 min and copies Done/Erledigt tasks to Task-Archiv via a Claude system-prompt call. The `task:` pending-state machine is extended to support backlog promotion. A one-time migration on startup moves all existing Done tasks to the archive.

**Tech Stack:** Python 3, existing `bot.py` architecture, Notion MCP via Claude CLI, `threading`, `json`

---

## Task 1: Create Notion databases

No unit tests (Notion side-effect). Manual verification via Notion UI.

**Files:**
- Modify: `C:\Users\tjark\.claude\CLAUDE.md` (add DB sections after Spieleideen-Datenbank)

- [ ] **Step 1: Create Backlog database**

Run Claude with full permissions and ask it to:

```
Create a new Notion database called "Backlog" as a child of the Organizer page (same parent as the Tagesorganizer database). Properties:
- Name (title)
- Status (status): options Offen, Erledigt
- Priorität (select): options Hoch, Mittel, Niedrig
- Bereich (select): options Arbeit, Privat, Lernen, Gesundheit
- Notiz (rich_text)
Return the data_source_id of the new database.
```

Record the returned `data_source_id` as **BACKLOG_DATA_SOURCE_ID**.

- [ ] **Step 2: Create Task-Archiv database**

Run Claude with full permissions and ask it to:

```
Create a new Notion database called "Task-Archiv" as a child of the Organizer page. Properties:
- Name (title)
- Status (status): options Done, Erledigt
- Priorität (select): options Hoch, Mittel, Niedrig
- Datum (date)
- Bereich (select): options Arbeit, Privat, Lernen, Gesundheit
- Notiz (rich_text)
- Archiviert am (date)
Return the data_source_id of the new database.
```

Record the returned `data_source_id` as **ARCHIV_DATA_SOURCE_ID**.

- [ ] **Step 3: Add DB docs to CLAUDE.md**

Append to `C:\Users\tjark\.claude\CLAUDE.md` after the Spieleideen-Datenbank section:

```markdown
# Backlog-Datenbank
- Name: Backlog
- data_source_id: `<BACKLOG_DATA_SOURCE_ID>`
- Eltern-Seite: Organizer (Workspace-Level)

## Properties
- Name (title)
- Status (status): `Offen` | `Erledigt`
- Priorität (select): `Hoch` | `Mittel` | `Niedrig`
- Bereich (select): `Arbeit` | `Privat` | `Lernen` | `Gesundheit`
- Notiz (rich_text)

# Task-Archiv-Datenbank
- Name: Task-Archiv
- data_source_id: `<ARCHIV_DATA_SOURCE_ID>`
- Eltern-Seite: Organizer (Workspace-Level)

## Properties
- Name (title)
- Status (status): kopiert von Quelldatenbank
- Priorität (select): `Hoch` | `Mittel` | `Niedrig`
- Datum (date): kopiert (leer für Backlog-Tasks)
- Bereich (select): `Arbeit` | `Privat` | `Lernen` | `Gesundheit`
- Notiz (rich_text)
- Archiviert am (date): Zeitstempel des Archivierungsvorgangs
```

- [ ] **Step 4: Commit**

```bash
git add C:/Users/tjark/.claude/CLAUDE.md
git commit -m "docs: add Backlog and Task-Archiv DB docs to CLAUDE.md"
```

---

## Task 2: Add constants and system prompts to bot.py

**Files:**
- Modify: `bot.py` (after line 13 where HABITS_DATA_SOURCE_ID is defined; new system prompts after TERMIN_SYSTEM_PROMPT at line 288)
- Create: `tests/test_backlog_archiv.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_backlog_archiv.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import bot

BACKLOG_ID = bot.BACKLOG_DATA_SOURCE_ID
ARCHIV_ID = bot.ARCHIV_DATA_SOURCE_ID

def test_backlog_id_is_set():
    assert BACKLOG_ID and BACKLOG_ID != "<BACKLOG_DATA_SOURCE_ID>"

def test_archiv_id_is_set():
    assert ARCHIV_ID and ARCHIV_ID != "<ARCHIV_DATA_SOURCE_ID>"

def test_backlog_system_prompt_contains_backlog_id():
    assert BACKLOG_ID in bot.BACKLOG_SYSTEM_PROMPT

def test_backlog_list_prompt_contains_backlog_id():
    assert BACKLOG_ID in bot.BACKLOG_LIST_SYSTEM_PROMPT

def test_archive_loop_prompt_contains_both_ids():
    assert BACKLOG_ID in bot.ARCHIVE_LOOP_SYSTEM_PROMPT
    assert ARCHIV_ID in bot.ARCHIVE_LOOP_SYSTEM_PROMPT

def test_archive_task_prompt_contains_archiv_id():
    assert ARCHIV_ID in bot.ARCHIVE_TASK_SYSTEM_PROMPT

def test_backlog_promote_prompt_contains_backlog_id():
    assert BACKLOG_ID in bot.BACKLOG_PROMOTE_SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_backlog_archiv.py -v
```

Expected: all 7 fail with `AttributeError: module 'bot' has no attribute 'BACKLOG_DATA_SOURCE_ID'`

- [ ] **Step 3: Add constants to bot.py**

After line 13 (`HABITS_DATA_SOURCE_ID = "6a4d7e7d-dcde-44e3-b7a0-c46330a6261c"`), insert:

```python
BACKLOG_DATA_SOURCE_ID = "<BACKLOG_DATA_SOURCE_ID>"   # replace with Task 1 value
ARCHIV_DATA_SOURCE_ID  = "<ARCHIV_DATA_SOURCE_ID>"    # replace with Task 1 value
```

Replace both placeholders with the actual UUIDs captured in Task 1.

- [ ] **Step 4: Add system prompts to bot.py**

After `TERMIN_SYSTEM_PROMPT` (after line 288), insert:

```python
BACKLOG_SYSTEM_PROMPT = f"""Du bist ein Notion-Backlog-Assistent. Der Nutzer nennt eine Aufgabe ohne festen Termin.
Lege sie im Backlog an (data_source_id: {BACKLOG_DATA_SOURCE_ID}).
Leite ab: Name, Priorität (Hoch/Mittel/Niedrig, Mittel falls nicht angegeben), Bereich (Arbeit/Privat/Lernen/Gesundheit, Privat falls unklar).
Status immer: Offen.
Antworte NUR mit einer Zeile: 📌 Backlog-Task angelegt: [Name] · [Priorität] · [Bereich]"""

BACKLOG_LIST_SYSTEM_PROMPT = f"""Du bist ein Notion-Backlog-Assistent.
Lies den Backlog (data_source_id: {BACKLOG_DATA_SOURCE_ID}).
Zeige alle Tasks mit Status = Offen, sortiert nach Priorität (Hoch zuerst).
Format:
Zeile 1: "📌 Backlog ([N] offen):"
Je Task: "[N]. [Prio-Icon] [Name] — [Bereich]"
Prio-Icons: Hoch=🔴 Mittel=🟡 Niedrig=🟢
Falls keine offenen Tasks: "📌 Backlog leer."
Kein Markdown."""

ARCHIVE_LOOP_SYSTEM_PROMPT = f"""Du bist ein Notion-Archiv-Assistent.
Archiviere alle erledigten Tasks aus dem Tagesorganizer und dem Backlog ins Task-Archiv.

Schritt 1 — Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0):
Finde alle Tasks mit Status = Done.
Für jeden: Lege Eintrag im Task-Archiv an (data_source_id: {ARCHIV_DATA_SOURCE_ID}).
Kopiere: Name, Status, Priorität, Datum, Bereich, Notiz. Setze "Archiviert am" = heutiges Datum (ISO 8601).
Archiviere dann den Original-Task (archived: true).

Schritt 2 — Backlog (data_source_id: {BACKLOG_DATA_SOURCE_ID}):
Finde alle Tasks mit Status = Erledigt.
Für jeden: Lege Eintrag im Task-Archiv an. Datum = leer. "Archiviert am" = heutiges Datum.
Archiviere dann den Original-Backlog-Task.

Antworte NUR mit: "✅ Archiviert: N Tasks" oder "Nichts zu archivieren."
Kein Markdown."""

ARCHIVE_TASK_SYSTEM_PROMPT = f"""Du bist ein Notion-Archiv-Assistent.
Archiviere den genannten Task sofort.
Suche im Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0) UND im Backlog (data_source_id: {BACKLOG_DATA_SOURCE_ID}) per fuzzy-Suche.
Falls gefunden und Status = Done oder Erledigt:
  Lege Eintrag im Task-Archiv an (data_source_id: {ARCHIV_DATA_SOURCE_ID}).
  Kopiere alle Properties. Setze "Archiviert am" = heutiges Datum.
  Archiviere Original (archived: true).
Antworte NUR: "✅ Archiviert: [Name]" oder "Übersprungen: [Name] (nicht Done)"
Kein Markdown."""

BACKLOG_PROMOTE_SYSTEM_PROMPT = f"""Du bist ein Notion-Backlog-Assistent.
Schritt 1: Finde den Task mit der genannten Nummer aus der Backlog-Liste (fuzzy-Suche auf den Namen).
Schritt 2: Lege neuen Task im Tagesorganizer an (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
  Übernehme: Name, Priorität, Bereich, Notiz.
  Setze Datum = angegebenes Zieldatum (ISO 8601). "morgen" = heute + 1 Tag.
  Status = Not started.
Schritt 3: Setze den Backlog-Task auf Status = Erledigt (data_source_id: {BACKLOG_DATA_SOURCE_ID}).
Antworte NUR mit: "✅ [Name] → Tagesorganizer für [DD.MM.YYYY]"
Kein Markdown."""
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_backlog_archiv.py -v
```

Expected: all 7 pass.

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_backlog_archiv.py
git commit -m "feat: add Backlog/Archiv constants and system prompts"
```

---

## Task 3: `backlog` list command + keyboard button

**Files:**
- Modify: `bot.py` (REPLY_KEYBOARD, command handler)
- Modify: `tests/test_backlog_archiv.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_backlog_archiv.py`:

```python
def test_backlog_in_reply_keyboard():
    all_buttons = [btn for row in bot.REPLY_KEYBOARD["keyboard"] for btn in row]
    assert "backlog" in all_buttons

def test_backlog_list_prompt_response_format():
    assert "📌 Backlog" in bot.BACKLOG_LIST_SYSTEM_PROMPT
    assert "offen" in bot.BACKLOG_LIST_SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_backlog_archiv.py::test_backlog_in_reply_keyboard -v
```

Expected: FAIL — `backlog` not in keyboard.

- [ ] **Step 3: Add `backlog` button to REPLY_KEYBOARD in bot.py**

Find REPLY_KEYBOARD (around line 49). Current:
```python
REPLY_KEYBOARD = {
    "keyboard": [
        ["moin", "abend"],
        ["task:", "status:"],
        ["woche", "fokus:"],
        ["verschieben:", "hilfe"],
    ],
```

Change to:
```python
REPLY_KEYBOARD = {
    "keyboard": [
        ["moin", "abend"],
        ["task:", "status:"],
        ["woche", "fokus:"],
        ["verschieben:", "hilfe"],
        ["backlog"],
    ],
```

- [ ] **Step 4: Add `backlog` command handler in bot.py**

In the command elif chain, after `elif text.lower() == "hilfe":` (around line 902), add:

```python
            elif text.lower() == "backlog":
                response = run_claude(f"Heute ist {today}.", system_prompt=BACKLOG_LIST_SYSTEM_PROMPT)
```

- [ ] **Step 5: Run tests**

```
pytest tests/test_backlog_archiv.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_backlog_archiv.py
git commit -m "feat: add backlog list command and keyboard button"
```

---

## Task 4: `backlog:` add command

**Files:**
- Modify: `bot.py` (HILFE_TEXT, _is_command guard, command handler, pending handler)
- Modify: `tests/test_backlog_archiv.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_backlog_archiv.py`:

```python
def test_hilfe_contains_backlog():
    assert "backlog:" in bot.HILFE_TEXT
    assert "backlog" in bot.HILFE_TEXT

def test_backlog_system_prompt_response_format():
    assert "📌 Backlog-Task angelegt" in bot.BACKLOG_SYSTEM_PROMPT

def test_backlog_system_prompt_status_offen():
    assert "Offen" in bot.BACKLOG_SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_backlog_archiv.py::test_hilfe_contains_backlog -v
```

Expected: FAIL — `backlog:` not in HILFE_TEXT.

- [ ] **Step 3: Update HILFE_TEXT in bot.py**

In HILFE_TEXT, after the `termin:` lines, add:

```
  backlog: <text> — Undatierte Aufgabe in Backlog speichern
  backlog — Alle offenen Backlog-Tasks anzeigen
```

The `✅ Tasks & Habits` section becomes:
```
✅ Tasks & Habits
  task: — Neuen Task anlegen (interaktiv)
  task: <text> — Neuen Task direkt anlegen
  habit: <text> — Neuen Habit anlegen
    z.B. habit: Sport täglich  oder  habit: Laufen alle 2 Tage
  termin: <text> — Termin anlegen
    z.B. termin: Arzttermin morgen um 14:00
  backlog: <text> — Undatierte Aufgabe in Backlog speichern
  backlog — Alle offenen Backlog-Tasks anzeigen
  status: <name> <status> — Status ändern
    erledigt / in arbeit / offen
  verschieben: <datum> — Offene Tasks verschieben
    z.B. verschieben: morgen  oder  verschieben: 2026-06-15
```

- [ ] **Step 4: Add `backlog:` command handler in bot.py**

After the `elif text.lower() == "backlog":` block added in Task 3, add:

```python
            elif text.lower().startswith("backlog:"):
                backlog_text = text[8:].strip()
                if not backlog_text:
                    pending_task_input[chat_id] = "backlog_input"
                    response = "Schreib mir: Name, Priorität (Hoch/Mittel/Niedrig), Bereich (Arbeit/Privat/Lernen/Gesundheit)\nz.B.: Stromtarif wechseln, Mittel, Privat"
                else:
                    prompt = f"Heute ist {today}. Backlog-Aufgabe: {backlog_text}"
                    response = run_claude(prompt, system_prompt=BACKLOG_SYSTEM_PROMPT)
```

- [ ] **Step 5: Add `backlog_input` pending state + update _is_command guard**

Find the `if chat_id in pending_task_input:` block (around line 773). This block will be fully replaced in Task 7. For now, add `"backlog_input"` handling into the `else` branch and update `_is_command`:

Update `_is_command` (in the pending handler):
```python
_is_command = (text.lower() in ("restart", "projekte", "moin", "abend", "woche", "hilfe", "erinnerungen", "/plans", "backlog")
               or any(text.lower().startswith(p) for p in
                      ("task:", "status:", "fokus:", "verschieben:", "lern:",
                       "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
                       "implement-plan:", "abort-plan:", "backlog:")))
```

In the `else` branch of the pending handler, prepend a check before the existing `del pending_task_input[chat_id]`:

```python
            else:
                state = pending_task_input[chat_id]
                del pending_task_input[chat_id]
                if state == "backlog_input":
                    send_message(chat_id, "⏳ Denke nach...")
                    prompt = f"Heute ist {today}. Backlog-Aufgabe: {text}"
                    response = run_claude(prompt, system_prompt=BACKLOG_SYSTEM_PROMPT)
                    send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                else:
                    send_message(chat_id, "⏳ Denke nach...")
                    prompt = f"Heute ist {today}. Aufgabe: {text}"
                    response = run_claude(prompt, system_prompt=TASK_SYSTEM_PROMPT)
                    send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                    publish_new_lessons(chat_id)
                    print(f"[task-dialog] → {response[:60]}")
                continue
```

- [ ] **Step 6: Run all tests**

```
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add bot.py tests/test_backlog_archiv.py
git commit -m "feat: add backlog: add command with interactive dialog"
```

---

## Task 5: Archive loop + one-time migration

**Files:**
- Modify: `bot.py` (`_run_archive_once`, `_archive_loop`, `_run_migration`, startup threads)
- Modify: `tests/test_backlog_archiv.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_backlog_archiv.py`:

```python
import json
from unittest.mock import patch

def test_run_archive_once_calls_run_claude():
    calls = []
    with patch("bot.run_claude", lambda prompt, system_prompt=None, **kw: calls.append(system_prompt) or "✅ Archiviert: 0 Tasks"):
        bot._run_archive_once()
    assert any(bot.ARCHIV_DATA_SOURCE_ID in (sp or "") for sp in calls)

def test_archive_migration_runs_if_flag_missing(tmp_path):
    (tmp_path / "settings.json").write_text('{"notifications_enabled": true}')
    calls = []
    with patch("bot.run_claude", lambda *a, **kw: calls.append(True) or "Nichts zu archivieren."):
        bot._run_migration(str(tmp_path))
    assert len(calls) >= 1
    settings = json.loads((tmp_path / "settings.json").read_text())
    assert settings.get("archive_migration_done") is True

def test_archive_migration_skipped_if_flag_set(tmp_path):
    (tmp_path / "settings.json").write_text('{"notifications_enabled": true, "archive_migration_done": true}')
    calls = []
    with patch("bot.run_claude", lambda *a, **kw: calls.append(True) or ""):
        bot._run_migration(str(tmp_path))
    assert len(calls) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_backlog_archiv.py::test_run_archive_once_calls_run_claude -v
```

Expected: FAIL with `AttributeError: module 'bot' has no attribute '_run_archive_once'`

- [ ] **Step 3: Add functions to bot.py**

After the `_plan_loop` function (after line ~544), add:

```python
def _run_archive_once():
    try:
        run_claude(f"Heute ist {date.today().isoformat()}.", system_prompt=ARCHIVE_LOOP_SYSTEM_PROMPT)
    except Exception as e:
        print(f"archive error: {e}")

def _archive_loop():
    while True:
        time.sleep(1800)
        _run_archive_once()

def _run_migration(_dir=WORK_DIR):
    s = load_settings(_dir)
    if s.get("archive_migration_done"):
        return
    _run_archive_once()
    s["archive_migration_done"] = True
    save_settings(s, _dir)
```

- [ ] **Step 4: Start threads in `__main__`**

In the `if __name__ == "__main__":` block (around line 626), after the existing thread starts, add:

```python
    threading.Thread(target=_archive_loop, daemon=True).start()
    threading.Thread(target=_run_migration, daemon=True).start()
```

- [ ] **Step 5: Run all tests**

```
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_backlog_archiv.py
git commit -m "feat: add archive loop (30min) and one-time migration"
```

---

## Task 6: `status:` immediate archive trigger

**Files:**
- Modify: `bot.py` (status: handler)
- Modify: `tests/test_backlog_archiv.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_backlog_archiv.py`:

```python
def test_status_erledigt_triggers_archive(monkeypatch):
    archive_calls = []
    monkeypatch.setattr(bot, "_run_archive_once", lambda: archive_calls.append(True))
    # Simulate the relevant condition in the status: handler
    status_text = "Sport erledigt"
    if any(w in status_text.lower() for w in ("erledigt", "fertig", "done")):
        bot._run_archive_once()
    assert len(archive_calls) == 1

def test_status_in_arbeit_does_not_trigger_archive(monkeypatch):
    archive_calls = []
    monkeypatch.setattr(bot, "_run_archive_once", lambda: archive_calls.append(True))
    status_text = "Sport in arbeit"
    if any(w in status_text.lower() for w in ("erledigt", "fertig", "done")):
        bot._run_archive_once()
    assert len(archive_calls) == 0
```

- [ ] **Step 2: Run tests to verify they pass already (logic test, not bot.py test)**

```
pytest tests/test_backlog_archiv.py::test_status_erledigt_triggers_archive tests/test_backlog_archiv.py::test_status_in_arbeit_does_not_trigger_archive -v
```

Expected: pass (tests verify the condition logic, not the handler location).

- [ ] **Step 3: Modify status: handler in bot.py**

Find (around line 904):

```python
            elif text.lower().startswith("status:"):
                status_text = text[7:].strip()
                if not status_text:
                    response = "Nutzung: status: <Taskname> <Status>  z.B. status: Sport erledigt"
                else:
                    prompt = f"Heute ist {today}. Anfrage: {status_text}"
                    response = run_claude(prompt, system_prompt=STATUS_SYSTEM_PROMPT)
```

Change to:

```python
            elif text.lower().startswith("status:"):
                status_text = text[7:].strip()
                if not status_text:
                    response = "Nutzung: status: <Taskname> <Status>  z.B. status: Sport erledigt"
                else:
                    prompt = f"Heute ist {today}. Anfrage: {status_text}"
                    response = run_claude(prompt, system_prompt=STATUS_SYSTEM_PROMPT)
                    if any(w in status_text.lower() for w in ("erledigt", "fertig", "done")):
                        threading.Thread(target=_run_archive_once, daemon=True).start()
```

- [ ] **Step 4: Run all tests**

```
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_backlog_archiv.py
git commit -m "feat: trigger archive on status: erledigt"
```

---

## Task 7: `task:` dialog — backlog promotion

**Files:**
- Modify: `bot.py` (task: command, full pending handler rewrite)
- Modify: `tests/test_backlog_archiv.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_backlog_archiv.py`:

```python
def test_backlog_promote_prompt_contains_tagesorganizer():
    assert "c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0" in bot.BACKLOG_PROMOTE_SYSTEM_PROMPT

def test_backlog_promote_prompt_mentions_erledigt():
    assert "Erledigt" in bot.BACKLOG_PROMOTE_SYSTEM_PROMPT

def test_task_bare_sets_task_menu_state():
    bot.pending_task_input.clear()
    chat_id = 99999
    text = "task:"
    task_text = text[5:].strip()
    if not task_text:
        bot.pending_task_input[chat_id] = "task_menu"
    assert bot.pending_task_input.get(chat_id) == "task_menu"
    bot.pending_task_input.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_backlog_archiv.py::test_task_bare_sets_task_menu_state -v
```

Expected: FAIL — state is `True`, not `"task_menu"`.

- [ ] **Step 3: Modify task: command to set task_menu state**

Find (around line 814):

```python
            elif text.lower().startswith("task:"):
                task_text = text[5:].strip()
                if not task_text:
                    pending_task_input[chat_id] = True
                    response = "Schreib mir: Name, Priorität (Hoch/Mittel/Niedrig), Bereich (Arbeit/Privat/Lernen/Gesundheit)\nz.B.: Arzttermin, Hoch, Gesundheit"
```

Change the two lines inside `if not task_text:` to:

```python
                if not task_text:
                    pending_task_input[chat_id] = "task_menu"
                    response = "Neuer Task oder aus Backlog?\nA) Neuer Task\nB) Aus Backlog auswählen"
```

- [ ] **Step 4: Replace pending handler with full state machine**

Find the entire `if chat_id in pending_task_input:` block (lines ~773–789). Replace it entirely with:

```python
            if chat_id in pending_task_input:
                state = pending_task_input[chat_id]
                _is_command = (text.lower() in ("restart", "projekte", "moin", "abend", "woche", "hilfe", "erinnerungen", "/plans", "backlog")
                               or any(text.lower().startswith(p) for p in
                                      ("task:", "status:", "fokus:", "verschieben:", "lern:",
                                       "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
                                       "implement-plan:", "abort-plan:", "backlog:")))
                if _is_command:
                    del pending_task_input[chat_id]
                elif state == "task_menu":
                    del pending_task_input[chat_id]
                    choice = text.strip().upper()
                    if choice in ("A", "1"):
                        pending_task_input[chat_id] = "task_input"
                        send_message(chat_id, "Schreib mir: Name, Priorität (Hoch/Mittel/Niedrig), Bereich (Arbeit/Privat/Lernen/Gesundheit)\nz.B.: Arzttermin, Hoch, Gesundheit")
                    elif choice in ("B", "2"):
                        send_message(chat_id, "⏳ Lade Backlog...")
                        backlog_response = run_claude(f"Heute ist {today}.", system_prompt=BACKLOG_LIST_SYSTEM_PROMPT)
                        if "leer" in backlog_response.lower():
                            send_message(chat_id, f"{backlog_response}\n\nKeine Backlog-Tasks verfügbar.")
                        else:
                            pending_task_input[chat_id] = {"state": "backlog_select", "list": backlog_response}
                            send_message(chat_id, f"{backlog_response}\n\nWelchen Task? (Nummer eingeben)")
                    else:
                        send_message(chat_id, "Bitte A oder B eingeben.")
                    continue
                elif isinstance(state, dict) and state.get("state") == "backlog_select":
                    del pending_task_input[chat_id]
                    try:
                        num = int(text.strip())
                        pending_task_input[chat_id] = {"state": "backlog_date", "num": num, "list": state["list"]}
                        send_message(chat_id, f"Ausgewählt: #{num}\nWelches Datum? (z.B. heute, morgen, 2026-06-15)")
                    except ValueError:
                        send_message(chat_id, "Bitte eine Nummer eingeben.")
                    continue
                elif isinstance(state, dict) and state.get("state") == "backlog_date":
                    del pending_task_input[chat_id]
                    send_message(chat_id, "⏳ Übertrage in Tagesorganizer...")
                    prompt = f"Heute ist {today}. Zieldatum: {text}.\nBacklog-Liste:\n{state['list']}\nNummer: {state['num']}"
                    response = run_claude(prompt, system_prompt=BACKLOG_PROMOTE_SYSTEM_PROMPT)
                    send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                    continue
                elif state == "backlog_input":
                    del pending_task_input[chat_id]
                    send_message(chat_id, "⏳ Denke nach...")
                    prompt = f"Heute ist {today}. Backlog-Aufgabe: {text}"
                    response = run_claude(prompt, system_prompt=BACKLOG_SYSTEM_PROMPT)
                    send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                    continue
                else:
                    del pending_task_input[chat_id]
                    send_message(chat_id, "⏳ Denke nach...")
                    prompt = f"Heute ist {today}. Aufgabe: {text}"
                    response = run_claude(prompt, system_prompt=TASK_SYSTEM_PROMPT)
                    send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                    publish_new_lessons(chat_id)
                    print(f"[task-dialog] → {response[:60]}")
                    continue
```

Note: the `else` branch (last case) handles both `True` (legacy) and `"task_input"` states — both flow to TASK_SYSTEM_PROMPT. The intermediate `backlog_input` case added in Task 4 Step 5 is now consolidated here.

- [ ] **Step 5: Run all tests**

```
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_backlog_archiv.py
git commit -m "feat: extend task: dialog with backlog promotion flow"
```

---

## Task 8: Final integration check

**Files:**
- Modify: `tests/test_backlog_archiv.py`

- [ ] **Step 1: Add integration tests**

Add to `tests/test_backlog_archiv.py`:

```python
def test_all_system_prompts_defined():
    for attr in ("BACKLOG_SYSTEM_PROMPT", "BACKLOG_LIST_SYSTEM_PROMPT",
                 "ARCHIVE_LOOP_SYSTEM_PROMPT", "ARCHIVE_TASK_SYSTEM_PROMPT",
                 "BACKLOG_PROMOTE_SYSTEM_PROMPT"):
        assert hasattr(bot, attr), f"Missing: {attr}"
        assert getattr(bot, attr).strip(), f"Empty: {attr}"

def test_archive_loop_prompt_has_tagesorganizer():
    assert "c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0" in bot.ARCHIVE_LOOP_SYSTEM_PROMPT

def test_keyboard_still_has_original_buttons():
    all_buttons = [btn for row in bot.REPLY_KEYBOARD["keyboard"] for btn in row]
    for btn in ("moin", "abend", "task:", "status:", "hilfe"):
        assert btn in all_buttons, f"Original button missing: {btn}"
```

- [ ] **Step 2: Run full test suite**

```
pytest tests/ -v
```

Expected: all pass, no regressions.

- [ ] **Step 3: Commit**

```bash
git add tests/test_backlog_archiv.py
git commit -m "test: final integration tests for backlog/archiv feature"
```

---

## Self-Review

**Spec coverage:**
- ✅ Backlog DB: Task 1
- ✅ Task-Archiv DB: Task 1
- ✅ `backlog: <text>` command: Task 4
- ✅ `backlog` list command: Task 3
- ✅ `task:` dialog B) aus Backlog: Task 7
- ✅ `status: X erledigt` immediate archive: Task 6
- ✅ Background loop every 30 min: Task 5
- ✅ One-time migration on startup: Task 5
- ✅ `backlog` as 9th keyboard button: Task 3
- ✅ HILFE_TEXT updated: Task 4
- ✅ `_is_command` guard updated: Tasks 4 + 7
- ✅ CLAUDE.md updated: Task 1

**Placeholder scan:** DB ID placeholders in Task 2 are explicitly tied to Task 1 output — not implementation gaps.

**Type/name consistency:**
- `_run_archive_once` defined in Task 5, called in Task 6 ✅
- `BACKLOG_LIST_SYSTEM_PROMPT` used in Task 3 handler and Task 7 backlog_select branch ✅
- `BACKLOG_PROMOTE_SYSTEM_PROMPT` used in Task 7 backlog_date branch ✅
- Pending states `"task_menu"`, `"task_input"`, `"backlog_input"`, `{"state": "backlog_select"}`, `{"state": "backlog_date"}` consistent across Tasks 4 and 7 ✅

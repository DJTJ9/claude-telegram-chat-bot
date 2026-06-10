# Habits-System, task: Dialog, status: erledigt — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add recurring Habits to Notion, interactive two-step `task:` creation, and `status: X erledigt` with Habit recurrence logic.

**Architecture:** All Notion operations remain Claude-via-MCP (no direct API calls). A new "Habits" Notion DB is created once and its `data_source_id` is hardcoded in `bot.py`. A new `pending_task_input` dict tracks two-step `task:` dialog state per chat_id. System prompts for MOIN and STATUS are extended to include the Habits DB.

**Tech Stack:** Python 3, python-telegram-bot (polling), Anthropic Claude CLI, Notion MCP

---

## File Structure

Only `bot.py` and `tests/test_bot.py` change. No new files.

| File | Changes |
|---|---|
| `bot.py` | Add `HABITS_DATA_SOURCE_ID` constant, `HABIT_SYSTEM_PROMPT`, `pending_task_input` dict, update `MOIN_SYSTEM_PROMPT`/`STATUS_SYSTEM_PROMPT`/`HILFE_TEXT`, add `habit:` routing, update `task:` routing, update voice initial_prompt |
| `tests/test_bot.py` | Add tests for `habit:` prefix, pending state, updated hilfe coverage |

---

## Task 1: Create Habits Notion Database

**Files:**
- No code changes yet — one-time setup step

- [ ] **Step 1: Run the DB creation command**

Run this in the project directory:

```powershell
claude --dangerously-skip-permissions -p "Erstelle eine neue Notion-Datenbank namens 'Habits' als Unterseite der Organizer-Seite (page_id: 37a4bba2-9c55-8074-93bd-f21e2ef34a9e). Properties: Name (title), Intervall (number), Bereich (select: Arbeit/Privat/Lernen/Gesundheit), Nächste Fälligkeit (date), Status (status: Aktiv/Pausiert). Gib mir die data_source_id der erstellten Datenbank."
```

- [ ] **Step 2: Note the returned data_source_id**

Claude returns something like: `data_source_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

Copy this value — it is `HABITS_DATA_SOURCE_ID` used in all later tasks.

- [ ] **Step 3: Add constant to bot.py**

In `bot.py`, after line 7 (`MY_CHAT_ID = 8896609541`), add:

```python
HABITS_DATA_SOURCE_ID = "PASTE_ID_HERE"  # replace with actual ID from Step 2
```

- [ ] **Step 4: Commit**

```bash
git add bot.py
git commit -m "feat: add HABITS_DATA_SOURCE_ID constant for new Habits Notion DB"
```

---

## Task 2: Add HABIT_SYSTEM_PROMPT and `habit:` routing

**Files:**
- Modify: `bot.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bot.py`:

```python
def test_habit_prefix_detection():
    text = "habit: Sport täglich"
    assert text.lower().startswith("habit:")
    assert text[6:].strip() == "Sport täglich"

def test_habit_prefix_empty():
    text = "habit:"
    assert text[6:].strip() == ""

def test_hilfe_contains_habit():
    assert "habit:" in HILFE_TEXT
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_bot.py::test_hilfe_contains_habit -v
```

Expected: FAIL (`habit:` not yet in `HILFE_TEXT`).

- [ ] **Step 3: Add HABIT_SYSTEM_PROMPT to bot.py**

After the `IDEE_SYSTEM_PROMPT` block (around line 162), add (paste the actual `HABITS_DATA_SOURCE_ID` UUID in place of `PASTE_HABITS_ID_HERE`):

```python
HABIT_SYSTEM_PROMPT = """Du bist ein Habit-Assistent. Der Nutzer beschreibt einen wiederkehrenden Habit.
Lege ihn in der Habits-Datenbank an (data_source_id: PASTE_HABITS_ID_HERE).
Leite aus dem Text ab:
- Name: kurzer Titel des Habits
- Intervall: Anzahl Tage als Zahl (täglich=1, wöchentlich=7, alle N Tage=N)
- Bereich: Arbeit/Privat/Lernen/Gesundheit (leer lassen falls nicht angegeben)
- Nächste Fälligkeit: das heutige Datum (aus dem Nutzer-Prompt)
- Status: Aktiv
Antworte NUR mit einer Zeile: 🔄 Habit angelegt: [Name] · alle [Intervall] Tage · ab heute"""
```

- [ ] **Step 4: Add `habit:` routing in the main elif chain**

In `bot.py`, find the `elif text.lower().startswith("idee:"):` block. After it, add:

```python
            elif text.lower().startswith("habit:"):
                habit_text = text[6:].strip()
                if not habit_text:
                    response = "Nutzung: habit: <Habit>  z.B. habit: Sport täglich  oder  habit: Laufen alle 2 Tage"
                else:
                    prompt = f"Heute ist {today}. Habit: {habit_text}"
                    response = run_claude(prompt, system_prompt=HABIT_SYSTEM_PROMPT)
```

- [ ] **Step 5: Update HILFE_TEXT**

Replace the entire `HILFE_TEXT` string in `bot.py` with:

```python
HILFE_TEXT = """📋 Befehle:

🌅 Tagesplanung
  moin — Tasks + fällige Habits für heute
  abend — Tagesabschluss
  woche — Wochenrückblick
  fokus: <Bereich> — Arbeit / Privat / Lernen / Gesundheit

✅ Tasks & Habits
  task: — Neuen Task anlegen (interaktiv)
  task: <text> — Neuen Task direkt anlegen
  habit: <text> — Neuen Habit anlegen
    z.B. habit: Sport täglich  oder  habit: Laufen alle 2 Tage
  status: <name> <status> — Status ändern
    erledigt / in arbeit / offen
  verschieben: <datum> — Offene Tasks verschieben
    z.B. verschieben: morgen  oder  verschieben: 2026-06-15

📁 Projekte
  projekte — Alle Projekte anzeigen
  <name>: <frage> — Im Projektkontext fragen
  <name>: tasks — Projekt-Tasks anzeigen
  <name>: task: <text> — Projekt-Task anlegen

📚 Listen
  lern: <thema> — Lernthema speichern
  idee: <text> — Spielidee speichern

🛠 Sonstiges
  teach: <text> — Lernkurs erstellen
  restart — Bot neu starten"""
```

- [ ] **Step 6: Run tests to verify they pass**

```powershell
python -m pytest tests/test_bot.py -v
```

Expected: all tests PASS including `test_hilfe_contains_habit`.

- [ ] **Step 7: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add habit: command and HABIT_SYSTEM_PROMPT"
```

---

## Task 3: Update MOIN_SYSTEM_PROMPT with Habits section

**Files:**
- Modify: `bot.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bot.py`:

```python
from bot import MOIN_SYSTEM_PROMPT, HABITS_DATA_SOURCE_ID

def test_moin_prompt_includes_habits_db():
    assert HABITS_DATA_SOURCE_ID in MOIN_SYSTEM_PROMPT

def test_moin_prompt_includes_habits_section():
    assert "Habits heute" in MOIN_SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_bot.py::test_moin_prompt_includes_habits_db tests/test_bot.py::test_moin_prompt_includes_habits_section -v
```

Expected: both FAIL.

- [ ] **Step 3: Update MOIN_SYSTEM_PROMPT in bot.py**

Replace the existing `MOIN_SYSTEM_PROMPT` string with an f-string (note the `f` prefix). `HABITS_DATA_SOURCE_ID` must be defined earlier in the file (Task 1 ensures this):

```python
MOIN_SYSTEM_PROMPT = f"""Du bist ein Notion-Morgen-Assistent.
Lies den Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Zeige alle Tasks mit Datum = heute ODER ohne Datum, Status Not started oder In progress.

Format:
Zeile 1: "🌅 Guten Morgen! [N] Tasks heute"
Zeile 2 (nur wenn Projekt-Tasks vorhanden): "📁 " + je Projekt "[Name] ([N])" mit " · " getrennt
Leerzeile
Je Task: "· [Prio-Icon] [→Projekt falls gesetzt] [Name]"
Prio-Icons: Hoch=🔴 Mittel=🟡 Niedrig=🟢
Sortiere nach Priorität (Hoch zuerst), dann alphabetisch.

Dann lies die Habits-Datenbank (data_source_id: {HABITS_DATA_SOURCE_ID}).
Zeige alle Habits mit Nächste Fälligkeit ≤ heute UND Status = Aktiv.
Falls solche Habits vorhanden:
  Leerzeile
  Zeile: "🔄 Habits heute ([N]):"
  Je Habit: "· [Name] (alle [Intervall] Tage)"
Falls keine fälligen Habits: diese Sektion weglassen.

Kein Markdown. Kein Datum in der Task-Liste."""
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_bot.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add Habits section to moin/Morgen-Workflow"
```

---

## Task 4: Update STATUS_SYSTEM_PROMPT for Habit recurrence

**Files:**
- Modify: `bot.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bot.py`:

```python
from bot import STATUS_SYSTEM_PROMPT

def test_status_prompt_includes_habits_db():
    assert HABITS_DATA_SOURCE_ID in STATUS_SYSTEM_PROMPT

def test_status_prompt_includes_recurrence_logic():
    assert "Nächste Fälligkeit" in STATUS_SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_bot.py::test_status_prompt_includes_habits_db tests/test_bot.py::test_status_prompt_includes_recurrence_logic -v
```

Expected: both FAIL.

- [ ] **Step 3: Update STATUS_SYSTEM_PROMPT in bot.py**

Replace the existing `STATUS_SYSTEM_PROMPT` with an f-string:

```python
STATUS_SYSTEM_PROMPT = f"""Du bist ein Notion-Status-Assistent.

Schritt 1 — Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0):
Finde den Task per fuzzy-Suche (Name muss nicht exakt übereinstimmen).
Mappe den Status:
  erledigt / fertig / done → Done
  in arbeit / läuft / gestartet / in progress → In progress
  offen / zurück / nicht gestartet → Not started
Setze den Status. Merke ob ein Task gefunden wurde.

Schritt 2 — Habits-DB (data_source_id: {HABITS_DATA_SOURCE_ID}):
Nur ausführen falls "erledigt" oder "done" im Text.
Finde den Habit per fuzzy-Suche.
Falls gefunden:
  - Setze Status → Done
  - Berechne Nächste Fälligkeit = heutiges Datum + Intervall (Tage, aus Property "Intervall")
  - Setze Status zurück → Aktiv
Merke ob ein Habit gefunden wurde.

Antworte:
- Nur Task gefunden: "✅ [Task Name] → [Status]"
- Nur Habit gefunden: "🔄 Habit '[Name]' erledigt — nächste Fälligkeit: [Datum DD.MM.YYYY]"
- Beides gefunden: beide Zeilen
- Nichts gefunden: "❌ Kein passender Task/Habit gefunden: \\"[Eingabe]\\""
Kein Markdown."""
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_bot.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: update status: to handle habit recurrence (Nächste Fälligkeit)"
```

---

## Task 5: Add `task:` interactive dialog

**Files:**
- Modify: `bot.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bot.py`:

```python
from bot import pending_task_input

def test_pending_task_input_is_dict():
    assert isinstance(pending_task_input, dict)

def test_task_bare_command_detection():
    text = "task:"
    assert text.lower().startswith("task:")
    assert text[5:].strip() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_bot.py::test_pending_task_input_is_dict -v
```

Expected: FAIL (`cannot import name 'pending_task_input' from 'bot'`).

- [ ] **Step 3: Add pending_task_input dict to bot.py**

After the `conversation_history = {}` line, add:

```python
pending_task_input = {}
```

- [ ] **Step 4: Add pending state check to main loop**

In the main `while True:` loop, find this block (around line 380):

```python
            if text.lower() == "projekte":
                lines = ["📁 Verfügbare Projekte:"]
                for name, info in PROJECTS.items():
                    lines.append(f"  {name}: → {info['path']}")
                lines.append("\nNutzung: <name>: <frage>  |  <name>: tasks  |  <name>: task: <aufgabe>")
                send_message(chat_id, "\n".join(lines))
                continue

            send_message(chat_id, "⏳ Denke nach...")
```

Insert the pending check between `projekte` and `"⏳ Denke nach..."`:

```python
            if text.lower() == "projekte":
                lines = ["📁 Verfügbare Projekte:"]
                for name, info in PROJECTS.items():
                    lines.append(f"  {name}: → {info['path']}")
                lines.append("\nNutzung: <name>: <frage>  |  <name>: tasks  |  <name>: task: <aufgabe>")
                send_message(chat_id, "\n".join(lines))
                continue

            if chat_id in pending_task_input:
                del pending_task_input[chat_id]
                send_message(chat_id, "⏳ Denke nach...")
                prompt = f"Heute ist {today}. Aufgabe: {text}"
                response = run_claude(prompt, system_prompt=TASK_SYSTEM_PROMPT)
                send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                publish_new_lessons(chat_id)
                print(f"[task-dialog] → {response[:60]}")
                continue

            send_message(chat_id, "⏳ Denke nach...")
```

- [ ] **Step 5: Update `task:` handler to set pending state on bare command**

Find the `elif text.lower().startswith("task:"):` block. Replace the `if not task_text:` branch:

```python
            elif text.lower().startswith("task:"):
                task_text = text[5:].strip()
                if not task_text:
                    pending_task_input[chat_id] = True
                    response = "Schreib mir: Name, Priorität (Hoch/Mittel/Niedrig), Bereich (Arbeit/Privat/Lernen/Gesundheit)\nz.B.: Arzttermin, Hoch, Gesundheit"
                else:
                    prompt = f"Heute ist {today}. Aufgabe: {task_text}"
                    response = run_claude(prompt, system_prompt=TASK_SYSTEM_PROMPT, cwd=project_cwd)
```

- [ ] **Step 6: Update voice initial_prompt to include `habit:`**

Find `transcribe_voice` function, update the `prompt=` line inside `create()`:

```python
                prompt="task: erledigt: status: fokus: lern: idee: habit: verschieben:",
```

- [ ] **Step 7: Run all tests**

```powershell
python -m pytest tests/test_bot.py -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add task: interactive two-step dialog with pending state"
```

---

## Self-Review

**Spec coverage:**
- ✅ Habits DB created (Task 1)
- ✅ `habit:` command with Claude parsing (Task 2)
- ✅ Habits in Morgen-Workflow (Task 3)
- ✅ `status: erledigt` recurrence logic (Task 4)
- ✅ `task:` interactive dialog with pending state (Task 5)
- ✅ Defaults: Datum=heute, Prio=Mittel — handled by existing `TASK_SYSTEM_PROMPT`
- ✅ HILFE_TEXT updated (Task 2 Step 5)
- ✅ Voice initial_prompt updated (Task 5 Step 6)

**Dependency note:** Tasks 2–5 all use `HABITS_DATA_SOURCE_ID`. Complete Task 1 before the others.

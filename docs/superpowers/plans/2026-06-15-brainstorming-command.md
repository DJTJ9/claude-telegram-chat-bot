# brainstorming: Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `brainstorming:` Telegram command that launches a full headless brainstorming session (spec → plan → scheduling) with VISION.md context persistence and a `/specs` listing command.

**Architecture:** Single-file change to `bot.py`. Mirrors the existing `_run_teach` pattern: global concurrency flag + daemon-thread subprocess function + message handler. `/specs` is a pure filesystem listing, no subprocess. `VISION.md` is created/maintained by the Claude subprocess, not by bot.py.

**Tech Stack:** Python 3, `subprocess`, `threading`, `pathlib`, existing `claude --dangerously-skip-permissions` pattern, `pytest`

---

## File Map

| File | Change |
|------|--------|
| `bot.py` | Add `_brainstorming_active` flag, `_run_brainstorming()`, `brainstorming:` handler, `/specs` handler, update `HILFE_TEXT`, update `_is_command` guard |
| `tests/test_bot.py` | Add tests for `/specs` listing, `brainstorming:` parsing, `HILFE_TEXT` coverage |

---

## Task 1: Add `_brainstorming_active` flag and `_run_brainstorming()` to bot.py

**Files:**
- Modify: `bot.py` (after `_run_teach`, around line 632)

- [ ] **Step 1: Add the global flag just before `_run_teach`**

In `bot.py`, find the line `def _run_teach(topic):` (around line 617). Insert immediately before it:

```python
_brainstorming_active = False
```

- [ ] **Step 2: Add `_run_brainstorming()` after `_run_teach`**

After the closing line of `_run_teach` (the `send_message` line, around line 631), insert:

```python
def _run_brainstorming(topic, basis_slug=None):
    global _brainstorming_active
    safe_topic = topic[:500]
    vision_path = Path(WORK_DIR) / "VISION.md"
    vision_note = (
        f"Read {vision_path} first for existing project context and backlog."
        if vision_path.exists() else ""
    )
    basis_note = (
        f"Also read the spec file in docs/superpowers/specs/ whose name contains '{basis_slug}' "
        f"as prior session context before starting brainstorming."
        if basis_slug else ""
    )
    prompt = (
        f"Invoke the superpowers:brainstorming skill. "
        f"Feature idea from user: {safe_topic}. "
        f"{vision_note} {basis_note}"
        f"Use telegram relay for ALL questions and gate decisions "
        f"(notifications_enabled is true — do not output anything to terminal). "
        f"After the spec and plan are written and committed, update VISION.md in {WORK_DIR}: "
        f"add the new feature under Implementiert, move any collected-but-not-chosen ideas to Backlog, "
        f"record key decisions under Entscheidungen."
    )
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            timeout=7200, cwd=WORK_DIR, env=env
        )
        success = result.returncode == 0
        if success:
            send_message(MY_CHAT_ID, "✅ Brainstorming abgeschlossen")
        else:
            send_message(MY_CHAT_ID, f"❌ Brainstorming fehlgeschlagen\n{(result.stderr or '')[-300:]}")
    except subprocess.TimeoutExpired:
        send_message(MY_CHAT_ID, "❌ Brainstorming-Timeout (2h überschritten)")
    finally:
        _brainstorming_active = False
```

- [ ] **Step 3: Verify no syntax errors**

```bash
python -c "import bot"
```

Expected: no output (clean import).

- [ ] **Step 4: Commit**

```bash
git add bot.py
git commit -m "feat: add _run_brainstorming() with concurrency flag and 2h timeout"
```

---

## Task 2: Add `brainstorming:` and `/specs` handlers, update `HILFE_TEXT` and `_is_command`

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: Update `HILFE_TEXT`**

Find `HILFE_TEXT = """` (line 65). Replace the entire string with:

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
  termin: <text> — Termin anlegen
    z.B. termin: Arzttermin morgen um 14:00
  backlog: <text> — Undatierte Aufgabe in Backlog speichern
  backlog — Alle offenen Backlog-Tasks anzeigen
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
  suche: <text> — Alle DBs durchsuchen (Tasks, Backlog, Archiv, Lernthemen, Ideen)

⏰ Erinnerungen
  erinnere mich um 14:00 an Zahnarzt — Erinnerung setzen
  erinnere mich morgen um 9 an Meeting — mit Datum
  erinnerung: <text> — alternative Syntax
  erinnerungen — alle offenen Erinnerungen anzeigen

🛠 Sonstiges
  teach: <thema + warum> — Lernkurs erstellen oder planen
    z.B. teach: Python Grundlagen, weil ich Skripte automatisieren will
  restart — Bot neu starten

🧠 Brainstorming
  brainstorming: <idee> — Feature-Idee brainstormen (Spec → Plan → Scheduling)
  brainstorming: <idee>, basis: <slug> — Mit vorheriger Spec als Kontext
  /specs — Alle vorhandenen Specs anzeigen

🤖 Pläne
  /plans — geplante Implementierungen anzeigen
  implement-plan: <slug> um HH:MM — Implementierung planen
  implement-plan: <slug> jetzt — sofort implementieren
  abort-plan: <slug> — Implementierung entfernen
"""
```

- [ ] **Step 2: Update `_is_command` guard**

Find the `_is_command` assignment (around line 901). Make two changes:

Add `"/specs"` to the `text.lower() in (...)` set:
```python
_is_command = (text.lower() in ("restart", "projekte", "moin", "abend", "woche", "hilfe", "erinnerungen", "/plans", "backlog", "/specs")
```

Add `"brainstorming:"` to the `startswith` tuple:
```python
or any(text.lower().startswith(p) for p in
       ("task:", "status:", "fokus:", "verschieben:", "lern:",
        "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
        "implement-plan:", "abort-plan:", "backlog:", "suche:", "brainstorming:")))
```

- [ ] **Step 3: Add `brainstorming:` handler**

Find `elif text.lower().startswith("/teach") or text.lower().startswith("teach:"):` (around line 1119). Insert immediately before it:

```python
elif text.lower().startswith("brainstorming:"):
    topic = text[14:].strip()
    if not topic:
        response = (
            "Nutzung: brainstorming: <idee>\n"
            "oder:    brainstorming: <idee>, basis: <slug>\n"
            "Specs anzeigen: /specs"
        )
    elif _brainstorming_active:
        response = "⚠️ Brainstorming-Session läuft bereits. Bitte warten bis sie abgeschlossen ist."
    else:
        basis_slug = None
        lower_topic = topic.lower()
        if ", basis:" in lower_topic:
            idx = lower_topic.index(", basis:")
            basis_slug = topic[idx + 8:].strip()
            topic = topic[:idx].strip()
        _brainstorming_active = True
        send_message(chat_id, "🧠 Brainstorming gestartet — Fragen kommen gleich über den Chat")
        threading.Thread(
            target=_run_brainstorming, args=(topic, basis_slug), daemon=True
        ).start()
        continue
```

- [ ] **Step 4: Add `/specs` handler**

Find `elif text.lower() == "/plans":` in the message loop. Insert immediately after its `continue` (before the next `elif`):

```python
elif text.lower() == "/specs":
    specs_dir = Path(WORK_DIR) / "docs" / "superpowers" / "specs"
    files = sorted(specs_dir.glob("*.md")) if specs_dir.exists() else []
    if not files:
        response = "Keine Specs vorhanden."
    else:
        lines = ["📋 Vorhandene Specs:\n"]
        for f in files:
            stem = f.stem  # e.g. "2026-06-11-telegram-relay-design"
            parts = stem.split("-", 3)
            if len(parts) == 4:
                date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
                slug = parts[3].removesuffix("-design")
                lines.append(f"{date_str} · {slug}")
            else:
                lines.append(stem)
        lines.append("\nNutzung: brainstorming: <idee>, basis: <slug>")
        response = "\n".join(lines)
```

- [ ] **Step 5: Verify no syntax errors**

```bash
python -c "import bot"
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add bot.py
git commit -m "feat: add brainstorming: command, /specs handler, HILFE_TEXT update"
```

---

## Task 3: Tests

**Files:**
- Modify: `tests/test_bot.py`

- [ ] **Step 1: Add tests**

Append to `tests/test_bot.py`:

```python
def test_hilfe_contains_brainstorming():
    assert "brainstorming:" in HILFE_TEXT

def test_hilfe_contains_specs():
    assert "/specs" in HILFE_TEXT

def test_brainstorming_prefix_parse_simple():
    text = "brainstorming: Chat-App mit Räumen"
    topic = text[14:].strip()
    assert topic == "Chat-App mit Räumen"
    assert ", basis:" not in topic.lower()

def test_brainstorming_prefix_parse_with_basis():
    text = "brainstorming: Chat-App, basis: telegram-relay"
    topic = text[14:].strip()
    lower = topic.lower()
    assert ", basis:" in lower
    idx = lower.index(", basis:")
    basis_slug = topic[idx + 8:].strip()
    feature = topic[:idx].strip()
    assert feature == "Chat-App"
    assert basis_slug == "telegram-relay"

def test_specs_listing_format(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "2026-06-11-telegram-relay-design.md").write_text("")
    (specs_dir / "2026-06-13-teach-improvements-design.md").write_text("")

    files = sorted(specs_dir.glob("*.md"))
    lines = []
    for f in files:
        stem = f.stem
        parts = stem.split("-", 3)
        if len(parts) == 4:
            date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
            slug = parts[3].removesuffix("-design")
            lines.append(f"{date_str} · {slug}")
        else:
            lines.append(stem)

    assert lines[0] == "2026-06-11 · telegram-relay"
    assert lines[1] == "2026-06-13 · teach-improvements"

def test_specs_listing_empty(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    files = sorted(specs_dir.glob("*.md")) if specs_dir.exists() else []
    assert files == []
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_bot.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_bot.py
git commit -m "test: add tests for brainstorming: command and /specs listing"
```

---

## Manual Smoke Test (on Pi)

- [ ] Pull latest: `git -C ~/projekte/claude-telegram-chat-bot pull`
- [ ] Restart service: `sudo systemctl restart telegram-bot`
- [ ] Send `hilfe` → verify `brainstorming:` and `/specs` appear
- [ ] Send `/specs` → verify spec list with dates and slugs
- [ ] Send `brainstorming: Test-Feature` → verify `🧠 Brainstorming gestartet` + first Telegram question arrives
- [ ] Send `brainstorming: Test` while active → verify `⚠️ Session läuft bereits`

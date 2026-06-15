# vision:end Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `vision:end` command that stops a running vision: session and writes VISION.md with `## Letzter Stand` and `## Confidence-Scores` sections.

**Architecture:** Signal-file approach — bot.py writes `HUB_DIR/.vision_end` when `vision:end` received; telegram_ask.py checks the file on startup and every 5s while waiting; Claude's prompt updated to handle "vision:end" response and write VISION.md immediately.

**Tech Stack:** Python 3, pathlib, subprocess (existing); no new dependencies.

---

## File Map

| File | Change |
|------|--------|
| `scripts/telegram_ask.py` | Add HUB_DIR signal-file check on startup + periodic check in wait loop |
| `bot.py` | Add `vision:end` message handler; update `_run_vision` prompt (tool rights, end signal, VISION.md structure) |
| `tests/test_telegram_ask.py` | Add signal-file test |
| `tests/test_bot.py` | Add HILFE_TEXT test for vision:end |

---

## Task 1: telegram_ask.py — Signal-File-Check (TDD)

**Files:**
- Modify: `tests/test_telegram_ask.py`
- Modify: `scripts/telegram_ask.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_telegram_ask.py`:

```python
def test_signal_file_triggers_vision_end(tmp_path):
    """Signal file causes telegram_ask to print 'vision:end' and exit 0."""
    signal_file = tmp_path / ".vision_end"
    signal_file.write_text("end")

    settings_path = PROJECT_DIR / "settings.json"
    original = settings_path.read_text()
    settings_path.write_text(json.dumps({"notifications_enabled": True}))

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "Irgendeine Frage?"],
            capture_output=True, text=True, timeout=5,
            env={**os.environ, "HUB_DIR": str(tmp_path)},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "vision:end"
        assert not signal_file.exists()
    finally:
        settings_path.write_text(original)
```

- [ ] **Step 2: Run test — verify FAIL**

```
pytest tests/test_telegram_ask.py::test_signal_file_triggers_vision_end -v
```

Expected: FAIL (no signal-file logic in telegram_ask.py yet)

- [ ] **Step 3: Implement signal-file check in telegram_ask.py**

In `scripts/telegram_ask.py`, after line 22 (`sys.exit(1)` for notifications_enabled) and before line 24 (`if len(sys.argv) < 2:`), insert:

```python
_HUB_DIR = os.environ.get("HUB_DIR", "")
_signal_path = Path(_HUB_DIR) / ".vision_end" if _HUB_DIR else None


def _check_signal():
    if _signal_path and _signal_path.exists():
        _signal_path.unlink()
        print("vision:end")
        sys.exit(0)


_check_signal()
```

Then in the wait loop, replace:

```python
while time.time() - start < timeout:
    if response_path.exists():
        try:
            resp = json.loads(response_path.read_text())
            response_path.unlink()
        except Exception:
            time.sleep(0.1)
            continue
        print(resp.get("answer", "A"))
        sys.exit(0)
    time.sleep(0.5)
```

with:

```python
_last_signal_check = time.time()
while time.time() - start < timeout:
    if response_path.exists():
        try:
            resp = json.loads(response_path.read_text())
            response_path.unlink()
        except Exception:
            time.sleep(0.1)
            continue
        print(resp.get("answer", "A"))
        sys.exit(0)
    if time.time() - _last_signal_check >= 5:
        _check_signal()
        _last_signal_check = time.time()
    time.sleep(0.5)
```

- [ ] **Step 4: Run test — verify PASS**

```
pytest tests/test_telegram_ask.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/telegram_ask.py tests/test_telegram_ask.py
git commit -m "feat: vision:end signal-file check in telegram_ask.py"
```

---

## Task 2: bot.py — vision:end Message Handler

**Files:**
- Modify: `bot.py:1511` (add handler before `elif text.lower().startswith("vision:")`)
- Modify: `tests/test_bot.py` (HILFE_TEXT check)

- [ ] **Step 1: Write failing test**

Append to `tests/test_bot.py`:

```python
def test_hilfe_contains_vision_end():
    assert "vision:end" in HILFE_TEXT
```

- [ ] **Step 2: Run test — verify FAIL**

```
pytest tests/test_bot.py::test_hilfe_contains_vision_end -v
```

Expected: FAIL

- [ ] **Step 3: Add vision:end to HILFE_TEXT in bot.py**

In `bot.py`, find the HILFE_TEXT block containing `vision: <slug>`. Add a line immediately after it:

```
  vision:end — Laufende Vision-Session beenden und VISION.md speichern
```

The section should read:

```
🔭 Projekte & Vision
  projekte — Alle Projekte anzeigen (interaktiv)
  vision: <slug> — Vision-Session für ein Projekt starten
  vision:end — Laufende Vision-Session beenden und VISION.md speichern
  <name>: <frage> — Im Projektkontext fragen
```

- [ ] **Step 4: Add vision:end handler in message routing**

In `bot.py`, find (around line 1511):

```python
            elif text.lower().startswith("vision:"):
```

Insert directly BEFORE it:

```python
            elif text.lower() == "vision:end":
                if _vision_active:
                    Path(HUB_DIR, ".vision_end").write_text("end")
                    response = "⏹ vision:end Signal gesendet — Claude schreibt VISION.md"
                else:
                    response = "Keine Vision-Session aktiv."
```

- [ ] **Step 5: Run tests — verify PASS**

```
pytest tests/test_bot.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: vision:end message handler in bot.py"
```

---

## Task 3: bot.py — _run_vision Prompt Update

**Files:**
- Modify: `bot.py:696-708` (`_run_vision` prompt string)

No new tests — prompt change; verified by running a real vision: session.

- [ ] **Step 1: Replace the prompt string in _run_vision**

Find this block in `bot.py` (around line 696):

```python
    prompt = (
        f"You are running a project vision session for: {proj['name']} (slug: {slug}). "
        f"Project registry (all known projects for cross-reference): {registry_json}. "
        f"{code_note} "
        f"{vision_note} "
        f"Through dialogue, explore: project goal, required features (ordered by dependency), "
        f"architecture decisions, open questions. Ask one question at a time via: "
        f'python "{telegram_ask_path}" "your question here". '
        f"After session, write/update {vision_path}. "
        f"Then: git -C {HUB_DIR} add -A && "
        f"git -C {HUB_DIR} commit -m \"vision: update {slug}\" && "
        f"git -C {HUB_DIR} push"
    )
```

Replace with:

```python
    prompt = (
        f"You are running a project vision session for: {proj['name']} (slug: {slug}). "
        f"You have full tool access: write files, run Bash commands including git. "
        f"Project registry (all known projects for cross-reference): {registry_json}. "
        f"{code_note} "
        f"{vision_note} "
        f"Through dialogue, explore: project goal, required features (ordered by dependency), "
        f"architecture decisions, open questions. Ask one question at a time via: "
        f'python "{telegram_ask_path}" "your question here". '
        f"If any telegram_ask.py call returns exactly 'vision:end': stop asking questions immediately. "
        f"Write/update {vision_path} with all discussed content. "
        f"Then: git -C {HUB_DIR} add -A && git -C {HUB_DIR} commit -m \"vision: update {slug}\" && git -C {HUB_DIR} push. "
        f"Then exit. "
        f"When you have covered goal, top features, architecture, and open questions: "
        f"ask via telegram_ask.py: 'Soll ich die Vision-Session jetzt abschließen? (ja / vision:end / weiter)'. "
        f"On 'ja' or 'vision:end': write VISION.md and commit. On 'weiter': continue exploring. "
        f"When writing {vision_path}, always include/update these two sections: "
        f"'## Letzter Stand' with today's date, summary of topics discussed, and priorities for next session. "
        f"'## Confidence-Scores' as a markdown table: "
        f"| Position | Bestätigungen | Anzweiflungen | Bewertung | "
        f"Fill based on how often each architectural decision was confirmed vs. questioned in the dialogue. "
        f"Use 🟢 hoch / 🟡 mittel / 🔴 niedrig."
    )
```

- [ ] **Step 2: Run all tests — verify nothing broken**

```
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add bot.py
git commit -m "feat: update _run_vision prompt — tool rights, vision:end signal, VISION.md structure"
```

---

## Task 4: Deploy to Pi

- [ ] **Step 1: Push to remote**

```bash
git push
```

- [ ] **Step 2: SSH deploy**

Read `pi_host` from `settings.json`, then:

```bash
ssh pi@<pi_host> '~/deploy.sh'
```

Expected: deploy.sh pulls and restarts bot.

- [ ] **Step 3: Smoke test**

Send `vision:end` in Telegram when no session is active.
Expected: `"Keine Vision-Session aktiv."`

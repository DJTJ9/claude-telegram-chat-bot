# Projects Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a `projects-hub` git repo as central planning storage and wire it into the bot with a `vision:` command, inline-keyboard project selector, feature-driven brainstorming, auto-push, and bot auto-restart.

**Architecture:** A new `projects-hub` repo holds `projects-registry.json` and `topics/<slug>/` per project (VISION.md + specs/ + plans/). The bot reads `HUB_DIR` env var and uses the registry to drive inline keyboard menus. `_run_vision()` mirrors `_run_brainstorming()`. Callback dispatch is extended with `proj_*` and `feat_sel` prefixes.

**Tech Stack:** Python 3, Telegram Bot API (inline keyboards, callback_query), git CLI, Claude Code CLI

---

## File Structure

| File | Action |
|------|--------|
| `C:\Projekte\projects-hub\` | Create (new git repo) |
| `C:\Projekte\projects-hub\projects-registry.json` | Create |
| `C:\Projekte\projects-hub\topics\` | Create (empty dir) |
| `C:\Projekte\telegram-notion-bot\bot.py` | Modify (many additions) |
| `C:\Projekte\telegram-notion-bot\scripts\restart_bot.sh` | Create |
| `C:\Projekte\telegram-notion-bot\tests\test_bot.py` | Modify (new tests) |
| `C:\Users\tjark\.claude\CLAUDE.md` | Modify (hub section) |

---

### Task 1: Create projects-hub repo

**Files:**
- Create: `C:\Projekte\projects-hub\projects-registry.json`
- Create: `C:\Projekte\projects-hub\topics\.gitkeep`

- [ ] **Step 1: Initialize hub repo**

```powershell
New-Item -ItemType Directory -Path "C:\Projekte\projects-hub"
git -C "C:\Projekte\projects-hub" init
New-Item -ItemType Directory -Path "C:\Projekte\projects-hub\topics"
```

- [ ] **Step 2: Write projects-registry.json**

Create `C:\Projekte\projects-hub\projects-registry.json`:

```json
[
  {
    "slug": "telegram-notion-bot",
    "name": "NotionBot",
    "path": "C:\\Projekte\\telegram-notion-bot",
    "repo": "https://github.com/DJTJ9/telegram-notion-bot",
    "description": "Telegram Notion Bot"
  },
  {
    "slug": "dart-app",
    "name": "DartApp",
    "path": "C:\\Unity\\Aktuelle Projekte\\DartTrainingsApp",
    "repo": "",
    "description": "Dart Trainings-App"
  }
]
```

- [ ] **Step 3: Write .gitkeep and initial commit**

```powershell
New-Item -ItemType File -Path "C:\Projekte\projects-hub\topics\.gitkeep"
git -C "C:\Projekte\projects-hub" add -A
git -C "C:\Projekte\projects-hub" commit -m "chore: initial projects-hub setup"
```

- [ ] **Step 4: Create GitHub repo and push**

```powershell
gh repo create DJTJ9/projects-hub --private --source "C:\Projekte\projects-hub" --push
```

If `gh` not available, create repo at github.com then:

```powershell
git -C "C:\Projekte\projects-hub" remote add origin https://github.com/DJTJ9/projects-hub.git
git -C "C:\Projekte\projects-hub" push -u origin master
```

- [ ] **Step 5: Verify registry loads**

```powershell
python -c "import json; data = json.loads(open('C:/Projekte/projects-hub/projects-registry.json').read()); print(len(data), 'projects')"
```

Expected output: `2 projects`

- [ ] **Step 6: Commit task note**

```bash
git -C "C:\Projekte\telegram-notion-bot" add docs/superpowers/plans/2026-06-15-projects-hub.md
git -C "C:\Projekte\telegram-notion-bot" commit -m "chore: mark task 1 done (hub repo created)"
```

---

### Task 2: Add HUB_DIR env var + migrate PLANS_PATH to hub

**Files:**
- Modify: `bot.py` lines 13-15 (constants block)
- Modify: `bot.py` `_set_plan_status()`, `_run_plan()`, `_schedule_plan()`, `_abort_plan()`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_bot.py`:

```python
import os, json, tempfile
from pathlib import Path

def test_hub_dir_defaults_to_work_dir():
    from bot import HUB_DIR, WORK_DIR
    assert HUB_DIR == WORK_DIR or os.environ.get("HUB_DIR") is not None

def test_plans_path_in_hub_dir():
    from bot import PLANS_PATH, HUB_DIR
    assert str(PLANS_PATH).startswith(HUB_DIR)
    assert PLANS_PATH.name == "scheduled_plans.json"

def test_load_registry_empty_when_missing(tmp_path, monkeypatch):
    import bot
    monkeypatch.setattr(bot, "HUB_DIR", str(tmp_path))
    result = bot._load_registry()
    assert result == []

def test_load_registry_returns_list(tmp_path, monkeypatch):
    import bot
    registry = [{"slug": "test", "name": "Test", "path": "", "repo": "", "description": ""}]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry))
    monkeypatch.setattr(bot, "HUB_DIR", str(tmp_path))
    result = bot._load_registry()
    assert len(result) == 1
    assert result[0]["slug"] == "test"
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_bot.py::test_hub_dir_defaults_to_work_dir tests/test_bot.py::test_plans_path_in_hub_dir -v
```

Expected: `AttributeError: module 'bot' has no attribute 'HUB_DIR'`

- [ ] **Step 3: Add HUB_DIR and update PLANS_PATH in bot.py**

In `bot.py`, replace lines 13-15:

```python
WORK_DIR = os.environ.get("WORK_DIR", r"C:\Projekte\telegram-notion-bot")
HUB_DIR = os.environ.get("HUB_DIR", WORK_DIR)
REMINDERS_PATH = Path(WORK_DIR) / "reminders.json"
PLANS_PATH = Path(HUB_DIR) / "scheduled_plans.json"
```

- [ ] **Step 4: Add _load_registry() and _save_registry() functions**

Add after `_save_plans()` function:

```python
def _load_registry():
    path = Path(HUB_DIR) / "projects-registry.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []

def _save_registry(registry):
    path = Path(HUB_DIR) / "projects-registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 5: Update _set_plan_status() to use HUB_DIR**

Replace the git calls inside `_set_plan_status()`:

```python
def _set_plan_status(slug, status):
    plans = _load_plans()
    for p in plans:
        if p["slug"] == slug:
            p["status"] = status
            break
    _save_plans(plans)
    subprocess.run(["git", "-C", HUB_DIR, "add", "scheduled_plans.json"], capture_output=True)
    subprocess.run(["git", "-C", HUB_DIR, "commit", "-m", f"chore: plan {slug} -> {status}"], capture_output=True)
```

- [ ] **Step 6: Update _schedule_plan() and _abort_plan() to use HUB_DIR**

In `_schedule_plan()`, replace both `WORK_DIR` git calls with `HUB_DIR`:

```python
subprocess.run(["git", "-C", HUB_DIR, "add", "scheduled_plans.json"], capture_output=True)
subprocess.run(["git", "-C", HUB_DIR, "commit", "-m", f"chore: schedule plan {slug} at {scheduled_time}"], capture_output=True)
```

In `_abort_plan()`, replace both `WORK_DIR` git calls with `HUB_DIR`:

```python
subprocess.run(["git", "-C", HUB_DIR, "add", "scheduled_plans.json"], capture_output=True)
subprocess.run(["git", "-C", HUB_DIR, "commit", "-m", f"chore: remove plan {slug}"], capture_output=True)
```

- [ ] **Step 7: Update _run_plan() to resolve paths from HUB_DIR for hub plans**

Replace the existing `_run_plan()` function:

```python
def _run_plan(plan_path, slug=None):
    if plan_path.startswith("topics/"):
        base = Path(HUB_DIR)
        allowed = (Path(HUB_DIR) / "topics").resolve()
        exec_cwd = HUB_DIR
    else:
        base = Path(WORK_DIR)
        allowed = (Path(WORK_DIR) / "docs" / "superpowers" / "plans").resolve()
        exec_cwd = WORK_DIR
    resolved = (base / plan_path).resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError:
        send_message(MY_CHAT_ID, f"❌ Ungültiger Plan-Pfad: {plan_path}")
        return
    prompt = (
        f"Follow the implementation plan exactly. "
        f"Plan file: {plan_path}\n"
        f"Read the plan file and implement every task step by step. Commit all changes when done."
    )
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            timeout=3600, cwd=exec_cwd)
    if result.returncode != 0:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                timeout=3600, cwd=exec_cwd)
    success = result.returncode == 0
    if slug:
        _set_plan_status(slug, "done" if success else "failed")
    label = slug or plan_path
    if success:
        send_message(MY_CHAT_ID, f"✅ Implementierung abgeschlossen: {label}")
    else:
        send_message(MY_CHAT_ID, f"❌ Implementierung fehlgeschlagen: {label}\n{(result.stderr or '')[-500:]}")
```

- [ ] **Step 8: Copy scheduled_plans.json to hub (one-time migration)**

```powershell
Copy-Item "C:\Projekte\telegram-notion-bot\scheduled_plans.json" "C:\Projekte\projects-hub\scheduled_plans.json"
git -C "C:\Projekte\projects-hub" add scheduled_plans.json
git -C "C:\Projekte\projects-hub" commit -m "chore: migrate scheduled_plans.json from bot repo"
git -C "C:\Projekte\projects-hub" push
```

- [ ] **Step 9: Run tests — expect PASS**

```powershell
python -m pytest tests/test_bot.py::test_hub_dir_defaults_to_work_dir tests/test_bot.py::test_plans_path_in_hub_dir tests/test_bot.py::test_load_registry_empty_when_missing tests/test_bot.py::test_load_registry_returns_list -v
```

Expected: 4 tests PASS

- [ ] **Step 10: Commit**

```bash
git -C "C:\Projekte\telegram-notion-bot" add bot.py tests/test_bot.py
git -C "C:\Projekte\telegram-notion-bot" commit -m "feat: add HUB_DIR, _load_registry(), migrate PLANS_PATH to hub"
```

---

### Task 3: Revamp `projekte` handler + _parse_vision_features()

**Files:**
- Modify: `bot.py` — `projekte` text handler, callback_query block, new helper
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_bot.py`:

```python
def test_parse_vision_features_empty(tmp_path, monkeypatch):
    import bot
    monkeypatch.setattr(bot, "HUB_DIR", str(tmp_path))
    result = bot._parse_vision_features("no-such-project")
    assert result == []

def test_parse_vision_features_parses_unchecked(tmp_path, monkeypatch):
    import bot
    monkeypatch.setattr(bot, "HUB_DIR", str(tmp_path))
    slug_dir = tmp_path / "topics" / "test-proj"
    slug_dir.mkdir(parents=True)
    (slug_dir / "VISION.md").write_text(
        "## Features\n- [ ] Feature A\n- [x] Done Feature\n- [ ] Feature B\n"
    )
    result = bot._parse_vision_features("test-proj")
    assert result == ["Feature A", "Feature B"]
    assert "Done Feature" not in result

def test_parse_vision_features_all_returned(tmp_path, monkeypatch):
    import bot
    monkeypatch.setattr(bot, "HUB_DIR", str(tmp_path))
    slug_dir = tmp_path / "topics" / "big-proj"
    slug_dir.mkdir(parents=True)
    lines = "\n".join(f"- [ ] Feature {i}" for i in range(15))
    (slug_dir / "VISION.md").write_text(f"## Features\n{lines}\n")
    result = bot._parse_vision_features("big-proj")
    assert len(result) == 15
    assert result[0] == "Feature 0"
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_bot.py::test_parse_vision_features_empty tests/test_bot.py::test_parse_vision_features_parses_unchecked -v
```

Expected: `AttributeError: module 'bot' has no attribute '_parse_vision_features'`

- [ ] **Step 3: Add _parse_vision_features() to bot.py**

Add after `_save_registry()`:

```python
def _parse_vision_features(slug):
    vision_path = Path(HUB_DIR) / "topics" / slug / "VISION.md"
    if not vision_path.exists():
        return []
    features = []
    for line in vision_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \[ \] (.+)$", line.strip())
        if m:
            features.append(m.group(1).strip())
    return features
```

- [ ] **Step 4: Add _pending_new_project global near other state dicts**

Find `conversation_history = {}` in bot.py and add after it:

```python
_pending_new_project = {}
```

- [ ] **Step 5: Replace projekte text handler with inline keyboard version**

Find and replace the existing `if text.lower() == "projekte":` block:

```python
            if text.lower() in ("projekte", "/projekte"):
                registry = _load_registry()
                buttons = [[{"text": "➕ Neues Projekt", "callback_data": "new_proj"}]]
                for proj in registry:
                    buttons.append([{"text": f"🎯 {proj['name']}", "callback_data": f"proj_sel:{proj['slug']}"}])
                send_message(chat_id, "Deine Projekte:", reply_markup={"inline_keyboard": buttons})
                continue
```

- [ ] **Step 6: Add new_proj and proj_sel: callbacks to callback dispatcher**

In the `if cb:` block, after the existing `approve_`/`deny_` branch, add:

```python
                elif cb_data == "new_proj":
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    _pending_new_project[MY_CHAT_ID] = {"state": "await_name"}
                    send_message(MY_CHAT_ID, "Name des neuen Projekts?")
                    continue
                elif cb_data.startswith("proj_sel:"):
                    slug = cb_data[9:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    registry = _load_registry()
                    proj = next((p for p in registry if p["slug"] == slug), {"name": slug})
                    buttons = [[
                        {"text": "🔭 Vision", "callback_data": f"proj_vis:{slug}"},
                        {"text": "🧠 Brainstorming", "callback_data": f"proj_bs:{slug}"},
                        {"text": "📋 Pläne", "callback_data": f"proj_plans:{slug}"},
                    ]]
                    send_message(MY_CHAT_ID, f"{proj['name']} — was möchtest du tun?",
                                 reply_markup={"inline_keyboard": buttons})
                    continue
```

- [ ] **Step 7: Run tests — expect PASS**

```powershell
python -m pytest tests/test_bot.py::test_parse_vision_features_empty tests/test_bot.py::test_parse_vision_features_parses_unchecked tests/test_bot.py::test_parse_vision_features_all_returned -v
```

Expected: 3 tests PASS

- [ ] **Step 8: Commit**

```bash
git -C "C:\Projekte\telegram-notion-bot" add bot.py tests/test_bot.py
git -C "C:\Projekte\telegram-notion-bot" commit -m "feat: projekte inline keyboard, _parse_vision_features(), _pending_new_project"
```

---

### Task 4: New project creation state machine + _create_project_entry()

**Files:**
- Modify: `bot.py` — message handler, callback handler, new `_create_project_entry()`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_bot.py`:

```python
def test_create_project_entry_adds_to_registry(tmp_path, monkeypatch):
    import bot, threading
    monkeypatch.setattr(bot, "HUB_DIR", str(tmp_path))
    (tmp_path / "projects-registry.json").write_text("[]")
    monkeypatch.setattr(bot, "_vision_active", False)
    captured = []
    monkeypatch.setattr(bot, "send_message", lambda *a, **kw: captured.append(a))
    monkeypatch.setattr(bot, "_run_vision", lambda slug: None)
    monkeypatch.setattr(threading, "Thread",
        lambda target, args, daemon: type("T", (), {"start": lambda self: None})())
    bot._create_project_entry("my-app", "MyApp", path="C:\\Projekte\\MyApp", chat_id=123)
    registry = bot._load_registry()
    assert any(p["slug"] == "my-app" for p in registry)
    assert (tmp_path / "topics" / "my-app" / "specs").exists()
    assert (tmp_path / "topics" / "my-app" / "plans").exists()
```

- [ ] **Step 2: Run test — expect FAIL**

```powershell
python -m pytest tests/test_bot.py::test_create_project_entry_adds_to_registry -v
```

Expected: `AttributeError: module 'bot' has no attribute '_create_project_entry'`

- [ ] **Step 3: Add _create_project_entry() to bot.py**

Add after `_save_registry()`:

```python
def _create_project_entry(slug, name, path, chat_id):
    global _vision_active
    registry = _load_registry()
    if not any(p["slug"] == slug for p in registry):
        registry.append({"slug": slug, "name": name, "path": path or "", "repo": "", "description": ""})
        _save_registry(registry)
        subprocess.run(["git", "-C", HUB_DIR, "add", "projects-registry.json"], capture_output=True)
        subprocess.run(["git", "-C", HUB_DIR, "commit", "-m", f"chore: add project {slug}"], capture_output=True)
    topic_dir = Path(HUB_DIR) / "topics" / slug
    (topic_dir / "specs").mkdir(parents=True, exist_ok=True)
    (topic_dir / "plans").mkdir(parents=True, exist_ok=True)
    send_message(chat_id, f"✅ Projekt {name} angelegt. Starte Vision-Session...")
    _vision_active = True
    threading.Thread(target=_run_vision, args=(slug,), daemon=True).start()
```

- [ ] **Step 4: Add _pending_new_project message handler**

In the message dispatch loop, add BEFORE `send_message(chat_id, "⏳ Denke nach...")`:

```python
            # New project creation state machine
            if chat_id in _pending_new_project:
                state_data = _pending_new_project[chat_id]
                state = state_data["state"]
                _is_nav = text.lower() in ("projekte", "hilfe", "moin", "abend", "/plans", "/specs")
                if _is_nav:
                    del _pending_new_project[chat_id]
                elif state == "await_name":
                    name = text.strip()[:40]
                    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30]
                    if not slug:
                        send_message(chat_id, "❌ Ungültiger Name. Nochmal versuchen.")
                    else:
                        default_path = f"C:\\Projekte\\{name}"
                        _pending_new_project[chat_id] = {"state": "await_path", "slug": slug, "name": name}
                        buttons = [
                            [{"text": f"A) {default_path}", "callback_data": f"npth_a:{slug}"}],
                            [{"text": "B) Anderen Pfad eingeben", "callback_data": f"npth_b:{slug}"}],
                            [{"text": "C) Noch kein Pfad (nur Planung)", "callback_data": f"npth_c:{slug}"}],
                        ]
                        send_message(chat_id, f"Wo soll {name} angelegt werden?",
                                     reply_markup={"inline_keyboard": buttons})
                elif state == "await_custom_path":
                    custom_path = text.strip()
                    slug = state_data["slug"]
                    name = state_data["name"]
                    del _pending_new_project[chat_id]
                    _create_project_entry(slug, name, path=custom_path, chat_id=chat_id)
                continue
```

- [ ] **Step 5: Add npth_* callback handlers**

In the callback dispatcher, add after `proj_sel:` handling:

```python
                elif cb_data.startswith("npth_a:"):
                    slug = cb_data[7:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    state = _pending_new_project.pop(MY_CHAT_ID, {})
                    name = state.get("name", slug)
                    _create_project_entry(slug, name, path=f"C:\\Projekte\\{name}", chat_id=MY_CHAT_ID)
                    continue
                elif cb_data.startswith("npth_b:"):
                    slug = cb_data[7:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    state = _pending_new_project.get(MY_CHAT_ID, {})
                    _pending_new_project[MY_CHAT_ID] = {**state, "state": "await_custom_path", "slug": slug}
                    send_message(MY_CHAT_ID, "Pfad eingeben (z.B. C:\\Projekte\\MeineApp):")
                    continue
                elif cb_data.startswith("npth_c:"):
                    slug = cb_data[7:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    state = _pending_new_project.pop(MY_CHAT_ID, {})
                    name = state.get("name", slug)
                    _create_project_entry(slug, name, path=None, chat_id=MY_CHAT_ID)
                    continue
```

- [ ] **Step 6: Run test — expect PASS**

```powershell
python -m pytest tests/test_bot.py::test_create_project_entry_adds_to_registry -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git -C "C:\Projekte\telegram-notion-bot" add bot.py tests/test_bot.py
git -C "C:\Projekte\telegram-notion-bot" commit -m "feat: new project creation state machine + _create_project_entry()"
```

---

### Task 5: _run_vision() + vision: handler + proj_vis callback

**Files:**
- Modify: `bot.py` — add `_vision_active`, `_run_vision()`, `vision:` handler, `proj_vis:` callback
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_bot.py`:

```python
def test_vision_active_flag_exists():
    import bot
    assert hasattr(bot, "_vision_active")
    assert isinstance(bot._vision_active, bool)

def test_vision_handler_prefix():
    text = "vision: dart-app"
    assert text.lower().startswith("vision:")
    assert text[7:].strip() == "dart-app"

def test_vision_handler_empty():
    text = "vision:"
    assert text[7:].strip() == ""
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_bot.py::test_vision_active_flag_exists -v
```

Expected: `AssertionError`

- [ ] **Step 3: Add _vision_active global**

Add after `_brainstorming_active = False`:

```python
_vision_active = False
```

- [ ] **Step 4: Add _run_vision() to bot.py**

Add after `_run_brainstorming()`:

```python
def _run_vision(slug):
    global _vision_active
    registry = _load_registry()
    proj = next((p for p in registry if p["slug"] == slug),
                {"slug": slug, "name": slug, "path": "", "repo": ""})
    hub_path = Path(HUB_DIR) / "topics" / slug
    hub_path.mkdir(parents=True, exist_ok=True)
    vision_path = hub_path / "VISION.md"
    telegram_ask_path = Path(WORK_DIR) / "scripts" / "telegram_ask.py"

    vision_note = (
        f"Read {vision_path} first — it exists. Append/refine sections, do NOT overwrite entirely."
        if vision_path.exists() else
        f"Create {vision_path} with this structure:\n"
        f"# {proj['name']} — Vision\n\n## Ziel\n\n"
        f"## Features (Backlog — priorisiert)\n- [ ] ...\n\n"
        f"## Architektur\n\n## Offene Fragen\n\n## Entscheidungen\n"
    )
    code_note = (
        f"Project code is at {proj['path']} — read its structure for architecture context."
        if proj.get("path") and Path(proj["path"]).exists() else ""
    )
    registry_json = json.dumps(registry, ensure_ascii=False)

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
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                timeout=3600, cwd=str(hub_path), env=env)
        if result.returncode == 0:
            send_message(MY_CHAT_ID, f"🔭 Vision-Session für {proj['name']} abgeschlossen")
        else:
            send_message(MY_CHAT_ID, f"❌ Vision-Session fehlgeschlagen\n{(result.stderr or '')[-300:]}")
    except subprocess.TimeoutExpired:
        send_message(MY_CHAT_ID, "❌ Vision-Timeout (1h überschritten)")
    finally:
        _vision_active = False
```

- [ ] **Step 5: Add vision: text handler before brainstorming: handler**

```python
            elif text.lower().startswith("vision:"):
                slug = text[7:].strip()
                if not slug:
                    response = "Nutzung: vision: <slug>  z.B. vision: dart-app\nProjekte anzeigen: projekte"
                elif _vision_active:
                    response = "⚠️ Vision-Session läuft bereits. Warten bis abgeschlossen."
                else:
                    registry = _load_registry()
                    proj = next(
                        (p for p in registry
                         if p["slug"] == slug or p["name"].lower() == slug.lower()),
                        None
                    )
                    if not proj:
                        response = (f"❌ Projekt '{slug}' nicht gefunden. "
                                    f"Erst anlegen: projekte → ➕ Neues Projekt")
                    else:
                        _vision_active = True
                        send_message(chat_id,
                                     f"🔭 Vision-Session für {proj['name']} gestartet — Fragen kommen gleich")
                        threading.Thread(target=_run_vision, args=(proj["slug"],), daemon=True).start()
                        continue
```

- [ ] **Step 6: Add proj_vis: callback handler**

In callback dispatcher, add after `proj_sel:` handling:

```python
                elif cb_data.startswith("proj_vis:"):
                    slug = cb_data[9:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    if _vision_active:
                        send_message(MY_CHAT_ID, "⚠️ Vision-Session läuft bereits.")
                    else:
                        registry = _load_registry()
                        proj = next((p for p in registry if p["slug"] == slug), {"name": slug})
                        _vision_active = True
                        send_message(MY_CHAT_ID,
                                     f"🔭 Vision-Session für {proj['name']} gestartet — Fragen kommen gleich")
                        threading.Thread(target=_run_vision, args=(slug,), daemon=True).start()
                    continue
```

- [ ] **Step 7: Run tests — expect PASS**

```powershell
python -m pytest tests/test_bot.py::test_vision_active_flag_exists tests/test_bot.py::test_vision_handler_prefix tests/test_bot.py::test_vision_handler_empty -v
```

Expected: 3 tests PASS

- [ ] **Step 8: Commit**

```bash
git -C "C:\Projekte\telegram-notion-bot" add bot.py tests/test_bot.py
git -C "C:\Projekte\telegram-notion-bot" commit -m "feat: _run_vision(), vision: handler, proj_vis callback, _vision_active flag"
```

---

### Task 6: proj_bs + feat_sel callbacks (feature selector)

**Files:**
- Modify: `bot.py` — callback dispatcher

- [ ] **Step 1: Add proj_bs: callback handler**

In callback dispatcher, add after `proj_vis:` handling:

```python
                elif cb_data.startswith("proj_bs:"):
                    slug = cb_data[8:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    features = _parse_vision_features(slug)
                    if not features:
                        buttons = [[{"text": "🔭 Vision starten", "callback_data": f"proj_vis:{slug}"}]]
                        send_message(MY_CHAT_ID,
                                     "Keine offenen Features. Starte zuerst eine Vision-Session.",
                                     reply_markup={"inline_keyboard": buttons})
                    else:
                        buttons = []
                        for i, feat in enumerate(features[:9]):
                            label = feat[:38]
                            buttons.append([{"text": f"🎯 {label}", "callback_data": f"feat_sel:{slug}:{i}"}])
                        buttons.append([{"text": "✏️ Neues Feature → erst Vision",
                                         "callback_data": f"proj_vis:{slug}"}])
                        registry = _load_registry()
                        proj = next((p for p in registry if p["slug"] == slug), {"name": slug})
                        send_message(MY_CHAT_ID, f"{proj['name']} — welches Feature brainstormen?",
                                     reply_markup={"inline_keyboard": buttons})
                    continue
```

- [ ] **Step 2: Add feat_sel: callback handler**

Add after `proj_bs:` handling:

```python
                elif cb_data.startswith("feat_sel:"):
                    parts = cb_data.split(":", 2)
                    if len(parts) == 3:
                        slug, idx_str = parts[1], parts[2]
                        requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                        try:
                            idx = int(idx_str)
                            features = _parse_vision_features(slug)
                            if 0 <= idx < len(features):
                                feature = features[idx]
                                if _brainstorming_active:
                                    send_message(MY_CHAT_ID, "⚠️ Brainstorming-Session läuft bereits.")
                                else:
                                    _brainstorming_active = True
                                    send_message(MY_CHAT_ID,
                                                 f"🧠 Brainstorming: {feature[:60]} — Fragen kommen gleich")
                                    threading.Thread(
                                        target=_run_brainstorming,
                                        args=(feature, None, slug),
                                        daemon=True
                                    ).start()
                            else:
                                send_message(MY_CHAT_ID,
                                             "❌ Feature nicht mehr verfügbar — projekte neu laden.")
                        except (ValueError, IndexError):
                            send_message(MY_CHAT_ID, "❌ Ungültige Feature-Auswahl.")
                    continue
```

- [ ] **Step 3: Commit**

```bash
git -C "C:\Projekte\telegram-notion-bot" add bot.py
git -C "C:\Projekte\telegram-notion-bot" commit -m "feat: proj_bs and feat_sel callbacks for feature-driven brainstorming"
```

---

### Task 7: Update _run_brainstorming() for hub output + auto-push

**Files:**
- Modify: `bot.py` — `_run_brainstorming()` signature and body

- [ ] **Step 1: Write test for backwards compatibility**

Append to `tests/test_bot.py`:

```python
def test_run_brainstorming_without_slug_uses_work_dir(monkeypatch):
    import bot, subprocess as sp
    calls = []
    def fake_run(cmd, **kw):
        calls.append(kw.get("cwd"))
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(sp, "run", fake_run)
    monkeypatch.setattr(bot, "subprocess", sp)
    monkeypatch.setattr(bot, "send_message", lambda *a, **kw: None)
    bot._brainstorming_active = True
    bot._run_brainstorming("test topic")
    assert any(c == bot.WORK_DIR for c in calls)
```

- [ ] **Step 2: Run test — expect FAIL (wrong signature)**

```powershell
python -m pytest tests/test_bot.py::test_run_brainstorming_without_slug_uses_work_dir -v
```

- [ ] **Step 3: Replace _run_brainstorming() with hub-aware version**

Replace the full `_run_brainstorming(topic, basis_slug=None)` function:

```python
def _run_brainstorming(topic, basis_slug=None, project_slug=None):
    global _brainstorming_active
    safe_topic = topic[:500]
    telegram_ask_path = Path(WORK_DIR) / "scripts" / "telegram_ask.py"
    restart_script = Path(WORK_DIR) / "scripts" / "restart_bot.sh"

    if project_slug:
        registry = _load_registry()
        proj = next((p for p in registry if p["slug"] == project_slug),
                    {"slug": project_slug, "name": project_slug, "path": "", "repo": ""})
        hub_path = Path(HUB_DIR) / "topics" / project_slug
        hub_path.mkdir(parents=True, exist_ok=True)
        vision_path = hub_path / "VISION.md"
        prior_specs = sorted((hub_path / "specs").glob("*.md")) if (hub_path / "specs").exists() else []
        registry_json = json.dumps(registry, ensure_ascii=False)
        proj_path = proj.get("path", "")

        vision_note = f"Read {vision_path} for project context, architecture, and feature backlog." if vision_path.exists() else ""
        specs_note = (f"Prior specs for cross-session context: {', '.join(str(s) for s in prior_specs[-3:])}"
                      if prior_specs else "")
        push_proj = (
            f"git -C {proj_path!r} add -A && "
            f"git -C {proj_path!r} commit -m \"feat: {safe_topic[:40]}\" && "
            f"git -C {proj_path!r} push"
            if proj_path else ""
        )
        post_impl = (
            f"After successful implementation:\n"
            f"1. In {vision_path}, change '- [ ] {safe_topic}' to "
            f"'- [x] {safe_topic} (implementiert {date.today().isoformat()})'.\n"
            f"2. git -C {HUB_DIR} add -A && git -C {HUB_DIR} commit -m "
            f"\"chore: {project_slug} after {safe_topic[:30]}\" && git -C {HUB_DIR} push\n"
            f"3. {push_proj}\n"
            f"4. If bot.py or scripts/ in {WORK_DIR} were modified: "
            f"send a Telegram message that the bot is restarting, "
            f"then run: bash {restart_script}"
        )
        prompt = (
            f"Invoke the superpowers:brainstorming skill. "
            f"Project: {proj['name']} (slug: {project_slug}). "
            f"Feature to brainstorm: {safe_topic}. "
            f"Project registry: {registry_json}. "
            f"{vision_note} {specs_note} "
            f"Save spec to {hub_path}/specs/YYYY-MM-DD-<topic>-design.md. "
            f"Save plan to {hub_path}/plans/YYYY-MM-DD-<topic>.md. "
            f"Use python \"{telegram_ask_path}\" for ALL questions and gate decisions. "
            f"{post_impl}"
        )
        exec_cwd = str(hub_path)
    else:
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
            f"Use python \"{telegram_ask_path}\" for ALL questions and gate decisions "
            f"(notifications_enabled is true — do not output anything to terminal). "
            f"After the spec and plan are written and committed, update VISION.md in {WORK_DIR}: "
            f"add the new feature under Implementiert, move any collected-but-not-chosen ideas to Backlog, "
            f"record key decisions under Entscheidungen."
        )
        exec_cwd = WORK_DIR

    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            timeout=7200, cwd=exec_cwd, env=env
        )
        if result.returncode == 0:
            send_message(MY_CHAT_ID, "✅ Brainstorming abgeschlossen")
        else:
            send_message(MY_CHAT_ID, f"❌ Brainstorming fehlgeschlagen\n{(result.stderr or '')[-300:]}")
    except subprocess.TimeoutExpired:
        send_message(MY_CHAT_ID, "❌ Brainstorming-Timeout (2h überschritten)")
    finally:
        _brainstorming_active = False
```

- [ ] **Step 4: Run test — expect PASS**

```powershell
python -m pytest tests/test_bot.py::test_run_brainstorming_without_slug_uses_work_dir -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C "C:\Projekte\telegram-notion-bot" add bot.py tests/test_bot.py
git -C "C:\Projekte\telegram-notion-bot" commit -m "feat: _run_brainstorming() hub output, auto-push, auto-restart instructions"
```

---

### Task 8: proj_plans callback + /specs hub support

**Files:**
- Modify: `bot.py` — `proj_plans:` callback, `/specs` handler

- [ ] **Step 1: Add proj_plans: callback handler**

In callback dispatcher, add after `feat_sel:` handling:

```python
                elif cb_data.startswith("proj_plans:"):
                    slug = cb_data[11:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    plans_dir = Path(HUB_DIR) / "topics" / slug / "plans"
                    if not plans_dir.exists() or not list(plans_dir.glob("*.md")):
                        send_message(MY_CHAT_ID, f"Keine Pläne für {slug}.")
                    else:
                        files = sorted(plans_dir.glob("*.md"), reverse=True)
                        registry = _load_registry()
                        proj = next((p for p in registry if p["slug"] == slug), {"name": slug})
                        lines = [f"📋 Pläne für {proj['name']}:\n"]
                        for f in files[:10]:
                            stem = f.stem
                            parts = stem.split("-", 3)
                            if len(parts) == 4:
                                lines.append(f"• {parts[0]}-{parts[1]}-{parts[2]} · {parts[3]}")
                            else:
                                lines.append(f"• {stem}")
                        send_message(MY_CHAT_ID, "\n".join(lines))
                    continue
```

- [ ] **Step 2: Update /specs handler to include hub specs**

Replace the existing `/specs` text handler:

```python
            if text.lower() == "/specs":
                lines = ["📋 Specs:\n"]
                hub_topics = Path(HUB_DIR) / "topics"
                if hub_topics.exists():
                    for slug_dir in sorted(hub_topics.iterdir()):
                        if not slug_dir.is_dir():
                            continue
                        specs_subdir = slug_dir / "specs"
                        if not specs_subdir.exists():
                            continue
                        for f in sorted(specs_subdir.glob("*.md")):
                            stem = f.stem
                            parts = stem.split("-", 3)
                            if len(parts) == 4:
                                date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
                                slug_label = parts[3].removesuffix("-design")
                                lines.append(f"{date_str} · [{slug_dir.name}] {slug_label}")
                            else:
                                lines.append(f"[{slug_dir.name}] {stem}")
                local_specs = Path(WORK_DIR) / "docs" / "superpowers" / "specs"
                if local_specs.exists():
                    for f in sorted(local_specs.glob("*.md")):
                        stem = f.stem
                        parts = stem.split("-", 3)
                        if len(parts) == 4:
                            date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
                            slug_label = parts[3].removesuffix("-design")
                            lines.append(f"{date_str} · [bot] {slug_label}")
                        else:
                            lines.append(f"[bot] {stem}")
                if len(lines) == 1:
                    response = "Keine Specs vorhanden."
                else:
                    lines.append("\nNutzung: brainstorming: <idee>, basis: <slug>")
                    response = "\n".join(lines)
                send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                continue
```

- [ ] **Step 3: Commit**

```bash
git -C "C:\Projekte\telegram-notion-bot" add bot.py
git -C "C:\Projekte\telegram-notion-bot" commit -m "feat: proj_plans callback, /specs includes hub specs"
```

---

### Task 9: scripts/restart_bot.sh

**Files:**
- Create: `scripts/restart_bot.sh`

- [ ] **Step 1: Create restart script**

Create `C:\Projekte\telegram-notion-bot\scripts\restart_bot.sh`:

```bash
#!/bin/bash
# Restart the telegram-notion-bot.
# Uses systemd if available (Pi), otherwise kills and relaunches.
systemctl restart telegram-bot 2>/dev/null && exit 0
pkill -f "python.*bot\.py" 2>/dev/null
sleep 1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." && python bot.py &
echo "Bot restarted (pid=$!)"
```

- [ ] **Step 2: Commit**

```bash
git -C "C:\Projekte\telegram-notion-bot" add scripts/restart_bot.sh
git -C "C:\Projekte\telegram-notion-bot" commit -m "feat: add scripts/restart_bot.sh for auto-restart after bot changes"
```

---

### Task 10: HILFE_TEXT update + CLAUDE.md hub section + .env + final push

**Files:**
- Modify: `bot.py` — `HILFE_TEXT`
- Modify: `C:\Users\tjark\.claude\CLAUDE.md`
- Modify: `C:\Projekte\telegram-notion-bot\.env`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write test**

Append to `tests/test_bot.py`:

```python
def test_hilfe_contains_vision_and_projekte():
    from bot import HILFE_TEXT
    assert "vision:" in HILFE_TEXT
    assert "projekte" in HILFE_TEXT
    assert "Projekte & Vision" in HILFE_TEXT
```

- [ ] **Step 2: Run test — expect FAIL**

```powershell
python -m pytest tests/test_bot.py::test_hilfe_contains_vision_and_projekte -v
```

Expected: `AssertionError`

- [ ] **Step 3: Update HILFE_TEXT in bot.py**

Replace `HILFE_TEXT` constant with:

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

🔭 Projekte & Vision
  projekte — Alle Projekte anzeigen (interaktiv)
  vision: <slug> — Vision-Session für ein Projekt starten
  <name>: <frage> — Im Projektkontext fragen
  <name>: tasks — Projekt-Tasks anzeigen
  <name>: task: <text> — Projekt-Task anlegen

📚 Listen
  lern: <thema> — Lernthema speichern
  idee: <text> — Spielidee speichern
  suche: <text> — Alle DBs durchsuchen

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

⚙️ Einstellungen
  /bot-notify an — Benachrichtigungen aktivieren
  /bot-notify aus — Benachrichtigungen deaktivieren"""
```

- [ ] **Step 4: Run test — expect PASS**

```powershell
python -m pytest tests/test_bot.py::test_hilfe_contains_vision_and_projekte -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```powershell
python -m pytest tests/test_bot.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Add hub section to C:\Users\tjark\.claude\CLAUDE.md**

Find the end of the existing CLAUDE.md content and append:

```markdown
# Projects Hub

- Hub repo: `C:\Projekte\projects-hub` (Pi: `~/projects-hub`)
- Env var: `HUB_DIR` — bot reads this; defaults to `WORK_DIR` if not set
- Registry: `HUB_DIR/projects-registry.json` — array of `{slug, name, path, repo, description}`
- Topics: `HUB_DIR/topics/<slug>/` — contains `VISION.md`, `specs/`, `plans/`
- `scheduled_plans.json` lives in `HUB_DIR` (not `WORK_DIR`)
- VISION.md uses `- [ ] Feature` for backlog, `- [x] Feature (implementiert YYYY-MM-DD)` for done
- After implementation: push hub repo + target project repo; if bot.py changed → restart via `scripts/restart_bot.sh`
- Bot restart script: `WORK_DIR/scripts/restart_bot.sh`
```

- [ ] **Step 7: Add HUB_DIR to .env**

In `C:\Projekte\telegram-notion-bot\.env`, add:

```
HUB_DIR=C:\Projekte\projects-hub
```

- [ ] **Step 8: Commit bot.py and tests**

```bash
git -C "C:\Projekte\telegram-notion-bot" add bot.py tests/test_bot.py .env
git -C "C:\Projekte\telegram-notion-bot" commit -m "feat: update HILFE_TEXT, add HUB_DIR to .env"
```

- [ ] **Step 9: Final push**

```bash
git -C "C:\Projekte\telegram-notion-bot" push
git -C "C:\Projekte\projects-hub" push
```

---

## Pi Deployment (after all tasks complete)

Run on Pi via SSH:

```bash
cd ~
git clone https://github.com/DJTJ9/projects-hub.git
echo "HUB_DIR=/home/pi/projects-hub" >> ~/telegram-notion-bot/.env
cd ~/telegram-notion-bot && git pull
bash scripts/restart_bot.sh
```

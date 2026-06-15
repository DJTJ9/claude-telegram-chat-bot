import sys, os, json
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pathlib import Path
from bot import normalize_voice, REPLY_KEYBOARD, HILFE_TEXT, MOIN_SYSTEM_PROMPT, HABITS_DATA_SOURCE_ID, STATUS_SYSTEM_PROMPT, pending_task_input, load_reminders, save_reminders, REMINDER_PARSE_SYSTEM_PROMPT, SUCHE_SYSTEM_PROMPT

def test_doppelpunkt_lower():
    assert normalize_voice("task doppelpunkt bug fixen") == "task: bug fixen"

def test_doppelpunkt_upper():
    assert normalize_voice("Task Doppelpunkt bug fixen") == "Task: bug fixen"

def test_komma():
    assert normalize_voice("eins komma fünf") == "eins, fünf"

def test_punkt():
    assert normalize_voice("Ende punkt") == "Ende."

def test_no_change():
    assert normalize_voice("moin") == "moin"

def test_combined():
    assert normalize_voice("status doppelpunkt sport erledigt") == "status: sport erledigt"

def test_status_prefix_detection():
    text = "status: sport erledigt"
    assert text.lower().startswith("status:")
    assert text[7:].strip() == "sport erledigt"

def test_status_prefix_voice():
    text = normalize_voice("status doppelpunkt sport erledigt")
    assert text.lower().startswith("status:")
    assert text[7:].strip() == "sport erledigt"

def test_keyboard_structure():
    assert "keyboard" in REPLY_KEYBOARD
    rows = REPLY_KEYBOARD["keyboard"]
    all_buttons = [btn for row in rows for btn in row]
    assert "moin" in all_buttons
    assert "status:" in all_buttons
    assert "hilfe" in all_buttons
    assert REPLY_KEYBOARD["resize_keyboard"] is True

def test_hilfe_contains_all_commands():
    for cmd in ["moin", "abend", "woche", "task:", "status:", "fokus:", "verschieben:", "lern:", "idee:"]:
        assert cmd in HILFE_TEXT, f"Missing command in HILFE_TEXT: {cmd}"

def test_habit_prefix_detection():
    text = "habit: Sport täglich"
    assert text.lower().startswith("habit:")
    assert text[6:].strip() == "Sport täglich"

def test_habit_prefix_empty():
    text = "habit:"
    assert text[6:].strip() == ""

def test_hilfe_contains_habit():
    assert "habit:" in HILFE_TEXT

def test_moin_prompt_includes_habits_db():
    assert HABITS_DATA_SOURCE_ID in MOIN_SYSTEM_PROMPT

def test_moin_prompt_includes_habits_section():
    assert "Habits heute" in MOIN_SYSTEM_PROMPT

def test_status_prompt_includes_habits_db():
    assert HABITS_DATA_SOURCE_ID in STATUS_SYSTEM_PROMPT

def test_status_prompt_includes_recurrence_logic():
    assert "Nächste Fälligkeit" in STATUS_SYSTEM_PROMPT

def test_pending_task_input_is_dict():
    assert isinstance(pending_task_input, dict)

def test_task_bare_command_detection():
    text = "task:"
    assert text.lower().startswith("task:")
    assert text[5:].strip() == ""

from bot import load_settings, save_settings

def test_load_settings_default(tmp_path):
    assert load_settings(tmp_path) == {"notifications_enabled": True}

def test_load_settings_reads_file(tmp_path):
    (tmp_path / "settings.json").write_text('{"notifications_enabled": false}')
    assert load_settings(tmp_path) == {"notifications_enabled": False}

def test_save_settings(tmp_path):
    save_settings({"notifications_enabled": False}, tmp_path)
    data = json.loads((tmp_path / "settings.json").read_text())
    assert data == {"notifications_enabled": False}

def test_save_load_roundtrip(tmp_path):
    save_settings({"notifications_enabled": True}, tmp_path)
    assert load_settings(tmp_path) == {"notifications_enabled": True}

def test_load_settings_corrupt_file(tmp_path):
    (tmp_path / "settings.json").write_text("{bad json}")
    assert load_settings(tmp_path) == {"notifications_enabled": True}

def test_bot_notify_in_hilfe():
    from bot import HILFE_TEXT
    assert "/bot-notify" in HILFE_TEXT

def test_load_reminders_empty(tmp_path, monkeypatch):
    import bot
    monkeypatch.setattr(bot, "REMINDERS_PATH", tmp_path / "reminders.json")
    assert bot.load_reminders() == []

def test_save_load_reminders_roundtrip(tmp_path, monkeypatch):
    import bot
    monkeypatch.setattr(bot, "REMINDERS_PATH", tmp_path / "reminders.json")
    data = [{"id": "abc12345", "text": "Test", "due": "2026-06-12T14:00:00", "status": "pending", "chat_id": 123, "created": "2026-06-11T10:00:00"}]
    bot.save_reminders(data)
    assert bot.load_reminders() == data

def test_load_reminders_corrupt(tmp_path, monkeypatch):
    import bot
    p = tmp_path / "reminders.json"
    p.write_text("{bad json}", encoding="utf-8")
    monkeypatch.setattr(bot, "REMINDERS_PATH", p)
    assert bot.load_reminders() == []

def test_reminder_parse_prompt_contains_rules():
    assert "morgen" in REMINDER_PARSE_SYSTEM_PROMPT
    assert "JSON" in REMINDER_PARSE_SYSTEM_PROMPT
    assert "due" in REMINDER_PARSE_SYSTEM_PROMPT

def test_hilfe_contains_erinnerungen():
    assert "erinnere" in HILFE_TEXT
    assert "erinnerungen" in HILFE_TEXT

from bot import TERMIN_SYSTEM_PROMPT

def test_termin_system_prompt_contains_datasource():
    assert "c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0" in TERMIN_SYSTEM_PROMPT

def test_termin_system_prompt_datetime_format():
    assert "YYYY-MM-DDTHH:MM:SS" in TERMIN_SYSTEM_PROMPT

def test_termin_system_prompt_default_time():
    assert "09:00" in TERMIN_SYSTEM_PROMPT

def test_termin_system_prompt_response_format():
    assert "📅 Termin angelegt" in TERMIN_SYSTEM_PROMPT

def test_termin_prefix_detection():
    text = "termin: Arzttermin morgen um 14:00"
    assert text.lower().startswith("termin:")

def test_termin_prefix_extraction():
    text = "termin: Arzttermin morgen um 14:00"
    assert text[7:].strip() == "Arzttermin morgen um 14:00"

def test_termin_empty_detection():
    text = "termin:"
    assert text[7:].strip() == ""

def test_hilfe_contains_termin():
    assert "termin:" in HILFE_TEXT

def test_moin_prompt_includes_termine_section():
    assert "Termine heute" in MOIN_SYSTEM_PROMPT

def test_moin_prompt_includes_tasks_section():
    assert "Tasks heute" in MOIN_SYSTEM_PROMPT

def test_moin_prompt_includes_datetime_distinction():
    assert "Zeitanteil" in MOIN_SYSTEM_PROMPT

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

# --- teach: handler tests ---

def test_teach_prefix_detection():
    text = "teach: Python Grundlagen, weil ich Skripte automatisieren will"
    assert text.lower().startswith("teach:")
    assert text.split(":", 1)[1].strip() == "Python Grundlagen, weil ich Skripte automatisieren will"

def test_teach_slash_prefix_detection():
    text = "/teach Python Grundlagen"
    assert text.lower().startswith("/teach")
    assert text[6:].strip() == "Python Grundlagen"

def test_teach_empty_detection():
    text = "teach:"
    assert text.split(":", 1)[1].strip() == ""

def test_teach_is_known_command():
    known_prefixes = (
        "task:", "status:", "fokus:", "verschieben:", "lern:",
        "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
        "implement-plan:", "abort-plan:", "backlog:", "suche:",
    )
    assert "teach: Python".lower().startswith(known_prefixes)

def test_run_teach_exists():
    from bot import _run_teach
    assert callable(_run_teach)

def test_hilfe_contains_teach_with_context():
    from bot import HILFE_TEXT
    assert "teach:" in HILFE_TEXT
    assert "warum" in HILFE_TEXT.lower() or "thema" in HILFE_TEXT.lower()

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

# --- Task 2: HUB_DIR + registry tests ---

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

# --- Task 3: _parse_vision_features tests ---

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

# --- Task 4: _create_project_entry tests ---

def test_create_project_entry_adds_to_registry(tmp_path, monkeypatch):
    import bot
    monkeypatch.setattr(bot, "HUB_DIR", str(tmp_path))
    (tmp_path / "projects-registry.json").write_text("[]")
    monkeypatch.setattr(bot, "_vision_active", False)
    monkeypatch.setattr(bot, "send_message", lambda *a, **kw: None)
    monkeypatch.setattr(bot, "_run_vision", lambda slug: None)
    bot._create_project_entry("my-app", "MyApp", path="C:\\Projekte\\MyApp", chat_id=123)
    registry = bot._load_registry()
    assert any(p["slug"] == "my-app" for p in registry)
    assert (tmp_path / "topics" / "my-app" / "specs").exists()
    assert (tmp_path / "topics" / "my-app" / "plans").exists()

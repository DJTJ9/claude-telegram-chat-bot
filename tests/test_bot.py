import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pathlib import Path
from bot import normalize_voice, REPLY_KEYBOARD, HILFE_TEXT, MOIN_SYSTEM_PROMPT, HABITS_DATA_SOURCE_ID, STATUS_SYSTEM_PROMPT, pending_task_input, load_reminders, save_reminders, REMINDER_PARSE_SYSTEM_PROMPT

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

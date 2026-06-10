import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot import normalize_voice, REPLY_KEYBOARD, HILFE_TEXT

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

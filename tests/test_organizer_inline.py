import sys, os, json, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("TOKEN_ORGANIZER", "test")

# ── Prompt schema tests ──────────────────────────────────────────────────────

SAMPLE_MOIN_JSON = json.dumps({
    "date": "2026-06-22",
    "appointments": [{"name": "Zahnarzt", "time": "14:00", "id": "abc123"}],
    "tasks": [{"name": "PR Review", "prio": "Hoch", "projekt": "dart-app", "id": "def456"}],
    "habits": [{"name": "Sport", "interval": 1, "id": "ghi789"}],
})

SAMPLE_ABEND_JSON = json.dumps({
    "date": "2026-06-22",
    "done": [{"name": "PR Review", "projekt": "dart-app"}],
    "open": [{"name": "Einkaufen", "prio": "Mittel", "projekt": None, "id": "jkl012"}],
    "missed_habits": [{"name": "Sport", "id": "mno345"}],
    "projekt_bilanz": [{"name": "dart-app", "done": 1, "open": 0}],
})

def test_moin_json_parses():
    data = json.loads(SAMPLE_MOIN_JSON)
    assert data["tasks"][0]["prio"] == "Hoch"
    assert data["habits"][0]["interval"] == 1
    assert data["appointments"][0]["time"] == "14:00"

def test_abend_json_parses():
    data = json.loads(SAMPLE_ABEND_JSON)
    assert data["open"][0]["id"] == "jkl012"
    assert data["missed_habits"][0]["name"] == "Sport"
    assert data["projekt_bilanz"][0]["done"] == 1

# ── Pure helper function tests ───────────────────────────────────────────────

def test_extract_name_plain():
    from bots.organizer import _extract_name_from_message
    assert _extract_name_from_message("🔴 PR Review  →dart-app") == "PR Review"

def test_extract_name_no_prio():
    from bots.organizer import _extract_name_from_message
    assert _extract_name_from_message("Einkaufen") == "Einkaufen"

def test_extract_name_mittel():
    from bots.organizer import _extract_name_from_message
    assert _extract_name_from_message("🟡 Einkaufen") == "Einkaufen"

def test_extract_name_multiline():
    from bots.organizer import _extract_name_from_message
    assert _extract_name_from_message("⏳ Code Review  →dart-app\n🔴 (Hoch)") == "Code Review"

def test_resolve_date_key_morgen():
    from bots.organizer import _resolve_date_key
    assert _resolve_date_key("morgen", "2026-06-22") == "2026-06-23"

def test_resolve_date_key_uebermorgen():
    from bots.organizer import _resolve_date_key
    assert _resolve_date_key("uebermorgen", "2026-06-22") == "2026-06-24"

def test_resolve_date_key_naechste_woche():
    from bots.organizer import _resolve_date_key
    assert _resolve_date_key("naechste_woche", "2026-06-22") == "2026-06-29"

def test_resolve_date_key_heute():
    from bots.organizer import _resolve_date_key
    assert _resolve_date_key("heute", "2026-06-22") == "2026-06-22"

def test_resolve_value_prio():
    from bots.organizer import _resolve_value
    assert _resolve_value("prio", "hoch", "2026-06-22") == "Hoch"
    assert _resolve_value("prio", "mittel", "2026-06-22") == "Mittel"
    assert _resolve_value("prio", "niedrig", "2026-06-22") == "Niedrig"

def test_resolve_value_bereich():
    from bots.organizer import _resolve_value
    assert _resolve_value("bereich", "arbeit", "2026-06-22") == "Arbeit"
    assert _resolve_value("bereich", "gesundheit", "2026-06-22") == "Gesundheit"

def test_resolve_value_datum():
    from bots.organizer import _resolve_value
    assert _resolve_value("datum", "morgen", "2026-06-22") == "2026-06-23"

def test_task_buttons_structure():
    from bots.organizer import _task_buttons
    buttons = _task_buttons("abc123def456")
    assert len(buttons) == 1
    assert len(buttons[0]) == 3
    assert buttons[0][0]["callback_data"] == "done:abc123def456"
    assert buttons[0][1]["callback_data"] == "reschedule:abc123def456"
    assert buttons[0][2]["callback_data"] == "edit:abc123def456"

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

# ── Message sender tests ─────────────────────────────────────────────────────

from unittest.mock import patch, MagicMock

def test_send_task_message_builds_correct_text():
    from bots.organizer import _send_task_message
    task = {"name": "PR Review", "prio": "Hoch", "projekt": "dart-app", "id": "abc123def456"}
    with patch("bots.organizer.send_message") as mock_send:
        _send_task_message(task)
        args = mock_send.call_args[0]
        text = args[2]
        markup = args[3] if len(args) > 3 else mock_send.call_args[1].get("reply_markup")
        assert "🔴" in text
        assert "PR Review" in text
        assert "→dart-app" in text
        assert markup["inline_keyboard"][0][0]["callback_data"] == "done:abc123def456"

def test_send_task_message_no_projekt():
    from bots.organizer import _send_task_message
    task = {"name": "Einkaufen", "prio": "Mittel", "projekt": None, "id": "xyz999"}
    with patch("bots.organizer.send_message") as mock_send:
        _send_task_message(task)
        text = mock_send.call_args[0][2]
        assert "→" not in text
        assert "Einkaufen" in text

def test_send_habit_message_taglich():
    from bots.organizer import _send_habit_message
    habit = {"name": "Sport", "interval": 1, "id": "hab001"}
    with patch("bots.organizer.send_message") as mock_send:
        _send_habit_message(habit)
        args = mock_send.call_args[0]
        text = args[2]
        markup = args[3] if len(args) > 3 else mock_send.call_args[1].get("reply_markup")
        assert "Sport" in text
        assert "täglich" in text
        assert markup["inline_keyboard"][0][0]["callback_data"] == "habit_done:hab001"

def test_send_habit_message_interval():
    from bots.organizer import _send_habit_message
    habit = {"name": "Yoga", "interval": 3, "id": "hab002"}
    with patch("bots.organizer.send_message") as mock_send:
        _send_habit_message(habit)
        assert "alle 3 Tage" in mock_send.call_args[0][2]

def test_send_moin_messages_header_task_habit():
    from bots.organizer import _send_moin_messages
    data = json.loads(SAMPLE_MOIN_JSON)
    with patch("bots.organizer.send_message") as mock_send:
        _send_moin_messages(data)
        all_texts = [c[0][2] for c in mock_send.call_args_list]
        assert any("Guten Morgen" in t for t in all_texts)
        assert any("Zahnarzt" in t for t in all_texts)
        assert any("PR Review" in t for t in all_texts)
        assert any("Sport" in t for t in all_texts)

def test_send_abend_messages_header_open_missed():
    from bots.organizer import _send_abend_messages
    data = json.loads(SAMPLE_ABEND_JSON)
    with patch("bots.organizer.send_message") as mock_send:
        _send_abend_messages(data)
        all_texts = [c[0][2] for c in mock_send.call_args_list]
        assert any("Tagesabschluss" in t for t in all_texts)
        assert any("PR Review" in t for t in all_texts)
        assert any("Einkaufen" in t for t in all_texts)
        assert any("Sport" in t for t in all_texts)

def test_apply_task_update_calls_claude():
    from bots.organizer import _apply_task_update
    with patch("bots.organizer.run_claude", return_value="✏️ Prio → Hoch") as mock_claude:
        result = _apply_task_update("abc123", "prio", "Hoch", "2026-06-22")
        assert result == "✏️ Prio → Hoch"
        prompt = mock_claude.call_args[0][0]
        assert "abc123" in prompt
        assert "prio" in prompt
        assert "Hoch" in prompt

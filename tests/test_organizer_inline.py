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

# ── Callback handler tests ───────────────────────────────────────────────────

def _make_cq(data: str, text: str = "🔴 PR Review  →dart-app", msg_id: int = 42, chat_id: int = 123):
    return {
        "id": "cq1",
        "from": {"id": chat_id},
        "data": data,
        "message": {"message_id": msg_id, "chat": {"id": chat_id}, "text": text},
    }

def test_callback_done_updates_message():
    from bots.organizer import _handle_callback
    import bots.organizer as org
    org.callback_state.clear()
    cq = _make_cq("done:abc123def456")
    with patch("bots.organizer.run_claude", return_value="✏️ status → Done"), \
         patch("bots.organizer.edit_message") as mock_edit, \
         patch("bots.organizer._run_archive_once"), \
         patch("bots.organizer.threading"):
        _handle_callback(cq)
        mock_edit.assert_called_once()
        text = mock_edit.call_args[0][3]
        assert "✅" in text
        assert "PR Review" in text

def test_callback_habit_done():
    from bots.organizer import _handle_callback
    cq = _make_cq("habit_done:hab001", text="🔄 Sport (täglich)")
    with patch("bots.organizer.run_claude", return_value="✅ Sport — nächste Fälligkeit: 23.06.2026"), \
         patch("bots.organizer.edit_message") as mock_edit:
        _handle_callback(cq)
        text = mock_edit.call_args[0][3]
        assert "Sport" in text

def test_callback_reschedule_shows_buttons():
    from bots.organizer import _handle_callback
    cq = _make_cq("reschedule:abc123")
    with patch("bots.organizer.edit_message") as mock_edit:
        _handle_callback(cq)
        markup = mock_edit.call_args[0][4]
        all_texts = [btn["text"] for row in markup["inline_keyboard"] for btn in row]
        assert "Morgen" in all_texts
        assert "Übermorgen" in all_texts

def test_callback_reschedule_d_updates_task():
    from bots.organizer import _handle_callback
    cq = _make_cq("reschedule_d:abc123:morgen")
    with patch("bots.organizer._apply_task_update") as mock_update, \
         patch("bots.organizer.edit_message"):
        _handle_callback(cq)
        mock_update.assert_called_once()
        pid, field = mock_update.call_args[0][0], mock_update.call_args[0][1]
        assert pid == "abc123"
        assert field == "datum"

def test_callback_edit_shows_field_buttons():
    from bots.organizer import _handle_callback
    cq = _make_cq("edit:abc123")
    with patch("bots.organizer.edit_message") as mock_edit:
        _handle_callback(cq)
        markup = mock_edit.call_args[0][4]
        all_texts = [btn["text"] for row in markup["inline_keyboard"] for btn in row]
        assert "Priorität" in all_texts
        assert "Datum" in all_texts
        assert "Bereich" in all_texts
        assert "Notiz" in all_texts

def test_callback_edit_f_prio_shows_values():
    from bots.organizer import _handle_callback
    cq = _make_cq("edit_f:abc123:prio")
    with patch("bots.organizer.edit_message") as mock_edit:
        _handle_callback(cq)
        markup = mock_edit.call_args[0][4]
        all_texts = [btn["text"] for row in markup["inline_keyboard"] for btn in row]
        assert "Hoch" in all_texts
        assert "Mittel" in all_texts
        assert "Niedrig" in all_texts

def test_callback_edit_v_prio_applies_update():
    from bots.organizer import _handle_callback
    cq = _make_cq("edit_v:abc123:prio:hoch")
    with patch("bots.organizer._apply_task_update") as mock_update, \
         patch("bots.organizer.edit_message"):
        _handle_callback(cq)
        mock_update.assert_called_once()
        assert mock_update.call_args[0][2] == "Hoch"

def test_callback_edit_f_notiz_sets_state():
    from bots.organizer import _handle_callback
    import bots.organizer as org
    org.callback_state.clear()
    cq = _make_cq("edit_f:abc123:notiz", chat_id=999)
    with patch("bots.organizer.send_message"), \
         patch("bots.organizer.edit_message"):
        _handle_callback(cq)
        assert 999 in org.callback_state
        assert org.callback_state[999]["action"] == "edit_text"
        assert org.callback_state[999]["field"] == "notiz"

# ── Integration: _dispatch_command ──────────────────────────────────────────

def test_dispatch_moin_calls_send_moin_messages():
    from bots.organizer import _dispatch_command
    with patch("bots.organizer.run_claude_parse", return_value=SAMPLE_MOIN_JSON), \
         patch("bots.organizer._send_moin_messages") as mock_fn, \
         patch("bots.organizer.send_message"):
        _dispatch_command("moin", 123)
        mock_fn.assert_called_once()
        data = mock_fn.call_args[0][0]
        assert data["tasks"][0]["name"] == "PR Review"

def test_dispatch_moin_fallback_on_bad_json():
    from bots.organizer import _dispatch_command
    with patch("bots.organizer.run_claude_parse", return_value="not valid json"), \
         patch("bots.organizer.run_claude", return_value="🌅 Guten Morgen!"), \
         patch("bots.organizer.send_message") as mock_send:
        _dispatch_command("moin", 123)
        texts = [c[0][2] for c in mock_send.call_args_list]
        assert any("Guten Morgen" in t for t in texts)

def test_dispatch_edit_calls_claude():
    from bots.organizer import _dispatch_command
    with patch("bots.organizer.run_claude", return_value="✏️ PR Review · Priorität → Hoch") as mock_claude, \
         patch("bots.organizer.send_message") as mock_send:
        _dispatch_command("edit: PR Review prio hoch", 123)
        assert mock_claude.called
        assert any("✏️" in c[0][2] for c in mock_send.call_args_list)

def test_dispatch_edit_empty_shows_usage():
    from bots.organizer import _dispatch_command
    with patch("bots.organizer.send_message") as mock_send:
        _dispatch_command("edit:", 123)
        text = mock_send.call_args[0][2]
        assert "Nutzung" in text


def test_run_plan_sets_active_session(tmp_path, monkeypatch):
    import bots.organizer as org
    import subprocess as sp
    monkeypatch.setattr(org, "WORK_DIR", tmp_path)

    captured_sessions = []

    def tracking_save(s):
        captured_sessions.append(s.get("active_session"))

    class FakeResult:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(org, "save_settings", tracking_save)
    monkeypatch.setattr(sp, "run", lambda *a, **k: FakeResult())
    monkeypatch.setattr(org, "send_message", lambda *a, **k: None)
    monkeypatch.setattr(org, "load_plans", lambda: [])
    monkeypatch.setattr(org, "save_plans", lambda x: None)

    plan_dir = tmp_path / "docs" / "superpowers" / "plans"
    plan_dir.mkdir(parents=True)
    (plan_dir / "test.md").write_text("# Plan")

    org._run_plan("docs/superpowers/plans/test.md")

    assert "organizer" in captured_sessions
    assert None in captured_sessions

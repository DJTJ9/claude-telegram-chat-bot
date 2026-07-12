import os, sys, json
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("TOKEN_BRAIN", "test_token")
os.environ.setdefault("CHAT_ID", "12345")
os.environ.setdefault("GROQ_API_KEY", "x")
sys.path.insert(0, str(Path(__file__).parent.parent))


def _write_wait(tmp_path, session_id="s1", **over):
    data = {"slug": "dev-skill", "pane": "%5",
            "question": "Frage? A) Ja B) Nein", "timestamp": 1234.0, **over}
    (tmp_path / f"pending_wait_{session_id}.json").write_text(json.dumps(data))
    return data


def _reset(brain):
    brain._wait_notified.clear()
    brain._wait_state = None


def test_check_wait_notify_sends_message(tmp_path):
    import bots.brain as brain
    _reset(brain)
    _write_wait(tmp_path)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms:
        brain._check_wait_notify()
    ms.assert_called_once()
    text = ms.call_args[0][2]
    assert "dev-skill" in text
    assert "Frage?" in text
    assert brain._wait_state == {"session_id": "s1", "pane": "%5",
                                 "question": "Frage? A) Ja B) Nein"}
    _reset(brain)


def test_check_wait_notify_dedupes_same_timestamp(tmp_path):
    import bots.brain as brain
    _reset(brain)
    _write_wait(tmp_path)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms:
        brain._check_wait_notify()
        brain._check_wait_notify()
    ms.assert_called_once()
    _reset(brain)


def test_check_wait_notify_renotifies_new_timestamp(tmp_path):
    import bots.brain as brain
    _reset(brain)
    _write_wait(tmp_path, timestamp=1234.0)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms:
        brain._check_wait_notify()
        _write_wait(tmp_path, timestamp=9999.0)
        brain._check_wait_notify()
    assert ms.call_count == 2
    _reset(brain)


def test_wait_reply_already_answered_when_file_gone(tmp_path):
    import bots.brain as brain
    _reset(brain)
    brain._wait_state = {"session_id": "s1", "pane": "%5", "question": "Q"}
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms:
        assert brain._handle_wait_reply("B") is True
    assert brain._wait_state is None
    assert "bereits im Terminal beantwortet" in ms.call_args[0][2]
    _reset(brain)


def test_wait_reply_sends_keys_when_prompt_open(tmp_path):
    import bots.brain as brain
    _reset(brain)
    _write_wait(tmp_path)
    brain._wait_state = {"session_id": "s1", "pane": "%5",
                         "question": "Frage? A) Ja B) Nein"}
    cap = MagicMock()
    cap.stdout = "blabla\nFrage? A) Ja B) Nein\n> "
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.subprocess.run", return_value=cap) as mrun, \
         patch("bots.brain.send_message") as ms:
        assert brain._handle_wait_reply("B") is True
    calls = [c.args[0] for c in mrun.call_args_list]
    assert ["tmux", "send-keys", "-t", "%5", "-l", "B"] in calls
    assert ["tmux", "send-keys", "-t", "%5", "Enter"] in calls
    assert not (tmp_path / "pending_wait_s1.json").exists()
    assert brain._wait_state is None
    assert "B" in ms.call_args[0][2]
    _reset(brain)


def test_wait_reply_first_wins_when_prompt_moved_on(tmp_path):
    import bots.brain as brain
    _reset(brain)
    _write_wait(tmp_path)
    brain._wait_state = {"session_id": "s1", "pane": "%5",
                         "question": "Frage? A) Ja B) Nein"}
    cap = MagicMock()
    cap.stdout = "ganz anderer Bildschirminhalt"
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.subprocess.run", return_value=cap) as mrun, \
         patch("bots.brain.send_message") as ms:
        assert brain._handle_wait_reply("B") is True
    sent = [c.args[0] for c in mrun.call_args_list if c.args[0][1] == "send-keys"]
    assert sent == []
    assert not (tmp_path / "pending_wait_s1.json").exists()
    assert "bereits im Terminal beantwortet" in ms.call_args[0][2]
    _reset(brain)


def test_wait_reply_returns_false_without_state():
    import bots.brain as brain
    _reset(brain)
    assert brain._handle_wait_reply("B") is False


def test_handle_message_routes_to_wait_reply(tmp_path):
    import bots.brain as brain
    _reset(brain)
    brain._wait_state = {"session_id": "s1", "pane": "%5", "question": "Q"}
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms:
        brain._handle_message({"text": "B", "chat": {"id": int(brain.CHAT_ID)}})
    assert "bereits im Terminal beantwortet" in ms.call_args[0][2]
    _reset(brain)

import os, sys, json
from pathlib import Path
from unittest.mock import patch

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


def test_check_wait_notify_sends_message(tmp_path):
    import bots.brain as brain
    _reset(brain)
    _write_wait(tmp_path)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms, \
         patch("bots.brain._get_dev_status", return_value=("Bug: X", "implement")):
        brain._check_wait_notify()
    ms.assert_called_once()
    text = ms.call_args[0][2]
    assert "dev-skill" in text
    assert "implement" in text
    assert "Frage?" not in text
    _reset(brain)


def test_check_wait_notify_omits_phase_when_status_missing(tmp_path):
    import bots.brain as brain
    _reset(brain)
    _write_wait(tmp_path)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms, \
         patch("bots.brain._get_dev_status", return_value=("", "")):
        brain._check_wait_notify()
    text = ms.call_args[0][2]
    assert "dev-skill" in text
    assert "()" not in text
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

import os, sys, json
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("TOKEN_BRAIN", "test_token")
os.environ.setdefault("TOKEN_NOTIFICATIONS", "test_token_notify")
os.environ.setdefault("CHAT_ID", "12345")
os.environ.setdefault("GROQ_API_KEY", "x")
sys.path.insert(0, str(Path(__file__).parent.parent))


def _write_wait(tmp_path, session_id="s1", **over):
    data = {"slug": "dev-skill", "pane": "%5",
            "question": "Frage? A) Ja B) Nein", "timestamp": 1234.0, **over}
    (tmp_path / f"pending_wait_{session_id}.json").write_text(json.dumps(data))
    return data


def test_check_wait_notify_sends_message(tmp_path):
    import bots.brain as brain
    _write_wait(tmp_path)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms, \
         patch("bots.brain._get_dev_status", return_value=("Bug: X", "implement")):
        brain._check_wait_notify()
    ms.assert_called_once()
    assert ms.call_args[0][0] == brain.NOTIFY_TOKEN
    assert ms.call_args[0][0] != brain.TOKEN
    text = ms.call_args[0][2]
    assert "dev-skill" in text
    assert "implement" in text
    assert "Frage?" not in text


def test_check_wait_notify_omits_phase_when_status_missing(tmp_path):
    import bots.brain as brain
    _write_wait(tmp_path)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms, \
         patch("bots.brain._get_dev_status", return_value=("", "")):
        brain._check_wait_notify()
    text = ms.call_args[0][2]
    assert "dev-skill" in text
    assert "()" not in text


def test_check_wait_notify_dedupes_same_timestamp(tmp_path):
    import bots.brain as brain
    _write_wait(tmp_path)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms:
        brain._check_wait_notify()
        brain._check_wait_notify()
    ms.assert_called_once()


def test_check_wait_notify_renotifies_new_timestamp(tmp_path):
    import bots.brain as brain
    _write_wait(tmp_path, timestamp=1234.0)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms:
        brain._check_wait_notify()
        _write_wait(tmp_path, timestamp=9999.0)
        brain._check_wait_notify()
    assert ms.call_count == 2


def test_check_wait_notify_gated_off(tmp_path):
    import bots.brain as brain
    _write_wait(tmp_path)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.load_settings", return_value={"wait_notify_enabled": False}), \
         patch("bots.brain.send_message") as ms:
        brain._check_wait_notify()
    ms.assert_not_called()


def test_notify_deduped_across_restart_via_marker(tmp_path):
    import bots.brain as brain
    _write_wait(tmp_path, timestamp=111.0)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms:
        brain._check_wait_notify()
        # Restart simulieren: etwaiger In-Memory-State weg, Marker-Datei bleibt
        if hasattr(brain, "_wait_notified"):
            brain._wait_notified.clear()
        brain._check_wait_notify()
    ms.assert_called_once()  # M4: Marker verhindert Doppel-Notify
    assert (tmp_path / "pending_wait_s1.notified").read_text() == "111.0"


def test_phase_suffix_from_feature_file(tmp_path):
    import bots.brain as brain
    fdir = tmp_path / "topics" / "dev-skill" / "features"
    fdir.mkdir(parents=True)
    (fdir / "email-auth.md").write_text("# E-Mail Auth\nPhase: implement\n")
    _write_wait(tmp_path, feature="email-auth", timestamp=1.0)
    with patch.object(brain, "WORK_DIR", tmp_path), \
         patch.object(brain, "HUB_DIR", tmp_path), \
         patch("bots.brain.send_message") as ms:
        brain._check_wait_notify()
    text = ms.call_args[0][2]
    assert "dev-skill" in text
    assert "(implement)" in text


def test_main_keyboard_has_toggle_row_on():
    import bots.brain as brain
    with patch("bots.brain.load_settings", return_value={"wait_notify_enabled": True}):
        kb = brain._build_main_keyboard([])
    flat = [b for row in kb for b in row]
    toggle = [b for b in flat if b["callback_data"] == "toggle_wait_notify"]
    assert len(toggle) == 1
    assert "An" in toggle[0]["text"]


def test_main_keyboard_toggle_row_off():
    import bots.brain as brain
    with patch("bots.brain.load_settings", return_value={"wait_notify_enabled": False}):
        kb = brain._build_main_keyboard([])
    toggle = [b for row in kb for b in row if b["callback_data"] == "toggle_wait_notify"]
    assert "Aus" in toggle[0]["text"]


def test_toggle_row_is_first_above_projects():
    import bots.brain as brain
    projects = [{"name": "Proj A", "slug": "a"}, {"name": "Proj B", "slug": "b"}]
    with patch("bots.brain.load_settings", return_value={"wait_notify_enabled": True}):
        kb = brain._build_main_keyboard(projects)
    assert kb[0][0]["callback_data"] == "toggle_wait_notify"
    assert kb[1][0]["callback_data"] == "proj:a"

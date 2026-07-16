import json, tempfile
from pathlib import Path

def test_load_settings_defaults():
    with tempfile.TemporaryDirectory() as d:
        from core.settings import load_settings
        s = load_settings(d)
        assert "notifications_enabled" not in s
        assert s["active_session"] is None
        assert s["active_session_bot"] is None


def test_settings_json_has_no_notifications_flag():
    data = json.loads((Path(__file__).parent.parent / "settings.json").read_text())
    assert "notifications_enabled" not in data

def test_save_and_load():
    with tempfile.TemporaryDirectory() as d:
        from core.settings import load_settings, save_settings
        s = load_settings(d)
        s["active_session"] = "brainstorming"
        s["active_session_bot"] = "TOKEN_BRAIN"
        save_settings(s, d)
        s2 = load_settings(d)
        assert s2["active_session"] == "brainstorming"
        assert s2["active_session_bot"] == "TOKEN_BRAIN"


def test_update_settings_merges_defaults_and_persists():
    with tempfile.TemporaryDirectory() as d:
        from core.settings import update_settings, load_settings

        def m(s):
            s["active_session"] = "dev"

        out = update_settings(m, d)
        # defaults merged in
        assert out["active_session"] == "dev"
        assert out["active_session_bot"] is None
        # persisted to disk
        assert load_settings(d)["active_session"] == "dev"


def test_update_settings_return_new_dict():
    with tempfile.TemporaryDirectory() as d:
        from core.settings import update_settings, load_settings
        update_settings(lambda s: {**s, "active_session": "teach"}, d)
        assert load_settings(d)["active_session"] == "teach"

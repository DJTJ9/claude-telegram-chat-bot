import json, tempfile
from pathlib import Path

def test_load_settings_defaults():
    with tempfile.TemporaryDirectory() as d:
        from core.settings import load_settings
        s = load_settings(d)
        assert s["notifications_enabled"] == True
        assert s["active_session"] is None
        assert s["active_session_bot"] is None

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

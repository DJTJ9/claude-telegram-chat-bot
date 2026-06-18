import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch
import bots.permissions as mod


def test_get_updates_called_with_timeout_1(tmp_path, monkeypatch):
    """permissions bot must poll with timeout=1 to avoid >1s file-check delay."""
    calls = []

    def fake_get_updates(token, offset=None, timeout=30):
        calls.append(timeout)
        raise KeyboardInterrupt  # stop the loop after first call

    monkeypatch.setenv("TOKEN_PERMISSIONS", "fake_token")
    monkeypatch.setenv("CHAT_ID", "12345")

    with patch.object(mod, "get_updates", fake_get_updates), \
         patch.object(mod, "WORK_DIR", tmp_path):
        try:
            mod.main()
        except KeyboardInterrupt:
            pass

    assert calls, "get_updates was never called"
    assert calls[0] == 1, f"Expected timeout=1, got timeout={calls[0]}"

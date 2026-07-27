import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_flip_from_default_true_to_false():
    with tempfile.TemporaryDirectory() as d:
        from scripts.toggle_wait_notify import set_wait_notify
        from core.settings import load_settings
        assert set_wait_notify(None, d) is False
        assert load_settings(d)["wait_notify_enabled"] is False


def test_flip_twice_returns_true():
    with tempfile.TemporaryDirectory() as d:
        from scripts.toggle_wait_notify import set_wait_notify
        set_wait_notify(None, d)
        assert set_wait_notify(None, d) is True


def test_explicit_on_and_off():
    with tempfile.TemporaryDirectory() as d:
        from scripts.toggle_wait_notify import set_wait_notify
        from core.settings import load_settings
        assert set_wait_notify(False, d) is False
        assert set_wait_notify(True, d) is True
        assert load_settings(d)["wait_notify_enabled"] is True

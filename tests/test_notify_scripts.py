import sys, json, subprocess, os
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
NOTIFY_SCRIPT = PROJECT_DIR / "scripts" / "telegram_notify.py"


def test_notify_exits_silently_without_token(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"notifications_enabled": True, "active_session": None}))
    result = subprocess.run(
        [sys.executable, str(NOTIFY_SCRIPT), "Test message"],
        capture_output=True, text=True, timeout=5,
        env={**os.environ, "WORK_DIR": str(tmp_path),
             "TOKEN_PERMISSIONS": "", "TOKEN_BRAIN": "", "TOKEN_TEACH": "", "TOKEN_ORGANIZER": ""}
    )
    assert result.returncode == 0


def test_notify_uses_get_notify_token():
    src = (PROJECT_DIR / "scripts" / "telegram_notify.py").read_text()
    assert "get_notify_token" in src


def test_on_stop_uses_permissions_token():
    src = (PROJECT_DIR / "scripts" / "on_stop.py").read_text()
    assert "TELEGRAM_TOKEN" not in src
    assert "TOKEN_PERMISSIONS" in src


def test_notify_bot_override_exits_cleanly_with_empty_token(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"notifications_enabled": True, "active_session": None}))
    result = subprocess.run(
        [sys.executable, str(NOTIFY_SCRIPT), "--bot", "teach", "Test message"],
        capture_output=True, text=True, timeout=5,
        env={**os.environ, "WORK_DIR": str(tmp_path),
             "TOKEN_TEACH": "", "TOKEN_PERMISSIONS": "", "TOKEN_BRAIN": "", "TOKEN_ORGANIZER": ""}
    )
    assert result.returncode == 0


def test_notify_bot_override_code_present():
    src = (PROJECT_DIR / "scripts" / "telegram_notify.py").read_text()
    assert "bot_override" in src
    assert 'f"TOKEN_{' in src


def test_notify_checks_notifications_enabled():
    src = (PROJECT_DIR / "scripts" / "telegram_notify.py").read_text()
    assert "notifications_enabled" in src


def test_notify_skips_send_when_notifications_disabled(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"notifications_enabled": False, "active_session": None}))
    result = subprocess.run(
        [sys.executable, str(NOTIFY_SCRIPT), "Test message"],
        capture_output=True, text=True, timeout=5,
        env={**os.environ, "WORK_DIR": str(tmp_path),
             "TOKEN_PERMISSIONS": "should-not-be-used", "TOKEN_BRAIN": "", "TOKEN_TEACH": "", "TOKEN_ORGANIZER": ""}
    )
    assert result.returncode == 0

import sys, json, subprocess, os
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
NOTIFY_SCRIPT = PROJECT_DIR / "scripts" / "telegram_notify.py"
DEV_NOTIFY_SCRIPT = PROJECT_DIR / "scripts" / "dev_notify.py"


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


def test_on_stop_no_longer_sends_telegram():
    src = (PROJECT_DIR / "scripts" / "on_stop.py").read_text()
    assert "TOKEN_PERMISSIONS" not in src
    assert "sendMessage" not in src
    assert "notifications_enabled" not in src


def test_on_stop_writes_turn_ended_flag_and_clears_pending_wait(tmp_path):
    (tmp_path / "pending_wait_sid-xyz.json").write_text("{}")
    result = subprocess.run(
        [sys.executable, str(PROJECT_DIR / "scripts" / "on_stop.py")],
        input=json.dumps({"session_id": "sid-xyz"}),
        capture_output=True, text=True, timeout=5,
        env={**os.environ, "WORK_DIR": str(tmp_path)},
    )
    assert result.returncode == 0
    assert (tmp_path / "turn_ended_sid-xyz.flag").exists()
    assert not (tmp_path / "pending_wait_sid-xyz.json").exists()


def test_telegram_ask_script_removed():
    assert not (PROJECT_DIR / "scripts" / "telegram_ask.py").exists()


def test_permissions_bot_removed():
    assert not (PROJECT_DIR / "bots" / "permissions.py").exists()
    assert not (PROJECT_DIR / "systemd" / "bot-permissions.service").exists()


def test_setup_webhooks_has_no_permissions_entry():
    src = (PROJECT_DIR / "scripts" / "setup_webhooks.py").read_text()
    assert "TOKEN_PERMISSIONS" not in src
    assert '"permissions"' not in src


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


def test_notify_has_no_notifications_gate():
    src = (PROJECT_DIR / "scripts" / "telegram_notify.py").read_text()
    assert "notifications_enabled" not in src


def test_dev_notify_ignores_notifications_disabled_gate(tmp_path):
    """dev_notify.py ist der Pflicht-Notify-Pfad für /dev finish — muss unabhängig
    von notifications_enabled feuern (Bug: Brain-Notify kam nicht an, weil
    telegram_notify.py das Gate respektiert)."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"notifications_enabled": False, "active_session": None}))
    result = subprocess.run(
        [sys.executable, str(DEV_NOTIFY_SCRIPT), "--bot", "brain", "Test message"],
        capture_output=True, text=True, timeout=5,
        env={**os.environ, "WORK_DIR": str(tmp_path), "TOKEN_BRAIN": ""}
    )
    assert result.returncode == 0


def test_dev_notify_does_not_check_notifications_enabled():
    src = DEV_NOTIFY_SCRIPT.read_text()
    assert "load_settings" not in src
    assert '.get("notifications_enabled"' not in src


def test_dev_notify_exits_silently_without_bot_flag(tmp_path):
    result = subprocess.run(
        [sys.executable, str(DEV_NOTIFY_SCRIPT), "Test message"],
        capture_output=True, text=True, timeout=5,
        env={**os.environ, "WORK_DIR": str(tmp_path)}
    )
    assert result.returncode == 0


def test_dev_notify_exits_silently_without_token(tmp_path):
    result = subprocess.run(
        [sys.executable, str(DEV_NOTIFY_SCRIPT), "--bot", "brain", "Test message"],
        capture_output=True, text=True, timeout=5,
        env={**os.environ, "WORK_DIR": str(tmp_path), "TOKEN_BRAIN": ""}
    )
    assert result.returncode == 0

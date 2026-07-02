import sys, json, subprocess, os
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "set_session.py"


def _run(args, env_override=None):
    e = {**os.environ, **(env_override or {})}
    return subprocess.run([sys.executable, str(SCRIPT)] + args,
                          capture_output=True, text=True, timeout=5, env=e)


def test_set_dev_session_writes_session_file(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"notifications_enabled": True}))
    result = _run(["dev", "my-proj"],
                  env_override={"WORK_DIR": str(tmp_path), "CLAUDE_CODE_SESSION_ID": "test-sid-1"})
    assert result.returncode == 0
    settings = json.loads(settings_path.read_text())
    assert settings["active_session"] == "dev"
    assert "active_dev_slug" not in settings
    session_file = tmp_path / "dev_sessions" / "test-sid-1.json"
    data = json.loads(session_file.read_text())
    assert data["active_dev_slug"] == "my-proj"
    assert data["implementation_mode"] is False
    assert data["implementation_mode_until"] is None


def test_clear_session_deletes_session_file(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"active_session": "dev"}))
    sessions_dir = tmp_path / "dev_sessions"
    sessions_dir.mkdir()
    (sessions_dir / "test-sid-2.json").write_text(json.dumps({"active_dev_slug": "my-proj"}))
    result = _run(["clear"],
                  env_override={"WORK_DIR": str(tmp_path), "CLAUDE_CODE_SESSION_ID": "test-sid-2"})
    assert result.returncode == 0
    settings = json.loads(settings_path.read_text())
    assert settings["active_session"] is None
    assert not (sessions_dir / "test-sid-2.json").exists()


def test_clear_session_without_existing_file_ok(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"active_session": "dev"}))
    result = _run(["clear"],
                  env_override={"WORK_DIR": str(tmp_path), "CLAUDE_CODE_SESSION_ID": "test-sid-3"})
    assert result.returncode == 0


def test_missing_slug_exits_nonzero():
    result = _run(["dev"], env_override={"CLAUDE_CODE_SESSION_ID": "test-sid-4"})
    assert result.returncode != 0


def test_missing_session_id_exits_nonzero(tmp_path):
    env = {**os.environ, "WORK_DIR": str(tmp_path)}
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    result = subprocess.run([sys.executable, str(SCRIPT), "dev", "my-proj"],
                            capture_output=True, text=True, timeout=5, env=env)
    assert result.returncode != 0

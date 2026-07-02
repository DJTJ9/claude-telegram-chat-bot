import sys, os, json
from pathlib import Path
import subprocess

PROJECT_DIR = Path(__file__).parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "on_permission.py"


def _run(tool_name, tool_input, notifications=True):
    settings = PROJECT_DIR / "settings.json"
    original = settings.read_text()
    settings.write_text(json.dumps({"notifications_enabled": notifications}))
    try:
        data = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=data, capture_output=True, text=True, timeout=5
        )
        return json.loads(result.stdout)
    finally:
        settings.write_text(original)


def test_edit_inside_project_auto_approves():
    inside_path = str(PROJECT_DIR / "bot.py")
    resp = _run("Edit", {"file_path": inside_path})
    assert resp["decision"] == "approve"


def test_write_inside_project_auto_approves():
    inside_path = str(PROJECT_DIR / "reminders.json")
    resp = _run("Write", {"file_path": inside_path})
    assert resp["decision"] == "approve"


def test_notifications_off_auto_approves_bash():
    resp = _run("Bash", {"command": "echo hi"}, notifications=False)
    assert resp["decision"] == "approve"


def _run_with_impl_mode(tool_name, tool_input, impl_mode=False, impl_until=None, session_id="test-sid-perm"):
    settings = PROJECT_DIR / "settings.json"
    original = settings.read_text()
    settings.write_text(json.dumps({"notifications_enabled": True}))
    sessions_dir = PROJECT_DIR / "dev_sessions"
    sessions_dir.mkdir(exist_ok=True)
    session_path = sessions_dir / f"{session_id}.json"
    session_existed = session_path.exists()
    session_original = session_path.read_text() if session_existed else None
    session_path.write_text(json.dumps({
        "active_dev_slug": "test-proj",
        "implementation_mode": impl_mode,
        "implementation_mode_until": impl_until,
    }))
    try:
        data = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        env = {**os.environ, "CLAUDE_CODE_SESSION_ID": session_id}
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=data, capture_output=True, text=True, timeout=5, env=env
        )
        return json.loads(result.stdout)
    finally:
        settings.write_text(original)
        if session_existed:
            session_path.write_text(session_original)
        else:
            session_path.unlink(missing_ok=True)


def test_implementation_mode_approves_bash():
    from datetime import datetime, timedelta
    until = (datetime.now() + timedelta(hours=4)).isoformat(timespec="seconds")
    resp = _run_with_impl_mode("Bash", {"command": "echo hi"}, impl_mode=True, impl_until=until)
    assert resp["decision"] == "approve"


def test_implementation_mode_approves_edit_outside_project():
    from datetime import datetime, timedelta
    until = (datetime.now() + timedelta(hours=4)).isoformat(timespec="seconds")
    resp = _run_with_impl_mode("Edit", {"file_path": r"C:\Users\tjark\.claude\CLAUDE.md"},
                               impl_mode=True, impl_until=until)
    assert resp["decision"] == "approve"


def test_implementation_mode_false_uses_normal_path():
    # impl_mode=False falls through to normal path; Edit inside project still approves
    inside = str(PROJECT_DIR / "bot.py")
    resp = _run_with_impl_mode("Edit", {"file_path": inside}, impl_mode=False, impl_until=None)
    assert resp["decision"] == "approve"

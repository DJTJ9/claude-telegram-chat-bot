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

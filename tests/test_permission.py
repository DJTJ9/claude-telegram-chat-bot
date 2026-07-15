import sys, os, json
from pathlib import Path
import subprocess

PROJECT_DIR = Path(__file__).parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "on_permission.py"


def _run(tool_name, tool_input):
    # CLAUDE_CODE_SESSION_ID muss raus: läuft die Suite in einer echten
    # CC-Session mit aktivem implementation_mode, würde der Hook sonst
    # unabhängig vom Tool approven.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
        capture_output=True, text=True, timeout=5, env=env,
    )


def test_edit_inside_project_is_approved():
    result = _run("Edit", {"file_path": str(PROJECT_DIR / "settings.json")})
    assert json.loads(result.stdout) == {"decision": "approve"}


def test_write_inside_project_is_approved():
    result = _run("Write", {"file_path": str(PROJECT_DIR / "scripts" / "neu.py")})
    assert json.loads(result.stdout) == {"decision": "approve"}


def test_edit_outside_project_produces_no_output():
    result = _run("Edit", {"file_path": "/etc/hosts"})
    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_bash_produces_no_output():
    result = _run("Bash", {"command": "ls -la"})
    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_unparseable_input_blocks():
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="not json", capture_output=True, text=True, timeout=5, env=env,
    )
    assert json.loads(result.stdout)["decision"] == "block"
    assert result.returncode == 2


def test_relay_and_gate_code_removed():
    src = SCRIPT.read_text()
    assert "notifications_enabled" not in src
    assert "pending_permission" not in src
    assert "permission_response" not in src
    assert "Denied via Telegram" not in src


def test_implementation_mode_branch_kept():
    src = SCRIPT.read_text()
    assert "implementation_mode" in src
    assert "implementation_mode_until" in src

import sys, json, subprocess, os
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "set_session.py"


def _run(args, env_override=None):
    e = {**os.environ, **(env_override or {})}
    return subprocess.run([sys.executable, str(SCRIPT)] + args,
                          capture_output=True, text=True, timeout=5, env=e)


def test_set_dev_session(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"notifications_enabled": True}))
    result = _run(["dev", "my-proj"], env_override={"WORK_DIR": str(tmp_path)})
    assert result.returncode == 0
    data = json.loads(settings_path.read_text())
    assert data["active_session"] == "dev"
    assert data["active_dev_slug"] == "my-proj"


def test_clear_session(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"active_session": "dev", "active_dev_slug": "my-proj"}))
    result = _run(["clear"], env_override={"WORK_DIR": str(tmp_path)})
    assert result.returncode == 0
    data = json.loads(settings_path.read_text())
    assert data["active_session"] is None
    assert data["active_dev_slug"] is None


def test_missing_slug_exits_nonzero():
    result = _run(["dev"])
    assert result.returncode != 0

import json, os, subprocess, sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "on_notification.py"


def _run(tmp_path, stdin_data, tmux_pane="%5",
         capture_text="Frage? \nA) Ja\nB) Nein\n> "):
    """Run hook with temp WORK_DIR and a fake tmux binary on PATH."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    cap_file = tmp_path / "capture.txt"
    cap_file.write_text(capture_text)
    fake_tmux = bin_dir / "tmux"
    fake_tmux.write_text('#!/bin/sh\ncat "$FAKE_CAPTURE"\n')
    fake_tmux.chmod(0o755)
    env = {**os.environ,
           "WORK_DIR": str(tmp_path),
           "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "FAKE_CAPTURE": str(cap_file)}
    if tmux_pane is None:
        env.pop("TMUX_PANE", None)
    else:
        env["TMUX_PANE"] = tmux_pane
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(stdin_data) if isinstance(stdin_data, dict) else stdin_data,
        capture_output=True, text=True, env=env, timeout=15,
    )


def _mk_session(tmp_path, session_id="s1", **fields):
    d = tmp_path / "dev_sessions"
    d.mkdir(exist_ok=True)
    data = {"active_dev_slug": "dev-skill", "implementation_mode": False,
            "implementation_mode_until": None, **fields}
    (d / f"{session_id}.json").write_text(json.dumps(data))


def _pending(tmp_path, session_id="s1"):
    return tmp_path / f"pending_wait_{session_id}.json"


def test_writes_pending_wait_for_bound_dev_session(tmp_path):
    _mk_session(tmp_path)
    r = _run(tmp_path, {"session_id": "s1", "message": "Claude is waiting for your input"})
    assert r.returncode == 0, r.stderr
    data = json.loads(_pending(tmp_path).read_text())
    assert data["slug"] == "dev-skill"
    assert data["pane"] == "%5"
    assert "Frage?" in data["question"]
    assert isinstance(data["timestamp"], float)


def test_no_dev_session_no_file(tmp_path):
    r = _run(tmp_path, {"session_id": "s1", "message": "Claude is waiting for your input"})
    assert r.returncode == 0
    assert not _pending(tmp_path).exists()


def test_permission_notification_filtered(tmp_path):
    _mk_session(tmp_path)
    r = _run(tmp_path, {"session_id": "s1",
                        "message": "Claude needs your permission to use Bash"})
    assert r.returncode == 0
    assert not _pending(tmp_path).exists()


def test_implementation_mode_active_skips(tmp_path):
    _mk_session(tmp_path, implementation_mode=True,
                implementation_mode_until="2099-01-01T00:00:00")
    r = _run(tmp_path, {"session_id": "s1", "message": "Claude is waiting for your input"})
    assert r.returncode == 0
    assert not _pending(tmp_path).exists()


def test_implementation_mode_expired_notifies(tmp_path):
    _mk_session(tmp_path, implementation_mode=True,
                implementation_mode_until="2000-01-01T00:00:00")
    _run(tmp_path, {"session_id": "s1", "message": "Claude is waiting for your input"})
    assert _pending(tmp_path).exists()


def test_no_tmux_pane_no_file(tmp_path):
    _mk_session(tmp_path)
    r = _run(tmp_path, {"session_id": "s1", "message": "Claude is waiting for your input"},
             tmux_pane=None)
    assert r.returncode == 0
    assert not _pending(tmp_path).exists()


def test_unparseable_stdin_exits_zero(tmp_path):
    r = _run(tmp_path, "not json")
    assert r.returncode == 0
    assert not list(tmp_path.glob("pending_wait_*.json"))

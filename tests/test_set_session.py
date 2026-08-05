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
    # K4: settings.json wird nicht mehr angefasst
    settings = json.loads(settings_path.read_text())
    assert settings == {"notifications_enabled": True}
    session_file = tmp_path / "dev_sessions" / "test-sid-1.json"
    data = json.loads(session_file.read_text())
    assert data["active_dev_slug"] == "my-proj"
    assert data["implementation_mode"] is False
    assert data["implementation_mode_until"] is None


def test_dev_binds_slug_and_feature(tmp_path):
    result = _run(["dev", "proj", "email-auth"],
                  env_override={"WORK_DIR": str(tmp_path), "CLAUDE_CODE_SESSION_ID": "sid-a"})
    assert result.returncode == 0
    data = json.loads((tmp_path / "dev_sessions" / "sid-a.json").read_text())
    assert data["active_dev_slug"] == "proj"
    assert data["active_dev_feature"] == "email-auth"


def test_dev_without_feature_keeps_none(tmp_path):
    result = _run(["dev", "proj"],
                  env_override={"WORK_DIR": str(tmp_path), "CLAUDE_CODE_SESSION_ID": "sid-a"})
    assert result.returncode == 0
    data = json.loads((tmp_path / "dev_sessions" / "sid-a.json").read_text())
    assert data["active_dev_slug"] == "proj"
    assert data["active_dev_feature"] is None


def test_clear_removes_only_own_session_file(tmp_path):
    (tmp_path / "dev_sessions").mkdir(exist_ok=True)
    (tmp_path / "dev_sessions" / "sid-b.json").write_text('{"active_dev_slug": "other"}')
    (tmp_path / "settings.json").write_text('{"active_session": "teach", "x": 1}')
    env = {"WORK_DIR": str(tmp_path), "CLAUDE_CODE_SESSION_ID": "sid-a"}
    assert _run(["dev", "proj"], env_override=env).returncode == 0
    assert _run(["clear"], env_override=env).returncode == 0
    assert not (tmp_path / "dev_sessions" / "sid-a.json").exists()
    assert (tmp_path / "dev_sessions" / "sid-b.json").exists()
    # K4: settings.json bleibt byte-identisch — kein active_session-Clear mehr
    assert json.loads((tmp_path / "settings.json").read_text()) == {"active_session": "teach", "x": 1}


def test_set_dev_session_includes_worktree_fields(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"notifications_enabled": True}))
    result = _run(["dev", "my-proj"],
                  env_override={"WORK_DIR": str(tmp_path), "CLAUDE_CODE_SESSION_ID": "test-sid-wt"})
    assert result.returncode == 0
    session_file = tmp_path / "dev_sessions" / "test-sid-wt.json"
    data = json.loads(session_file.read_text())
    assert data["worktree_path"] is None
    assert data["branch"] is None
    assert data["worktree_base_dir"] is None


def test_set_dev_session_preserves_worktree_and_impl_mode(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"notifications_enabled": True}))
    sessions_dir = tmp_path / "dev_sessions"
    sessions_dir.mkdir()
    session_file = sessions_dir / "test-sid-merge.json"
    session_file.write_text(json.dumps({
        "active_dev_slug": "my-proj",
        "implementation_mode": True,
        "implementation_mode_until": "2026-07-11T18:00:00",
        "worktree_path": "/root/.claude/worktrees/foo",
        "branch": "worktree-foo",
        "worktree_base_dir": "/root/.claude",
    }))
    result = _run(["dev", "my-proj"],
                  env_override={"WORK_DIR": str(tmp_path), "CLAUDE_CODE_SESSION_ID": "test-sid-merge"})
    assert result.returncode == 0
    data = json.loads(session_file.read_text())
    assert data["active_dev_slug"] == "my-proj"
    assert data["implementation_mode"] is True
    assert data["implementation_mode_until"] == "2026-07-11T18:00:00"
    assert data["worktree_path"] == "/root/.claude/worktrees/foo"
    assert data["branch"] == "worktree-foo"
    assert data["worktree_base_dir"] == "/root/.claude"


def test_clear_session_deletes_session_file(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"active_session": "dev"}))
    sessions_dir = tmp_path / "dev_sessions"
    sessions_dir.mkdir()
    (sessions_dir / "test-sid-2.json").write_text(json.dumps({"active_dev_slug": "my-proj"}))
    result = _run(["clear"],
                  env_override={"WORK_DIR": str(tmp_path), "CLAUDE_CODE_SESSION_ID": "test-sid-2"})
    assert result.returncode == 0
    # K4: settings.json bleibt unberührt
    settings = json.loads(settings_path.read_text())
    assert settings == {"active_session": "dev"}
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

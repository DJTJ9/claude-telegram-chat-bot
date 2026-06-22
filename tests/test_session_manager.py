import os, sys, json, signal
os.environ.setdefault("TOKEN_BRAIN", "test_token")
os.environ.setdefault("CHAT_ID", "12345")
os.environ.setdefault("GROQ_API_KEY", "test_key")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch
from pathlib import Path


@pytest.fixture
def sm(tmp_path, monkeypatch):
    import core.session_manager as sm
    monkeypatch.setattr(sm, "WORK_DIR", tmp_path)
    monkeypatch.setattr(sm, "_STATE_PATH", tmp_path / "session_state.json")
    monkeypatch.setattr(sm, "_COMMENT_PATH", tmp_path / "pending_comment.json")
    return sm


def test_save_and_load_session(sm):
    sm.save_session("vision", "my-proj", pid=1234)
    s = sm.load_session()
    assert s["active"] == "vision"
    assert s["slug"] == "my-proj"
    assert s["pid"] == 1234
    assert "session_id" in s
    assert "started_at" in s
    assert s["checkpoint_path"].endswith(s["session_id"] + ".md")


def test_clear_session(sm):
    sm.save_session("vision", "my-proj", pid=1)
    sm.clear_session()
    assert sm.load_session() is None


def test_is_session_active_false_when_no_file(sm):
    assert sm.is_session_active() is False


def test_is_session_active_true_after_save(sm):
    sm.save_session("brainstorming", "my-proj", pid=1)
    assert sm.is_session_active() is True


def test_is_session_active_false_after_clear(sm):
    sm.save_session("vision", "x", pid=1)
    sm.clear_session()
    assert sm.is_session_active() is False


def test_kill_session_sends_sigterm(sm):
    sm.save_session("vision", "my-proj", pid=9999)
    with patch("os.kill") as mock_kill:
        result = sm.kill_session()
    mock_kill.assert_called_once_with(9999, signal.SIGTERM)
    assert result is True


def test_kill_session_returns_false_when_no_session(sm):
    result = sm.kill_session()
    assert result is False


def test_kill_session_handles_no_such_process(sm):
    sm.save_session("vision", "my-proj", pid=999999)
    with patch("os.kill", side_effect=ProcessLookupError):
        result = sm.kill_session()
    assert result is False


def test_write_and_read_comment(sm):
    sm.write_comment("My spontaneous thought")
    result = sm.read_and_clear_comment()
    assert result == "My spontaneous thought"


def test_read_clears_comment(sm):
    sm.write_comment("hello")
    sm.read_and_clear_comment()
    assert sm.read_and_clear_comment() is None


def test_read_comment_returns_none_when_no_file(sm):
    assert sm.read_and_clear_comment() is None


def test_write_and_load_checkpoint(sm):
    content = "## Checkpoint\n**Erledigt:** discussed auth"
    sm.write_checkpoint("abc123", content)
    loaded = sm.load_checkpoint("abc123")
    assert loaded == content


def test_load_checkpoint_returns_none_missing(sm):
    assert sm.load_checkpoint("nonexistent") is None


def test_checkpoint_path_format(sm):
    p = sm.checkpoint_path("abc123")
    assert str(p).endswith("checkpoint_abc123.md")


def test_parse_plan_tasks_basic(tmp_path):
    import core.session_manager as sm
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# My Plan\n\n"
        "## Task 1: Setup database\n"
        "**Dateien:** `db.py`\n"
        "Create the schema.\n\n"
        "## Task 2: Add auth\n"
        "**Dateien:** `auth.py`\n"
        "Implement JWT.\n"
    )
    tasks = sm.parse_plan_tasks(plan)
    assert len(tasks) == 2
    assert tasks[0]["title"] == "Setup database"
    assert "db.py" in tasks[0]["files"]
    assert tasks[0]["done"] is False
    assert tasks[1]["title"] == "Add auth"


def test_parse_plan_tasks_marks_done(tmp_path):
    import core.session_manager as sm
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task 1: Setup database\n"
        "**Dateien:** `db.py`\n"
        "Create the schema.\n\n"
        "## Task 2: Add auth\n"
        "**Dateien:** `auth.py`\n"
        "JWT.\n"
    )
    sm.mark_task_done(plan, "Setup database")
    tasks = sm.parse_plan_tasks(plan)
    assert tasks[0]["done"] is True
    assert tasks[1]["done"] is False


def test_next_pending_task(tmp_path):
    import core.session_manager as sm
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task 1: ~~Done task~~\n"
        "**Dateien:** `a.py`\n"
        "done.\n\n"
        "## Task 2: Active task\n"
        "**Dateien:** `b.py`\n"
        "do this.\n"
    )
    t = sm.next_pending_task(plan)
    assert t is not None
    assert t["title"] == "Active task"


def test_next_pending_task_returns_none_when_all_done(tmp_path):
    import core.session_manager as sm
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task 1: ~~Done~~\n"
        "**Dateien:** `a.py`\n"
        "done.\n"
    )
    assert sm.next_pending_task(plan) is None

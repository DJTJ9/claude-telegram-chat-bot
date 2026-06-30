import json
import os
import subprocess
import sys
import tempfile
import pathlib

HUB_DIR = os.environ.get("HUB_DIR", "")
WORK_DIR = os.environ.get("WORK_DIR", "")
sys.path.insert(0, os.path.join(WORK_DIR, "bots"))


# ── Task 1: dev_context.py projekte command ────────────────────────────────────

def _run_projekte():
    r = subprocess.run(
        ["python3", f"{HUB_DIR}/scripts/dev_context.py", "--command", "projekte"],
        capture_output=True, text=True, env=os.environ
    )
    return json.loads(r.stdout)


def test_projekte_command_returns_list():
    result = _run_projekte()
    assert isinstance(result, list)


def test_projekte_command_has_required_fields():
    result = _run_projekte()
    assert len(result) > 0
    for p in result:
        assert "slug" in p
        assert "name" in p
        assert "phase" in p
        assert "active" in p
        assert "next_feature" in p
        assert "updated" in p


def test_projekte_command_sorted_by_updated():
    result = _run_projekte()
    dates = [p["updated"] for p in result if p["updated"]]
    assert dates == sorted(dates, reverse=True)


# ── Task 2: _build_projekte_message ───────────────────────────────────────────

def test_build_projekte_message_returns_tuple():
    from organizer import _build_projekte_message
    msg, buttons = _build_projekte_message()
    assert isinstance(msg, str)
    assert isinstance(buttons, list)


def test_build_projekte_message_has_sections():
    from organizer import _build_projekte_message
    msg, _ = _build_projekte_message()
    assert "━━" in msg
    assert "📁 Projekte" in msg


def test_build_projekte_message_has_idea_button():
    from organizer import _build_projekte_message
    _, buttons = _build_projekte_message()
    flat = [btn["callback_data"] for row in buttons for btn in row]
    assert "idea_pick" in flat


# ── Task 3: idea_pick callbacks + workflow step ────────────────────────────────

def test_append_idea_hub_writes_to_status_and_vision():
    import organizer

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)
        slug_dir = tmp / "topics" / "testslug"
        slug_dir.mkdir(parents=True)
        (slug_dir / "STATUS.md").write_text("## Roadmap\n")
        (slug_dir / "VISION.md").write_text("## Roadmap\n")
        orig_hub = organizer.HUB_DIR
        organizer.HUB_DIR = tmp
        try:
            organizer._append_idea_hub("testslug", "Test Idee")
        finally:
            organizer.HUB_DIR = orig_hub
        assert "- [idea]      Test Idee" in (slug_dir / "STATUS.md").read_text()
        assert "- [idea]      Test Idee" in (slug_dir / "VISION.md").read_text()


def test_idea_pick_callback_handler_present():
    import inspect
    from organizer import _handle_callback
    src = inspect.getsource(_handle_callback)
    assert 'data == "idea_pick"' in src


def test_idea_pick_slug_callback_handler_present():
    import inspect
    from organizer import _handle_callback
    src = inspect.getsource(_handle_callback)
    assert 'data.startswith("idea_pick:")' in src


def test_idea_for_project_workflow_step_present():
    import inspect
    from organizer import handle_workflow_step
    src = inspect.getsource(handle_workflow_step)
    assert '"idea_for_project:name"' in src

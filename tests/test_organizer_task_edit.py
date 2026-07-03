"""Source inspection tests for Task-Bearbeiten-Flow."""
from pathlib import Path
src = (Path(__file__).parent.parent / "bots/organizer.py").read_text(encoding="utf-8")


def test_task_edit_list_uses_fetch_open_tasks():
    idx = src.index('elif kind == "task_edit_list":')
    block = src[idx:idx + 500]
    assert "fetch_open_tasks" in block
    assert "task_edit:pick:" in block


def test_task_edit_pick_shows_current_name():
    idx = src.index('data.startswith("task_edit:pick:")')
    block = src[idx:idx + 700]
    assert "fetch_open_tasks" in block
    assert "task_edit:name:keep" in block


def test_task_edit_name_freitext_moves_to_date():
    idx = src.index('if step == "task_edit:name":')
    block = src[idx:idx + 300]
    assert "_send_task_edit_date_step" in block


def test_task_edit_date_step_shows_current_or_placeholder():
    idx = src.index("def _send_task_edit_date_step")
    block = src[idx:idx + 700]
    assert "Noch kein Datum festgelegt" in block
    assert "task_edit:date:keep" in block


def test_task_edit_date_freitext_uses_helper():
    idx = src.index('if step == "task_edit:date":')
    block = src[idx:idx + 700]
    assert "_task_date_from_freitext" in block


def test_task_edit_priority_step_shows_current():
    idx = src.index("def _send_task_edit_priority_step")
    block = src[idx:idx + 700]
    assert "task_edit:priority:keep" in block


def test_task_edit_priority_callback_calls_update_task():
    idx = src.index('data.startswith("task_edit:priority:")')
    block = src[idx:idx + 700]
    assert "update_task" in block
    assert "✅ Task aktualisiert" in block

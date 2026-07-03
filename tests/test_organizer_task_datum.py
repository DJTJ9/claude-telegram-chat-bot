"""Source inspection tests for Task-Workflow Datum-Auswahl."""
from pathlib import Path
src = (Path(__file__).parent.parent / "bots/organizer.py").read_text(encoding="utf-8")


def test_task_start_shows_mode_picker():
    idx = src.index('if kind == "task":')
    block = src[idx:idx + 500]
    assert "task:mode:new" in block
    assert "task:mode:edit" in block


def test_task_mode_new_starts_name_step():
    idx = src.index('data.startswith("task:mode:")')
    block = src[idx:idx + 700]
    assert '"step": "task:name"' in block


def test_task_mode_edit_starts_edit_list():
    idx = src.index('data.startswith("task:mode:")')
    block = src[idx:idx + 700]
    assert "task_edit_list" in block


def test_task_name_step_leads_to_date_step():
    idx = src.index('if step == "task:name":')
    block = src[idx:idx + 700]
    assert '"step"] = "task:date"' in block
    assert "task:date:heute" in block
    assert "task:date:morgen" in block
    assert "task:date:spaeter" in block


def test_task_date_freitext_step_uses_helper():
    idx = src.index('if step == "task:date":')
    block = src[idx:idx + 700]
    assert "_task_date_from_freitext" in block


def test_task_date_callback_uses_helper():
    idx = src.index('data.startswith("task:date:")')
    block = src[idx:idx + 700]
    assert "_task_date_from_choice" in block


def test_task_priority_creates_backlog_when_no_date():
    idx = src.index('data.startswith("task:priority:")')
    block = src[idx:idx + 700]
    assert "create_backlog_item" in block
    assert "create_task" in block

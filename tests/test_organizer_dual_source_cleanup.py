from pathlib import Path
src = (Path(__file__).parent.parent / "bots/organizer.py").read_text(encoding="utf-8")


def test_notion_direct_import_removed():
    assert "from core import notion_direct" not in src


def test_notion_direct_archive_removed():
    assert "notion_direct.archive_backlog_item" not in src


def test_notion_direct_reschedule_removed():
    assert "notion_direct.reschedule" not in src


def test_nocodb_archive_backlog_present():
    assert "nocodb_direct.archive_backlog_item" in src


def test_nondigit_guard_present():
    assert "Veralteter Button" in src


def test_nondigit_guard_appears_three_times():
    assert src.count("Veralteter Button") >= 3

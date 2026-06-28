# tests/test_notion_sync_order.py
import json, os, sys
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))


def test_load_notion_db_id_found(tmp_path, monkeypatch):
    registry = [{"slug": "my-proj", "notion_db_id": "db-abc"}, {"slug": "other"}]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry))
    monkeypatch.setenv("HUB_DIR", str(tmp_path))
    from scripts.notion_sync import load_notion_db_id
    assert load_notion_db_id("my-proj") == "db-abc"


def test_load_notion_db_id_missing(tmp_path, monkeypatch):
    registry = [{"slug": "my-proj"}]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry))
    monkeypatch.setenv("HUB_DIR", str(tmp_path))
    from scripts.notion_sync import load_notion_db_id
    assert load_notion_db_id("my-proj") == ""


def test_load_notion_db_id_unknown_slug(tmp_path, monkeypatch):
    registry = [{"slug": "other", "notion_db_id": "db-xyz"}]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry))
    monkeypatch.setenv("HUB_DIR", str(tmp_path))
    from scripts.notion_sync import load_notion_db_id
    assert load_notion_db_id("nonexistent") == ""


def test_update_status_active_sets_name(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text("Active: (keine aktive Entwicklung)\nPhase: plan\n", encoding="utf-8")
    from scripts.notion_sync import _update_status_active
    _update_status_active(status, "Habit-Tracking")
    assert "Active: Habit-Tracking" in status.read_text()


def test_update_status_active_clears_when_empty(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text("Active: Habit-Tracking\nPhase: plan\n", encoding="utf-8")
    from scripts.notion_sync import _update_status_active
    _update_status_active(status, "")
    assert "Active: (keine aktive Entwicklung)" in status.read_text()


def test_reorder_vision_roadmap(tmp_path):
    vision = tmp_path / "VISION.md"
    vision.write_text(
        "# Project\n## Roadmap\n"
        "- [idea]      Feature B\n"
        "- [discussed]  Feature A\n"
        "- [done]      Feature C\n",
        encoding="utf-8"
    )
    from scripts.notion_sync import _reorder_vision_roadmap
    _reorder_vision_roadmap(vision, ["Feature A", "Feature B", "Feature C"])
    lines = [l for l in vision.read_text().splitlines() if l.startswith("- [")]
    assert "Feature A" in lines[0]
    assert "Feature B" in lines[1]
    assert "Feature C" in lines[2]


def test_reorder_vision_roadmap_preserves_unlisted(tmp_path):
    vision = tmp_path / "VISION.md"
    vision.write_text(
        "# Project\n## Roadmap\n"
        "- [done]      Feature A\n"
        "- [idea]      Feature B\n"
        "- [idea]      Unlisted\n",
        encoding="utf-8"
    )
    from scripts.notion_sync import _reorder_vision_roadmap
    _reorder_vision_roadmap(vision, ["Feature A", "Feature B"])
    lines = [l for l in vision.read_text().splitlines() if l.startswith("- [")]
    assert len(lines) == 3
    assert "Unlisted" in lines[2]


def test_sync_feature_order_no_db_id(tmp_path, monkeypatch, capsys):
    registry = [{"slug": "test-proj"}]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry))
    monkeypatch.setenv("HUB_DIR", str(tmp_path))
    from scripts.notion_sync import sync_feature_order_from_notion
    sync_feature_order_from_notion("test-proj")
    captured = capsys.readouterr()
    assert "No notion_db_id" in captured.err

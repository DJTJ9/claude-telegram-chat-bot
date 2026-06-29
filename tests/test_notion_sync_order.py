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


def test_per_project_prompt_done_includes_timestamp_and_position():
    from scripts.notion_sync import build_per_project_sync_prompt
    prompt = build_per_project_sync_prompt("my-proj", "Habit-Tracking", "done", None, None, "db-123")
    assert "db-123" in prompt
    assert "Status=done" in prompt
    assert "Abgeschlossen:" in prompt
    assert "Position:" in prompt


def test_per_project_prompt_discussed_no_timestamp():
    from scripts.notion_sync import build_per_project_sync_prompt
    prompt = build_per_project_sync_prompt("my-proj", "Habit-Tracking", "discussed", None, None, "db-123")
    assert "Abgeschlossen:" not in prompt
    assert "Status=discussed" in prompt


def test_main_uses_per_project_prompt_when_db_id_exists():
    src = Path("scripts/notion_sync.py").read_text()
    assert "build_per_project_sync_prompt" in src
    main_src = src[src.index("def main"):]
    assert "build_per_project_sync_prompt" in main_src
    assert "per_project_db_id" in main_src


def test_reorder_status_roadmap_respects_notion_order(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text(
        "# Status\nActive: X\nPhase: plan\n## Roadmap\n"
        "- [idea]      Feature B\n"
        "- [discussed]  Feature A\n"
        "- [done]      Feature C\n",
        encoding="utf-8"
    )
    entries = [
        {"name": "Feature A", "status": "discussed"},
        {"name": "Feature B", "status": "idea"},
        {"name": "Feature C", "status": "done"},
    ]
    from scripts.notion_sync import _reorder_status_roadmap
    _reorder_status_roadmap(status, entries)
    lines = [l for l in status.read_text().splitlines() if l.startswith("- [")]
    assert "Feature A" in lines[0]
    assert "Feature B" in lines[1]
    assert "Feature C" in lines[2]


def test_reorder_status_roadmap_updates_status_tag(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text("## Roadmap\n- [idea]      Feature A\n", encoding="utf-8")
    entries = [{"name": "Feature A", "status": "discussed"}]
    from scripts.notion_sync import _reorder_status_roadmap
    _reorder_status_roadmap(status, entries)
    text = status.read_text()
    assert "- [discussed]" in text
    assert "- [idea]" not in text


def test_reorder_status_roadmap_preserves_unlisted(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text(
        "## Roadmap\n- [idea]      Feature A\n- [done]      Unlisted\n",
        encoding="utf-8"
    )
    entries = [{"name": "Feature A", "status": "idea"}]
    from scripts.notion_sync import _reorder_status_roadmap
    _reorder_status_roadmap(status, entries)
    text = status.read_text()
    assert "Feature A" in text
    assert "Unlisted" in text


def test_sync_feature_order_calls_reorder_status_roadmap():
    src = Path("scripts/notion_sync.py").read_text()
    func_src = src[src.index("def sync_feature_order_from_notion"):]
    assert "_reorder_status_roadmap" in func_src

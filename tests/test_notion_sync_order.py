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

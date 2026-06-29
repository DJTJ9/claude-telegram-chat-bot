import json, os, sys
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault("PROJEKTE_PAGE_ID", "test-page-id")
os.environ.setdefault("HUB_DIR", "/tmp/test-hub")


def test_create_notion_db_extracts_uuid(monkeypatch):
    monkeypatch.setenv("PROJEKTE_PAGE_ID", "page-abc123")
    with patch("scripts.notion_create_db.run_claude") as mock_claude:
        mock_claude.return_value = "Neue Datenbank erstellt: a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        from scripts.notion_create_db import create_notion_db
        db_id = create_notion_db("test-proj", "Test Projekt")
    assert db_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def test_write_db_id_to_registry(tmp_path, monkeypatch):
    registry = [{"slug": "test-proj", "name": "Test"}, {"slug": "other", "name": "Other"}]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setenv("HUB_DIR", str(tmp_path))
    from scripts.notion_create_db import write_db_id_to_registry
    write_db_id_to_registry("test-proj", "uuid-123")
    data = json.loads((tmp_path / "projects-registry.json").read_text())
    assert data[0]["notion_db_id"] == "uuid-123"
    assert "notion_db_id" not in data[1]


def test_write_db_id_unknown_slug_noop(tmp_path, monkeypatch):
    registry = [{"slug": "other", "name": "Other"}]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setenv("HUB_DIR", str(tmp_path))
    from scripts.notion_create_db import write_db_id_to_registry
    write_db_id_to_registry("nonexistent", "uuid-999")
    data = json.loads((tmp_path / "projects-registry.json").read_text())
    assert "notion_db_id" not in data[0]


def test_all_flag_skips_existing_creates_missing(tmp_path, monkeypatch):
    registry = [
        {"slug": "a", "name": "A", "notion_db_id": "existing-id"},
        {"slug": "b", "name": "B"},
    ]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setenv("HUB_DIR", str(tmp_path))
    monkeypatch.setenv("PROJEKTE_PAGE_ID", "page-id")
    with patch("scripts.notion_create_db.run_claude") as mock:
        mock.return_value = "Datenbank erstellt: 11111111-2222-3333-4444-555555555555"
        from scripts.notion_create_db import create_all_missing
        create_all_missing(tmp_path)
    mock.assert_called_once()  # only for slug "b"
    data = json.loads((tmp_path / "projects-registry.json").read_text())
    assert data[0]["notion_db_id"] == "existing-id"
    assert data[1]["notion_db_id"] == "11111111-2222-3333-4444-555555555555"


def test_all_flag_main_has_route():
    src = Path("scripts/notion_create_db.py").read_text()
    assert "all_projects" in src
    assert "create_all_missing" in src

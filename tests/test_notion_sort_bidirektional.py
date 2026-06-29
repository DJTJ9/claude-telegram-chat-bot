import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_per_project_prompt_new_entry_gets_position():
    """New entries (not found in Notion) should get Position = max + 100."""
    from scripts.notion_sync import build_per_project_sync_prompt
    prompt = build_per_project_sync_prompt("my-proj", "New Feature", "discussed", None, None, "db-123")
    not_found_idx = prompt.index("Falls nicht gefunden")
    not_found_section = prompt[not_found_idx:]
    assert "Position" in not_found_section


def test_per_project_prompt_existing_entry_no_position_update():
    """Existing entries (found and updated) should NOT change Position (except done)."""
    from scripts.notion_sync import build_per_project_sync_prompt
    prompt = build_per_project_sync_prompt("my-proj", "Existing Feature", "discussed", None, None, "db-123")
    found_idx = prompt.index("Falls gefunden")
    found_section = prompt[found_idx:prompt.index("Falls nicht gefunden")]
    assert "Position" not in found_section


def test_sync_reorder_to_notion_exists_in_source():
    src = Path("scripts/notion_sync.py").read_text()
    assert "def sync_reorder_to_notion" in src
    assert "--reorder" in src


def test_sync_reorder_no_db_id(tmp_path, monkeypatch, capsys):
    import json
    registry = [{"slug": "test-proj"}]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setenv("HUB_DIR", str(tmp_path))
    (tmp_path / "topics" / "test-proj").mkdir(parents=True)
    (tmp_path / "topics" / "test-proj" / "STATUS.md").write_text(
        "## Roadmap\n- [idea]      Feature A\n", encoding="utf-8"
    )
    from scripts.notion_sync import sync_reorder_to_notion
    sync_reorder_to_notion("test-proj")
    assert "No notion_db_id" in capsys.readouterr().err


def test_reorder_prompt_assigns_positions(tmp_path, monkeypatch):
    import json
    from unittest.mock import patch
    registry = [{"slug": "test-proj", "notion_db_id": "db-xyz"}]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setenv("HUB_DIR", str(tmp_path))
    (tmp_path / "topics" / "test-proj").mkdir(parents=True)
    (tmp_path / "topics" / "test-proj" / "STATUS.md").write_text(
        "Active: X\nPhase: plan\n## Roadmap\n"
        "- [discussed]  Feature A\n"
        "- [idea]      Feature B\n"
        "- [done]      Feature C\n",
        encoding="utf-8",
    )
    from scripts.notion_sync import sync_reorder_to_notion
    with patch("scripts.notion_sync.run_claude", return_value="OK") as mock_rc:
        sync_reorder_to_notion("test-proj")
    prompt = mock_rc.call_args[0][0]
    assert "Position=100" in prompt
    assert "Position=200" in prompt
    assert "Feature C" not in prompt


def test_update_status_active_conditional_no_override(tmp_path):
    """Conditional update must NOT override a non-empty Active field."""
    status = tmp_path / "STATUS.md"
    status.write_text("Active: My Current Feature\nPhase: implement\n", encoding="utf-8")
    from scripts.notion_sync import _update_status_active
    _update_status_active(status, "New Feature From Notion", conditional=True)
    assert "My Current Feature" in status.read_text()


def test_update_status_active_conditional_sets_when_empty(tmp_path):
    """Conditional update MUST set Active when field is empty/default."""
    status = tmp_path / "STATUS.md"
    status.write_text("Active: (keine aktive Entwicklung)\nPhase: (none)\n", encoding="utf-8")
    from scripts.notion_sync import _update_status_active
    _update_status_active(status, "First Feature", conditional=True)
    assert "First Feature" in status.read_text()


def test_sync_feature_order_auto_active_from_first_non_done():
    """sync_feature_order_from_notion must compute auto_active Python-side."""
    src = Path("scripts/notion_sync.py").read_text()
    func_start = src.index("def sync_feature_order_from_notion")
    func_src = src[func_start:func_start + 1500]
    assert 'e.get("aktiv")' not in func_src
    assert '"done"' in func_src

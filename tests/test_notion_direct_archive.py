import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("NOTION_TOKEN", "test")

from unittest.mock import patch, MagicMock
from core import notion_direct


def _page_json(name="Test Task", status="Erledigt", prio="Hoch", bereich="Privat", notiz="Hinweis"):
    return {
        "properties": {
            "Name":      {"title": [{"text": {"content": name}}]},
            "Status":    {"select": {"name": status}},
            "Priorität": {"select": {"name": prio}},
            "Bereich":   {"select": {"name": bereich}},
            "Notiz":     {"rich_text": [{"text": {"content": notiz}}]},
        }
    }


def _mock_requests(get_status=200, post_status=200, patch_status=200, page_data=None):
    mock = MagicMock()
    mock.get.return_value   = MagicMock(status_code=get_status,  json=lambda: page_data or _page_json())
    mock.post.return_value  = MagicMock(status_code=post_status)
    mock.patch.return_value = MagicMock(status_code=patch_status)
    return mock


def test_archive_backlog_item_returns_true_on_success():
    with patch("core.notion_direct.requests", _mock_requests()):
        assert notion_direct.archive_backlog_item("abc123") is True


def test_archive_backlog_item_creates_archiv_entry():
    mock_req = _mock_requests()
    with patch("core.notion_direct.requests", mock_req):
        notion_direct.archive_backlog_item("abc123")
    post_json = mock_req.post.call_args[1]["json"]
    assert post_json["parent"]["database_id"] == notion_direct.ARCHIV_DB_ID
    props = post_json["properties"]
    assert props["Name"]["title"][0]["text"]["content"] == "Test Task"
    assert "Archiviert am" in props
    assert props["Priorität"]["select"]["name"] == "Hoch"
    assert props["Bereich"]["select"]["name"] == "Privat"
    assert props["Notiz"]["rich_text"][0]["text"]["content"] == "Hinweis"


def test_archive_backlog_item_archives_original():
    mock_req = _mock_requests()
    with patch("core.notion_direct.requests", mock_req):
        notion_direct.archive_backlog_item("abc123")
    patch_calls = mock_req.patch.call_args_list
    archive_call = next(
        (c for c in patch_calls if c[1].get("json", {}).get("archived") is True), None
    )
    assert archive_call is not None, "archived: true patch not called"
    assert "abc123" in archive_call[0][0]


def test_archive_backlog_item_returns_false_on_get_failure():
    with patch("core.notion_direct.requests", _mock_requests(get_status=404)):
        assert notion_direct.archive_backlog_item("bad") is False


def test_archive_backlog_item_returns_false_on_post_failure():
    with patch("core.notion_direct.requests", _mock_requests(post_status=400)):
        assert notion_direct.archive_backlog_item("abc123") is False


def test_archiv_db_id_constant_is_set():
    assert notion_direct.ARCHIV_DB_ID == "38b4bba29c558102b9aecb790594aff6"


def test_archive_skips_missing_optional_fields():
    page = {"properties": {"Name": {"title": [{"text": {"content": "Minimal"}}]}}}
    mock_req = _mock_requests(page_data=page)
    with patch("core.notion_direct.requests", mock_req):
        result = notion_direct.archive_backlog_item("abc123")
    assert result is True
    props = mock_req.post.call_args[1]["json"]["properties"]
    assert "Priorität" not in props
    assert "Bereich" not in props
    assert "Notiz" not in props

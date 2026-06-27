import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("NOTION_TOKEN", "test")
os.environ.setdefault("TOKEN_ORGANIZER", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from unittest.mock import patch, MagicMock
import bots.organizer as org


def _cq(data, msg_id=1, chat_id=123):
    return {
        "id": "cq1",
        "from": {"id": chat_id},
        "message": {"message_id": msg_id, "text": ""},
        "data": data,
    }


def test_backlog_json_prompt_exists():
    assert hasattr(org, "BACKLOG_JSON_SYSTEM_PROMPT")
    assert org.BACKLOG_DATA_SOURCE_ID in org.BACKLOG_JSON_SYSTEM_PROMPT


def test_backlog_json_prompt_requests_items_array():
    assert '"items"' in org.BACKLOG_JSON_SYSTEM_PROMPT
    assert '"id"' in org.BACKLOG_JSON_SYSTEM_PROMPT


def test_backlog_done_callback_calls_archive():
    with patch("bots.organizer.notion_direct") as mock_nd, \
         patch("bots.organizer.answer_callback_query"), \
         patch("bots.organizer.send_message"):
        mock_nd.archive_backlog_item.return_value = True
        org._handle_callback(_cq("backlog_done:aaa111"))
    mock_nd.archive_backlog_item.assert_called_once_with("aaa111")


def test_backlog_done_callback_sends_confirmation():
    sent = []
    with patch("bots.organizer.notion_direct") as mock_nd, \
         patch("bots.organizer.answer_callback_query"), \
         patch("bots.organizer.send_message", side_effect=lambda t, c, m, **kw: sent.append(m)):
        mock_nd.archive_backlog_item.return_value = True
        org._handle_callback(_cq("backlog_done:aaa111"))
    assert any("archiv" in m.lower() or "✓" in m or "✅" in m for m in sent)


def test_backlog_done_failure_sends_error():
    sent = []
    with patch("bots.organizer.notion_direct") as mock_nd, \
         patch("bots.organizer.answer_callback_query"), \
         patch("bots.organizer.send_message", side_effect=lambda t, c, m, **kw: sent.append(m)):
        mock_nd.archive_backlog_item.return_value = False
        org._handle_callback(_cq("backlog_done:aaa111"))
    assert any("❌" in m for m in sent)

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("NOTION_TOKEN", "test")
os.environ.setdefault("TOKEN_ORGANIZER", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from unittest.mock import patch
import bots.organizer as org


def _cq(data, msg_id=1, chat_id=123):
    return {
        "id": "cq1",
        "from": {"id": chat_id},
        "message": {"message_id": msg_id, "text": ""},
        "data": data,
    }


def test_task_priority_backlog_success_sends_confirmation():
    org._workflow[123] = {"data": {"name": "Neue Aufgabe", "datum": None}}
    sent = []
    with patch("bots.organizer.nocodb_direct") as mock_nd, \
         patch("bots.organizer.answer_callback_query"), \
         patch("bots.organizer.send_message", side_effect=lambda t, c, m, **kw: sent.append(m)):
        mock_nd.create_backlog_item.return_value = True
        org._handle_callback(_cq("task:priority:mittel"))
    mock_nd.create_backlog_item.assert_called_once_with("Neue Aufgabe", "Mittel")
    assert any("✅" in m and "Backlog" in m for m in sent)


def test_task_priority_backlog_failure_sends_error():
    org._workflow[123] = {"data": {"name": "Neue Aufgabe", "datum": None}}
    sent = []
    with patch("bots.organizer.nocodb_direct") as mock_nd, \
         patch("bots.organizer.answer_callback_query"), \
         patch("bots.organizer.send_message", side_effect=lambda t, c, m, **kw: sent.append(m)):
        mock_nd.create_backlog_item.return_value = False
        org._handle_callback(_cq("task:priority:mittel"))
    assert any("❌" in m for m in sent)

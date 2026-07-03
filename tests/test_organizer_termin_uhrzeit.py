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


def test_termin_priority_passes_uhrzeit_to_create_task():
    org._workflow[123] = {"data": {"name": "Zahnarzt", "datum": "morgen um 14:30"}}
    with patch("bots.organizer.nocodb_direct") as mock_nd, \
         patch("bots.organizer.answer_callback_query"), \
         patch("bots.organizer.send_message"):
        mock_nd.create_task.return_value = True
        org._handle_callback(_cq("termin:priority:hoch"))
    args, kwargs = mock_nd.create_task.call_args
    assert kwargs.get("uhrzeit") == "14:30"
    assert args[0] == "Zahnarzt"


def test_termin_priority_datum_has_no_time_suffix():
    org._workflow[123] = {"data": {"name": "Zahnarzt", "datum": "morgen um 14:30"}}
    with patch("bots.organizer.nocodb_direct") as mock_nd, \
         patch("bots.organizer.answer_callback_query"), \
         patch("bots.organizer.send_message"):
        mock_nd.create_task.return_value = True
        org._handle_callback(_cq("termin:priority:hoch"))
    args, kwargs = mock_nd.create_task.call_args
    datum_arg = args[1]
    assert "T" not in datum_arg
    assert len(datum_arg) == 10

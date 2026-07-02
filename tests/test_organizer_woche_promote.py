import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("TOKEN_ORGANIZER", "test")

from unittest.mock import patch
import bots.organizer as org


def _cq(data, msg_id=42, chat_id=123, text=""):
    return {
        "id": "cq1",
        "from": {"id": chat_id},
        "data": data,
        "message": {"message_id": msg_id, "chat": {"id": chat_id}, "text": text},
    }


def _src():
    with open(os.path.join(os.path.dirname(__file__), "..", "bots", "organizer.py"),
              encoding="utf-8") as f:
        return f.read()


class TestWochePromoteCallback(unittest.TestCase):
    def test_handler_present(self):
        self.assertIn('data.startswith("woche_promote:")', _src())

    def test_handler_validates_digit_id(self):
        src = _src()
        idx = src.index('data.startswith("woche_promote:")')
        snippet = src[idx:idx + 500]
        self.assertIn("isdigit()", snippet)

    def test_handler_calls_create_task(self):
        src = _src()
        idx = src.index('data.startswith("woche_promote:")')
        snippet = src[idx:idx + 700]
        self.assertIn("nocodb_direct.create_task", snippet)

    def test_handler_calls_fetch_backlog_items(self):
        src = _src()
        idx = src.index('data.startswith("woche_promote:")')
        snippet = src[idx:idx + 700]
        self.assertIn("fetch_backlog_items", snippet)


class TestWochePromoteCallbackBehavior(unittest.TestCase):
    def test_found_item_creates_task_and_sends_success(self):
        sent = []
        with patch("bots.organizer.nocodb_direct") as mock_nd, \
             patch("bots.organizer.answer_callback_query"), \
             patch("bots.organizer.send_message",
                   side_effect=lambda t, c, m, **kw: sent.append(m)):
            mock_nd.fetch_backlog_items.return_value = [
                {"id": "7", "name": "Steuererklärung", "prio": "Niedrig"}
            ]
            mock_nd.create_task.return_value = True
            org._handle_callback(_cq("woche_promote:7"))
        today = org.date.today().isoformat()
        mock_nd.create_task.assert_called_once_with("Steuererklärung", today, "Hoch")
        assert any("Steuererklärung" in m for m in sent)

    def test_item_not_found_sends_error_and_skips_create_task(self):
        sent = []
        with patch("bots.organizer.nocodb_direct") as mock_nd, \
             patch("bots.organizer.answer_callback_query"), \
             patch("bots.organizer.send_message",
                   side_effect=lambda t, c, m, **kw: sent.append(m)):
            mock_nd.fetch_backlog_items.return_value = []
            org._handle_callback(_cq("woche_promote:999"))
        mock_nd.create_task.assert_not_called()
        assert any("❌" in m for m in sent)

    def test_non_digit_id_returns_early(self):
        with patch("bots.organizer.nocodb_direct") as mock_nd, \
             patch("bots.organizer.answer_callback_query") as mock_ack, \
             patch("bots.organizer.send_message"):
            org._handle_callback(_cq("woche_promote:abc123"))
        mock_ack.assert_called_once_with(org.TOKEN, "cq1", "Veralteter Button – bitte neu laden.")
        mock_nd.fetch_backlog_items.assert_not_called()
        mock_nd.create_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()

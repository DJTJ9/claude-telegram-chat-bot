import io
import json
import unittest
from unittest.mock import patch

from bots import organizer


def _make_handler(body: bytes):
    handler = organizer._WebhookHandler.__new__(organizer._WebhookHandler)
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.send_response = lambda *a, **k: None
    handler.end_headers = lambda: None
    return handler


class TestWebhookRecvLatencyLog(unittest.TestCase):
    def test_do_post_logs_webhook_recv(self):
        body = json.dumps({"message": {"chat": {"id": 1}, "text": "hi"}}).encode()
        handler = _make_handler(body)
        with patch("bots.organizer.threading.Thread"):
            with patch("builtins.print") as mock_print:
                handler.do_POST()
        logged = [c.args[0] for c in mock_print.call_args_list]
        self.assertTrue(any("[LAT] webhook_recv" in line for line in logged))


class TestDispatchUpdateLatencyLog(unittest.TestCase):
    def test_dispatch_update_logs_around_answer_callback_query(self):
        upd = {"callback_query": {"from": {"id": organizer.CHAT_ID}, "id": "cq1",
                                   "data": "wf:abort",
                                   "message": {"message_id": 1, "text": "x"}}}
        with patch("bots.organizer.answer_callback_query") as mock_answer:
            with patch("bots.organizer.send_message"):
                with patch("builtins.print") as mock_print:
                    organizer._dispatch_update(upd)
        logged = [c.args[0] for c in mock_print.call_args_list]
        self.assertTrue(any("[LAT] before_answer_cbq" in line for line in logged))
        self.assertTrue(any("[LAT] after_answer_cbq" in line for line in logged))
        mock_answer.assert_called()


class TestTaskEditListLatencyLog(unittest.TestCase):
    def test_start_workflow_task_edit_list_logs_around_fetch(self):
        with patch("bots.organizer.nocodb_direct.fetch_open_tasks", return_value=[]) as mock_fetch:
            with patch("bots.organizer.send_message"):
                with patch("builtins.print") as mock_print:
                    organizer.start_workflow("task_edit_list", organizer.CHAT_ID)
        logged = [c.args[0] for c in mock_print.call_args_list]
        self.assertTrue(any("[LAT] before_fetch_open_tasks" in line for line in logged))
        self.assertTrue(any("[LAT] after_fetch_open_tasks" in line for line in logged))
        mock_fetch.assert_called_once()


class TestTaskModeNewLatencyLog(unittest.TestCase):
    def test_task_mode_new_logs_around_send_message(self):
        cq = {"from": {"id": organizer.CHAT_ID}, "id": "cq2", "data": "task:mode:new",
              "message": {"message_id": 1, "text": "x"}}
        with patch("bots.organizer.answer_callback_query"):
            with patch("bots.organizer.send_message") as mock_send:
                with patch("builtins.print") as mock_print:
                    organizer._handle_callback(cq)
        logged = [c.args[0] for c in mock_print.call_args_list]
        self.assertTrue(any("[LAT] before_send_task_mode_msg" in line for line in logged))
        self.assertTrue(any("[LAT] after_send_task_mode_msg" in line for line in logged))
        mock_send.assert_called_once()


if __name__ == "__main__":
    unittest.main()

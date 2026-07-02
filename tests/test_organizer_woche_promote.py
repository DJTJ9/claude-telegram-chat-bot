import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


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


if __name__ == "__main__":
    unittest.main()

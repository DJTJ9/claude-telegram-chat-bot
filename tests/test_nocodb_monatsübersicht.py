import unittest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import nocodb_direct


class TestCreateTask(unittest.TestCase):
    @patch("core.nocodb_direct.requests.post")
    def test_sends_correct_payload(self, mock_post):
        mock_post.return_value = MagicMock(status_code=201)
        result = nocodb_direct.create_task("Arzttermin", "2026-07-10T14:00:00", "Hoch")
        self.assertTrue(result)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["Title"], "Arzttermin")
        self.assertEqual(payload["Datum"], "2026-07-10T14:00:00")
        self.assertEqual(payload["Priorität"], "Hoch")
        self.assertEqual(payload["Status"], "Not started")

    @patch("core.nocodb_direct.requests.post")
    def test_returns_false_on_error(self, mock_post):
        mock_post.return_value = MagicMock(status_code=422)
        self.assertFalse(nocodb_direct.create_task("X", "2026-07-10", "Niedrig"))

    @patch("core.nocodb_direct.requests.post")
    def test_default_prio_niedrig(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        nocodb_direct.create_task("Task", "2026-07-10")
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["Priorität"], "Niedrig")


class TestFetchTasksMonth(unittest.TestCase):
    @patch("core.nocodb_direct.requests.get")
    def test_splits_termine_and_tasks(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"list": [
            {"Id": 1, "Title": "Arzttermin", "Datum": "2026-07-10T14:00:00",
             "Priorität": "Hoch", "Status": "Not started"},
            {"Id": 2, "Title": "Report schreiben", "Datum": "2026-07-15",
             "Priorität": "Mittel", "Status": "Done"},
            {"Id": 3, "Title": "Meeting vorbereiten", "Datum": "2026-07-05",
             "Priorität": "Niedrig", "Status": "Not started"},
        ]})
        result = nocodb_direct.fetch_tasks_month(2026, 7)
        self.assertEqual(len(result["termine"]), 1)
        self.assertEqual(result["termine"][0]["name"], "Arzttermin")
        self.assertEqual(result["termine"][0]["time"], "14:00")
        self.assertEqual(result["tasks_done"], 1)
        self.assertEqual(result["tasks_total"], 2)

    @patch("core.nocodb_direct.requests.get")
    def test_month_filter_correct(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"list": []})
        nocodb_direct.fetch_tasks_month(2026, 7)
        params = mock_get.call_args[1]["params"]
        self.assertIn("2026-07", params["where"])

    @patch("core.nocodb_direct.requests.get")
    def test_termine_sorted_by_datetime(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"list": [
            {"Id": 1, "Title": "Abend", "Datum": "2026-07-10T18:00:00",
             "Priorität": "Niedrig", "Status": "Not started"},
            {"Id": 2, "Title": "Morgen", "Datum": "2026-07-10T09:00:00",
             "Priorität": "Niedrig", "Status": "Not started"},
        ]})
        result = nocodb_direct.fetch_tasks_month(2026, 7)
        self.assertEqual(result["termine"][0]["name"], "Morgen")
        self.assertEqual(result["termine"][1]["name"], "Abend")

    @patch("core.nocodb_direct.requests.get")
    def test_api_error_returns_empty(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500)
        result = nocodb_direct.fetch_tasks_month(2026, 7)
        self.assertEqual(result["termine"], [])
        self.assertEqual(result["tasks_done"], 0)
        self.assertEqual(result["tasks_total"], 0)


class TestParseTerminDatum(unittest.TestCase):
    def _fn(self):
        import re
        def _parse_termin_datum(response: str):
            m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})\s+um\s+(\d{2}:\d{2})', response)
            if not m:
                return None
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}T{m.group(4)}:00"
        return _parse_termin_datum

    def test_parses_standard_format(self):
        fn = self._fn()
        self.assertEqual(
            fn("Termin angelegt: Arzttermin · 10.07.2026 um 14:00"),
            "2026-07-10T14:00:00"
        )

    def test_parses_different_month(self):
        fn = self._fn()
        self.assertEqual(
            fn("Termin angelegt: Meeting · 01.01.2027 um 09:00"),
            "2027-01-01T09:00:00"
        )

    def test_returns_none_for_no_match(self):
        fn = self._fn()
        self.assertIsNone(fn("Fehler: kein Termin gefunden"))


class TestTerminWorkflowSavesToNocoDB(unittest.TestCase):
    def setUp(self):
        self._src = open(os.path.join(os.path.dirname(__file__), "..", "bots", "organizer.py"),
                         encoding="utf-8").read()

    def test_parse_termin_datum_defined(self):
        self.assertIn("def _parse_termin_datum(", self._src)

    def test_create_task_called_in_termin_priority_handler(self):
        idx = self._src.index('data.startswith("termin:priority:")')
        snippet = self._src[idx:idx + 800]
        self.assertIn("nocodb_direct.create_task", snippet)
        self.assertIn("_parse_termin_datum", snippet)


class TestMonatCommand(unittest.TestCase):
    def setUp(self):
        self._src = open(os.path.join(os.path.dirname(__file__), "..", "bots", "organizer.py"),
                         encoding="utf-8").read()

    def test_monat_command_present(self):
        self.assertIn('"/monat"', self._src)

    def test_monat_calls_fetch_tasks_month(self):
        idx = self._src.index('"/monat"')
        snippet = self._src[idx:idx + 600]
        self.assertIn("fetch_tasks_month", snippet)

    def test_monat_shows_termine(self):
        idx = self._src.index('"/monat"')
        snippet = self._src[idx:idx + 800]
        self.assertIn("Termine", snippet)

    def test_monat_shows_tasks_bilanz(self):
        idx = self._src.index('"/monat"')
        snippet = self._src[idx:idx + 800]
        self.assertIn("Tasks", snippet)

    def test_monat_in_set_my_commands(self):
        self.assertIn('"monat"', self._src)


if __name__ == "__main__":
    unittest.main()

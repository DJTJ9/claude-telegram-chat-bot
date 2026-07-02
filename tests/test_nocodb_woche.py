import unittest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import nocodb_direct


class TestFetchWocheData(unittest.TestCase):
    def _tasks_response(self, rows):
        return MagicMock(status_code=200, json=lambda: {"list": rows})

    @patch("core.nocodb_direct.fetch_backlog_items")
    @patch("core.nocodb_direct.fetch_habits")
    @patch("core.nocodb_direct.requests.get")
    def test_splits_appointments_and_tasks_within_window(self, mock_get, mock_habits, mock_backlog):
        mock_get.return_value = self._tasks_response([
            {"Id": 1, "Title": "Zahnarzt", "Datum": "2026-07-08T14:00:00",
             "Priorität": "Hoch", "Status": "Not started"},
            {"Id": 2, "Title": "Rechnung stellen", "Datum": "2026-07-09",
             "Priorität": "Hoch", "Status": "Not started"},
            {"Id": 3, "Title": "Zu spät", "Datum": "2026-07-20",
             "Priorität": "Niedrig", "Status": "Not started"},
        ])
        mock_habits.return_value = []
        mock_backlog.return_value = []
        result = nocodb_direct.fetch_woche_data("2026-07-06")
        self.assertEqual(len(result["appointments"]), 1)
        self.assertEqual(result["appointments"][0]["name"], "Zahnarzt")
        self.assertEqual(result["appointments"][0]["time"], "14:00")
        self.assertEqual(len(result["tasks"]), 1)
        self.assertEqual(result["tasks"][0]["name"], "Rechnung stellen")

    @patch("core.nocodb_direct.fetch_backlog_items")
    @patch("core.nocodb_direct.fetch_habits")
    @patch("core.nocodb_direct.requests.get")
    def test_window_is_seven_days_inclusive(self, mock_get, mock_habits, mock_backlog):
        mock_get.return_value = self._tasks_response([
            {"Id": 1, "Title": "Letzter Tag", "Datum": "2026-07-12",
             "Priorität": "Mittel", "Status": "Not started"},
            {"Id": 2, "Title": "Achter Tag", "Datum": "2026-07-13",
             "Priorität": "Mittel", "Status": "Not started"},
        ])
        mock_habits.return_value = []
        mock_backlog.return_value = []
        result = nocodb_direct.fetch_woche_data("2026-07-06")
        names = [t["name"] for t in result["tasks"]]
        self.assertIn("Letzter Tag", names)
        self.assertNotIn("Achter Tag", names)
        self.assertEqual(result["end"], "2026-07-12")

    @patch("core.nocodb_direct.fetch_backlog_items")
    @patch("core.nocodb_direct.fetch_habits")
    @patch("core.nocodb_direct.requests.get")
    def test_tasks_sorted_by_priority(self, mock_get, mock_habits, mock_backlog):
        mock_get.return_value = self._tasks_response([
            {"Id": 1, "Title": "Niedrig-Task", "Datum": "2026-07-07",
             "Priorität": "Niedrig", "Status": "Not started"},
            {"Id": 2, "Title": "Hoch-Task", "Datum": "2026-07-07",
             "Priorität": "Hoch", "Status": "Not started"},
        ])
        mock_habits.return_value = []
        mock_backlog.return_value = []
        result = nocodb_direct.fetch_woche_data("2026-07-06")
        self.assertEqual(result["tasks"][0]["name"], "Hoch-Task")

    @patch("core.nocodb_direct.fetch_backlog_items")
    @patch("core.nocodb_direct.fetch_habits")
    @patch("core.nocodb_direct.requests.get")
    def test_habit_due_on_any_day_in_window_appears_once(self, mock_get, mock_habits, mock_backlog):
        mock_get.return_value = self._tasks_response([])
        mock_habits.return_value = [
            {"id": "1", "name": "Meditieren", "kategorie": "", "zyklus": "täglich", "status": "Not Started"},
        ]
        mock_backlog.return_value = []
        result = nocodb_direct.fetch_woche_data("2026-07-06")
        self.assertEqual(len(result["habits"]), 1)
        self.assertEqual(result["habits"][0]["name"], "Meditieren")

    @patch("core.nocodb_direct.fetch_backlog_items")
    @patch("core.nocodb_direct.fetch_habits")
    @patch("core.nocodb_direct.requests.get")
    def test_backlog_filtered_to_hoch(self, mock_get, mock_habits, mock_backlog):
        mock_get.return_value = self._tasks_response([])
        mock_habits.return_value = []
        mock_backlog.return_value = [
            {"id": "1", "name": "Umzug planen", "prio": "Hoch"},
            {"id": "2", "name": "Regal aufbauen", "prio": "Niedrig"},
        ]
        result = nocodb_direct.fetch_woche_data("2026-07-06")
        self.assertEqual(len(result["backlog"]), 1)
        self.assertEqual(result["backlog"][0]["name"], "Umzug planen")

    @patch("core.nocodb_direct.fetch_backlog_items")
    @patch("core.nocodb_direct.fetch_habits")
    @patch("core.nocodb_direct.requests.get")
    def test_termin_days_tracked(self, mock_get, mock_habits, mock_backlog):
        mock_get.return_value = self._tasks_response([
            {"Id": 1, "Title": "Zahnarzt", "Datum": "2026-07-08T14:00:00",
             "Priorität": "Hoch", "Status": "Not started"},
        ])
        mock_habits.return_value = []
        mock_backlog.return_value = []
        result = nocodb_direct.fetch_woche_data("2026-07-06")
        self.assertIn("2026-07-08", result["termin_days"])

    @patch("core.nocodb_direct.fetch_backlog_items")
    @patch("core.nocodb_direct.fetch_habits")
    @patch("core.nocodb_direct.requests.get")
    def test_api_error_returns_empty_lists(self, mock_get, mock_habits, mock_backlog):
        mock_get.return_value = MagicMock(status_code=500)
        mock_habits.return_value = []
        mock_backlog.return_value = []
        result = nocodb_direct.fetch_woche_data("2026-07-06")
        self.assertEqual(result["appointments"], [])
        self.assertEqual(result["tasks"], [])


if __name__ == "__main__":
    unittest.main()

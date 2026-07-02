import os, sys, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("NOCODB_API_URL", "http://localhost:8090")
os.environ.setdefault("NOCODB_API_TOKEN", "test_token")
os.environ.setdefault("NOCODB_TASKS_TABLE_ID", "tbl_tasks")
os.environ.setdefault("NOCODB_SPORT_TABLE_ID", "tbl_sport")
os.environ.setdefault("NOCODB_IDEENSAMMLUNG_TABLE_ID", "tbl_ideas")
os.environ.setdefault("NOCODB_BACKLOG_TABLE_ID", "tbl_backlog")
os.environ.setdefault("NOCODB_ARCHIV_TABLE_ID", "tbl_archiv")

from core.nocodb_direct import (
    mark_done, reschedule, add_idea, mark_sport_done,
    _habit_due_today, fetch_habits_due,
)


class TestMarkDone(unittest.TestCase):
    @patch("core.nocodb_direct.requests.patch")
    def test_patches_correct_url_with_done_status(self, mock_patch):
        mock_patch.return_value.status_code = 200
        result = mark_done(42)
        self.assertTrue(result)
        url = mock_patch.call_args[0][0]
        self.assertIn("tbl_tasks", url)
        self.assertNotIn("/42", url)
        payload = mock_patch.call_args[1]["json"]
        self.assertEqual(payload[0]["Id"], 42)
        self.assertEqual(payload[0]["Status"], "Done")


class TestReschedule(unittest.TestCase):
    @patch("core.nocodb_direct.requests.patch")
    def test_patches_with_date(self, mock_patch):
        mock_patch.return_value.status_code = 200
        reschedule(5, "2026-07-01")
        payload = mock_patch.call_args[1]["json"]
        self.assertEqual(payload[0]["Id"], 5)
        self.assertEqual(payload[0]["Datum"], "2026-07-01")


class TestAddIdea(unittest.TestCase):
    @patch("core.nocodb_direct.requests.post")
    def test_posts_to_ideensammlung_table(self, mock_post):
        mock_post.return_value.status_code = 200
        add_idea("neue Idee")
        url = mock_post.call_args[0][0]
        self.assertIn("tbl_ideas", url)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["Name"], "neue Idee")


class TestMarkSportDone(unittest.TestCase):
    @patch("core.nocodb_direct.requests.patch")
    def test_patches_sport_table(self, mock_patch):
        mock_patch.return_value.status_code = 200
        mark_sport_done(7)
        url = mock_patch.call_args[0][0]
        self.assertIn("tbl_sport", url)
        self.assertNotIn("/7", url)
        payload = mock_patch.call_args[1]["json"]
        self.assertEqual(payload[0]["Id"], 7)
        self.assertEqual(payload[0]["Status"], "Done")


class TestFetchBacklogItems(unittest.TestCase):
    @patch("core.nocodb_direct.requests.get")
    def test_returns_sorted_list(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "list": [
                {"Id": 1, "Name": "Task A", "Priorität": "Niedrig"},
                {"Id": 2, "Name": "Task B", "Priorität": "Hoch"},
            ]
        }
        from core.nocodb_direct import fetch_backlog_items
        items = fetch_backlog_items()
        self.assertEqual(items[0]["name"], "Task B")
        self.assertEqual(items[0]["id"], "2")

    @patch("core.nocodb_direct.requests.get")
    def test_returns_empty_on_error(self, mock_get):
        mock_get.return_value.status_code = 500
        from core.nocodb_direct import fetch_backlog_items
        self.assertEqual(fetch_backlog_items(), [])


class TestCreateBacklogItem(unittest.TestCase):
    @patch("core.nocodb_direct.requests.post")
    def test_posts_to_backlog_table(self, mock_post):
        mock_post.return_value.status_code = 200
        from core.nocodb_direct import create_backlog_item
        result = create_backlog_item("Neue Aufgabe", "Mittel")
        self.assertTrue(result)
        url = mock_post.call_args[0][0]
        self.assertIn("tbl_backlog", url)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["Name"], "Neue Aufgabe")
        self.assertEqual(payload["Status"], "Offen")
        self.assertEqual(payload["Priorität"], "Mittel")


class TestHabitDueToday(unittest.TestCase):
    def test_taeglich_always_due(self):
        self.assertTrue(_habit_due_today("täglich", weekday=2))

    def test_specific_weekday_matches(self):
        self.assertTrue(_habit_due_today("montags", weekday=0))

    def test_specific_weekday_does_not_match_other_day(self):
        self.assertFalse(_habit_due_today("montags", weekday=1))

    def test_wochentags_true_on_weekday(self):
        self.assertTrue(_habit_due_today("wochentags", weekday=3))

    def test_wochentags_false_on_weekend(self):
        self.assertFalse(_habit_due_today("wochentags", weekday=5))

    def test_wochenends_true_on_saturday(self):
        self.assertTrue(_habit_due_today("wochenends", weekday=5))

    def test_unknown_format_defaults_to_due(self):
        self.assertTrue(_habit_due_today("alle 3 Tage", weekday=0))

    def test_empty_zyklus_defaults_to_due(self):
        self.assertTrue(_habit_due_today("", weekday=0))


class TestFetchHabitsDue(unittest.TestCase):
    @patch("core.nocodb_direct.requests.get")
    def test_filters_done_and_keeps_due(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Name": "Laufen", "Kategorie": "Gesundheit", "Zyklus": "täglich", "Status": "Not Started"},
            {"Id": 2, "Name": "Meditieren", "Kategorie": "Gesundheit", "Zyklus": "montags", "Status": "Not Started"},
            {"Id": 3, "Name": "Lesen", "Kategorie": "Lernen", "Zyklus": "täglich", "Status": "Done"},
        ]}
        result = fetch_habits_due("2026-07-06")  # Montag
        names = [h["name"] for h in result]
        self.assertEqual(names, ["Laufen", "Meditieren"])

    @patch("core.nocodb_direct.requests.get")
    def test_excludes_habit_not_due_today(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Name": "Meditieren", "Kategorie": "Gesundheit", "Zyklus": "montags", "Status": "Not Started"},
        ]}
        result = fetch_habits_due("2026-07-07")  # Dienstag
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()

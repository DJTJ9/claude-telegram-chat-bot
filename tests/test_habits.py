import os, sys, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("NOCODB_API_URL", "http://localhost:8090")
os.environ.setdefault("NOCODB_API_TOKEN", "test_token")
os.environ.setdefault("NOCODB_BASE_ID", "test_base")
os.environ.setdefault("NOCODB_HABITS_TABLE_ID", "tbl_habits")

import scripts.nocodb_create_table as ct


class TestCreateHabitsTable(unittest.TestCase):
    def test_create_habits_table_function_exists(self):
        self.assertTrue(callable(getattr(ct, "create_habits_table", None)))

    @patch("scripts.nocodb_create_table.requests.post")
    def test_create_habits_table_posts_correct_schema(self, mock_post):
        mock_post.return_value.json.return_value = {"id": "tbl_habits_123"}
        table_id = ct.create_habits_table()
        self.assertEqual(table_id, "tbl_habits_123")
        payload = mock_post.call_args[1]["json"]
        col_titles = [c["title"] for c in payload["columns"]]
        self.assertIn("Name", col_titles)
        self.assertIn("Kategorie", col_titles)
        self.assertIn("Zyklus", col_titles)
        self.assertIn("Status", col_titles)

    def test_habits_flag_in_argparse(self):
        src = Path("scripts/nocodb_create_table.py").read_text()
        self.assertIn("--habits", src)


from core.nocodb_direct import fetch_habits, mark_habit_done


class TestFetchHabits(unittest.TestCase):
    @patch("core.nocodb_direct.requests.get")
    def test_returns_list_of_dicts(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Name": "Meditation", "Kategorie": "Gesundheit",
             "Zyklus": "täglich", "Status": "Not Started"},
            {"Id": 2, "Name": "Lesen", "Kategorie": "Lernen",
             "Zyklus": "täglich", "Status": "Done"},
        ]}
        result = fetch_habits()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "Meditation")
        self.assertEqual(result[0]["id"], "1")
        self.assertEqual(result[0]["kategorie"], "Gesundheit")

    @patch("core.nocodb_direct.requests.get")
    def test_uses_habits_table_id(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": []}
        fetch_habits()
        url = mock_get.call_args[0][0]
        self.assertIn("tbl_habits", url)

    @patch("core.nocodb_direct.requests.get")
    def test_returns_empty_on_api_error(self, mock_get):
        mock_get.return_value.status_code = 500
        result = fetch_habits()
        self.assertEqual(result, [])


class TestMarkHabitDone(unittest.TestCase):
    @patch("core.nocodb_direct.requests.patch")
    def test_patches_habit_with_done_status(self, mock_patch):
        mock_patch.return_value.status_code = 200
        result = mark_habit_done(3)
        self.assertTrue(result)
        url = mock_patch.call_args[0][0]
        self.assertIn("tbl_habits", url)
        self.assertIn("/3", url)
        payload = mock_patch.call_args[1]["json"]
        self.assertEqual(payload["Status"], "Done")


class TestSeedHabits(unittest.TestCase):
    def test_seed_script_exists(self):
        self.assertTrue(Path("scripts/seed_habits.py").exists())

    def test_seed_script_has_five_habits(self):
        src = Path("scripts/seed_habits.py").read_text()
        self.assertIn("Meditation", src)
        self.assertIn("Lesen", src)
        self.assertIn("Sport", src)
        self.assertIn("Dankbarkeit", src)
        self.assertIn("Journaling", src)


if __name__ == "__main__":
    unittest.main()

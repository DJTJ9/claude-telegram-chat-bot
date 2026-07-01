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

from core.nocodb_direct import mark_done, reschedule, add_idea, mark_sport_done


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


if __name__ == "__main__":
    unittest.main()

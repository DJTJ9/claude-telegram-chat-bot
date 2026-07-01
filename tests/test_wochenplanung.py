import os, sys, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("NOCODB_API_URL", "http://localhost:8090")
os.environ.setdefault("NOCODB_API_TOKEN", "test_token")
os.environ.setdefault("NOCODB_BASE_ID", "test_base")
os.environ.setdefault("NOCODB_TASKS_TABLE_ID", "tbl_tasks_123")
os.environ.setdefault("NOCODB_BACKLOG_TABLE_ID", "tbl_backlog_456")

import scripts.nocodb_create_table as ct


class TestCreateWochenplanungView(unittest.TestCase):
    def test_function_exists(self):
        self.assertTrue(callable(getattr(ct, "create_wochenplanung_view", None)))

    def test_wochenplanung_flag_in_argparse(self):
        src = Path("scripts/nocodb_create_table.py").read_text()
        self.assertIn("--wochenplanung", src)

    @patch("scripts.nocodb_create_table.requests.post")
    @patch("scripts.nocodb_create_table.requests.get")
    def test_creates_view_with_correct_title(self, mock_get, mock_post):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "columns": [
                {"id": "col_datum_id", "title": "Datum"},
                {"id": "col_name_id", "title": "Name"},
            ]
        }
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.side_effect = [
            {"id": "vw_woche_001"},
            {"id": "flt_001"},
            {"id": "srt_001"},
        ]
        view_id = ct.create_wochenplanung_view()
        self.assertEqual(view_id, "vw_woche_001")
        first_post_payload = mock_post.call_args_list[0][1]["json"]
        self.assertEqual(first_post_payload["title"], "Wochenplanung")

    @patch("scripts.nocodb_create_table.requests.post")
    @patch("scripts.nocodb_create_table.requests.get")
    def test_sets_iswithin_thisweek_filter(self, mock_get, mock_post):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "columns": [{"id": "col_datum_id", "title": "Datum"}]
        }
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.side_effect = [
            {"id": "vw_woche_001"},
            {"id": "flt_001"},
            {"id": "srt_001"},
        ]
        ct.create_wochenplanung_view()
        filter_payload = mock_post.call_args_list[1][1]["json"]
        self.assertEqual(filter_payload["fk_column_id"], "col_datum_id")
        self.assertEqual(filter_payload["comparison_op"], "isWithin")
        self.assertEqual(filter_payload["comparison_sub_op"], "thisWeek")

    @patch("scripts.nocodb_create_table.requests.post")
    @patch("scripts.nocodb_create_table.requests.get")
    def test_sets_datum_asc_sort(self, mock_get, mock_post):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "columns": [{"id": "col_datum_id", "title": "Datum"}]
        }
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.side_effect = [
            {"id": "vw_woche_001"},
            {"id": "flt_001"},
            {"id": "srt_001"},
        ]
        ct.create_wochenplanung_view()
        sort_payload = mock_post.call_args_list[2][1]["json"]
        self.assertEqual(sort_payload["fk_column_id"], "col_datum_id")
        self.assertEqual(sort_payload["direction"], "asc")


if __name__ == "__main__":
    unittest.main()

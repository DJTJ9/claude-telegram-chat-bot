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


import scripts.nocodb_promote_backlog as pb


class TestNocobdPromoteBacklog(unittest.TestCase):
    def test_script_exists(self):
        self.assertTrue(Path("scripts/nocodb_promote_backlog.py").exists())

    @patch("scripts.nocodb_promote_backlog.requests.get")
    def test_fetch_open_backlog_items(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Name": "Backlog Task A", "Status": "Offen", "Priorität": "Hoch"},
            {"Id": 2, "Name": "Backlog Task B", "Status": "Offen", "Priorität": "Mittel"},
        ]}
        items = pb.fetch_open_backlog()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["Name"], "Backlog Task A")

    @patch("scripts.nocodb_promote_backlog.requests.get")
    def test_fetch_filters_offen_only(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": []}
        pb.fetch_open_backlog()
        params = mock_get.call_args[1]["params"]
        self.assertIn("Offen", str(params))

    @patch("scripts.nocodb_promote_backlog.requests.post")
    def test_promote_creates_task_with_datum(self, mock_post):
        mock_post.return_value.status_code = 200
        pb.promote_to_task("Fix login bug", "Hoch", "2026-07-03")
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["Name"], "Fix login bug")
        self.assertEqual(payload["Datum"], "2026-07-03")
        self.assertEqual(payload["Priorität"], "Hoch")
        self.assertEqual(payload["Status"], "Not started")

    @patch("scripts.nocodb_promote_backlog.requests.post")
    def test_promote_uses_tasks_table_id(self, mock_post):
        mock_post.return_value.status_code = 200
        pb.promote_to_task("Task X", "Mittel", "2026-07-04")
        url = mock_post.call_args[0][0]
        self.assertIn("tbl_tasks_123", url)


if __name__ == "__main__":
    unittest.main()

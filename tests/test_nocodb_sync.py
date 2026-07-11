import json, os, sys, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("NOCODB_API_URL", "http://localhost:8090")
os.environ.setdefault("NOCODB_API_TOKEN", "test_token")
os.environ.setdefault("NOCODB_BASE_ID", "test_base")

from scripts.nocodb_sync import (
    _headers, _table_url, load_nocodb_table_id, find_row, upsert_feature,
    sync_dev_to_nocodb, sync_nocodb_to_dev,
    _get_all_rows, _insert_row_at_top, _insert_row_after, _move_row_to_top, _move_row_to_end,
)

FAKE_REGISTRY = [
    {"slug": "test-proj", "name": "Test", "nocodb_table_id": "tbl_abc123"},
    {"slug": "no-table", "name": "NoTable"},
]


class TestHeaders(unittest.TestCase):
    def test_headers_have_xc_token(self):
        h = _headers()
        self.assertEqual(h["xc-token"], "test_token")
        self.assertEqual(h["Content-Type"], "application/json")


class TestTableUrl(unittest.TestCase):
    def test_table_url_format(self):
        url = _table_url("tbl_abc123")
        self.assertEqual(url, "http://localhost:8090/api/v2/tables/tbl_abc123/records")


class TestLoadTableId(unittest.TestCase):
    def test_returns_table_id_for_known_slug(self):
        with patch("scripts.nocodb_sync.load_registry", return_value=FAKE_REGISTRY):
            self.assertEqual(load_nocodb_table_id("test-proj"), "tbl_abc123")

    def test_returns_empty_for_missing_slug(self):
        with patch("scripts.nocodb_sync.load_registry", return_value=FAKE_REGISTRY):
            self.assertEqual(load_nocodb_table_id("unknown"), "")

    def test_returns_empty_for_missing_field(self):
        with patch("scripts.nocodb_sync.load_registry", return_value=FAKE_REGISTRY):
            self.assertEqual(load_nocodb_table_id("no-table"), "")


class TestFindRow(unittest.TestCase):
    @patch("scripts.nocodb_sync.requests.get")
    def test_returns_row_when_found(self, mock_get):
        mock_get.return_value.json.return_value = {
            "list": [{"Id": 42, "Name": "Feature A", "Status": "idea"}]
        }
        row = find_row("tbl_abc123", "Feature A")
        self.assertEqual(row["Id"], 42)
        call_url = mock_get.call_args[0][0]
        self.assertIn("tbl_abc123", call_url)

    @patch("scripts.nocodb_sync.requests.get")
    def test_returns_none_when_not_found(self, mock_get):
        mock_get.return_value.json.return_value = {"list": []}
        self.assertIsNone(find_row("tbl_abc123", "Unknown"))


class TestUpsertFeature(unittest.TestCase):
    @patch("scripts.nocodb_sync.find_row", return_value=None)
    @patch("scripts.nocodb_sync.requests.post")
    def test_creates_row_when_not_found(self, mock_post, mock_find):
        upsert_feature("tbl_abc123", "Feature A", "idea")
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["Name"], "Feature A")
        self.assertEqual(payload["Status"], "idea")

    @patch("scripts.nocodb_sync.find_row", return_value={"Id": 5})
    @patch("scripts.nocodb_sync.requests.patch")
    def test_updates_row_when_found(self, mock_patch, mock_find):
        upsert_feature("tbl_abc123", "Feature A", "discussed", spec="specs/foo.md")
        mock_patch.assert_called_once()
        url = mock_patch.call_args[0][0]
        self.assertNotIn("/5", url)
        body = mock_patch.call_args[1]["json"]
        self.assertEqual(body[0]["Id"], 5)
        self.assertIn("specs/foo.md", body[0].get("Notiz", ""))


class TestUpsertFeatureNoPosition(unittest.TestCase):
    @patch("scripts.nocodb_sync.find_row", return_value=None)
    @patch("scripts.nocodb_sync.requests.post")
    def test_never_includes_position_in_payload(self, mock_post, mock_find):
        upsert_feature("tbl_abc123", "Feature A", "idea")
        payload = mock_post.call_args[1]["json"]
        self.assertNotIn("Position", payload)
        self.assertEqual(payload["Name"], "Feature A")
        self.assertEqual(payload["Status"], "idea")


class TestSyncDevToNocodb(unittest.TestCase):
    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    @patch("scripts.nocodb_sync.upsert_feature")
    def test_calls_upsert_with_correct_args(self, mock_upsert, mock_load):
        sync_dev_to_nocodb("test-proj", "My Feature", "planned", spec="specs/foo.md")
        mock_upsert.assert_called_once_with(
            "tbl_abc123", "My Feature", "planned", spec="specs/foo.md", plan="",
            insert_position="bottom", after_name=""
        )

    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="")
    @patch("scripts.nocodb_sync.upsert_feature")
    def test_skips_when_no_table_id(self, mock_upsert, mock_load):
        sync_dev_to_nocodb("unknown", "Feature", "idea")
        mock_upsert.assert_not_called()


import tempfile
from scripts.nocodb_sync import rebuild_nocodb_table, sync_rebuild, regenerate_status_roadmap
from scripts.nocodb_create_table import create_nocodb_table, write_table_id_to_registry


class TestRebuildNocobdTable(unittest.TestCase):
    @patch("scripts.nocodb_sync.requests.post")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.get")
    def test_deletes_all_then_reinserts(self, mock_get, mock_delete, mock_post):
        mock_get.return_value.json.return_value = {
            "list": [{"Id": 1, "Name": "Feature A", "Status": "idea",
                      "Epic": "Epic X"},
                     {"Id": 2, "Name": "Feature B", "Status": "done"}]
        }
        items = [("idea", "Feature A"), ("done", "Feature B")]
        rebuild_nocodb_table("tbl_abc123", items)

        delete_body = mock_delete.call_args[1]["json"]
        self.assertEqual(delete_body, [{"Id": 1}, {"Id": 2}])

        payloads = [c[1]["json"] for c in mock_post.call_args_list]
        self.assertEqual(payloads, [
            {"Name": "Feature A", "Status": "idea", "Epic": "Epic X"},
            {"Name": "Feature B", "Status": "done"},
        ])

    @patch("scripts.nocodb_sync.requests.post")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.get")
    def test_skips_delete_when_table_empty(self, mock_get, mock_delete, mock_post):
        mock_get.return_value.json.return_value = {"list": []}
        rebuild_nocodb_table("tbl_abc123", [("idea", "New Feature")])
        mock_delete.assert_not_called()
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args[1]["json"],
                         {"Name": "New Feature", "Status": "idea"})


class TestSyncRebuild(unittest.TestCase):
    @patch("scripts.nocodb_sync.rebuild_nocodb_table")
    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    def test_reads_status_md_and_rebuilds(self, mock_load, mock_rebuild):
        status_content = """# Project Status — test-proj
Active: Feature A
Phase: plan
Spec:
Plan:
Updated: 2026-06-30
## Roadmap
- [idea]      Feature A
- [done]      Feature B
- [idea]      Feature C
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            hub_dir = Path(tmpdir)
            topic_dir = hub_dir / "topics" / "test-proj"
            topic_dir.mkdir(parents=True)
            (topic_dir / "STATUS.md").write_text(status_content)
            with patch.dict(os.environ, {"HUB_DIR": str(hub_dir)}):
                sync_rebuild("test-proj")

        items_arg = mock_rebuild.call_args[0][1]
        self.assertEqual(len(items_arg), 3)
        self.assertEqual(items_arg[-1], ("done", "Feature B"))

    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="")
    @patch("scripts.nocodb_sync.rebuild_nocodb_table")
    def test_skips_when_no_table_id(self, mock_rebuild, mock_load):
        sync_rebuild("unknown-slug")
        mock_rebuild.assert_not_called()

    @patch("scripts.nocodb_sync.rebuild_nocodb_table")
    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    def test_done_items_always_sorted_to_end_regardless_of_status_md_order(self, mock_load, mock_rebuild):
        # Reproduces the bug: finish.md's manual STATUS.md reorder step didn't
        # move the finished [done] feature to the end of the Roadmap section.
        status_content = """# Project Status — test-proj
Active: Feature C
Phase: plan
Spec:
Plan:
Updated: 2026-06-30
## Roadmap
- [idea]      Feature A
- [done]      Feature B
- [idea]      Feature C
- [done]      Feature D
- [planned]   Feature E
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            hub_dir = Path(tmpdir)
            topic_dir = hub_dir / "topics" / "test-proj"
            topic_dir.mkdir(parents=True)
            (topic_dir / "STATUS.md").write_text(status_content)
            with patch.dict(os.environ, {"HUB_DIR": str(hub_dir)}):
                sync_rebuild("test-proj")

        items_arg = mock_rebuild.call_args[0][1]
        statuses = [status for status, _ in items_arg]
        done_indices = [i for i, s in enumerate(statuses) if s == "done"]
        non_done_indices = [i for i, s in enumerate(statuses) if s != "done"]
        self.assertTrue(all(d > n for d in done_indices for n in non_done_indices))
        # relative order among done items is preserved (stable sort)
        self.assertEqual(
            [name for status, name in items_arg if status == "done"],
            ["Feature B", "Feature D"],
        )


class TestCreateNocobdTable(unittest.TestCase):
    @patch("scripts.nocodb_create_table.requests.post")
    def test_posts_to_correct_endpoint(self, mock_post):
        mock_post.return_value.json.return_value = {"id": "tbl_newxyz", "title": "Test"}
        result = create_nocodb_table("test-proj", "Test Proj")
        self.assertEqual(result, "tbl_newxyz")
        url = mock_post.call_args[0][0]
        self.assertIn("/api/v1/db/meta/projects/", url)
        self.assertIn("/tables", url)

    @patch("scripts.nocodb_create_table.requests.post")
    def test_sends_correct_columns(self, mock_post):
        mock_post.return_value.json.return_value = {"id": "tbl_abc"}
        create_nocodb_table("slug", "Name")
        payload = mock_post.call_args[1]["json"]
        titles = [c["title"] for c in payload["columns"]]
        self.assertIn("Name", titles)
        self.assertIn("Status", titles)
        self.assertIn("Notiz", titles)
        self.assertNotIn("Position", titles)


class TestWriteTableIdToRegistry(unittest.TestCase):
    def test_writes_table_id_to_correct_slug(self):
        registry = [{"slug": "proj-a"}, {"slug": "proj-b"}]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(registry, f)
            tmp = Path(f.name)
        write_table_id_to_registry("proj-a", "tbl_xyz", registry_path=tmp)
        data = json.loads(tmp.read_text())
        self.assertEqual(data[0]["nocodb_table_id"], "tbl_xyz")
        self.assertNotIn("nocodb_table_id", data[1])
        tmp.unlink()


class TestSyncNocobdToDev(unittest.TestCase):
    @patch("scripts.nocodb_sync.requests.get")
    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    @patch("scripts.nocodb_sync.load_registry", return_value=[])
    def test_no_sort_id_in_get_params(self, mock_reg, mock_table, mock_get):
        mock_get.return_value.json.return_value = {"list": []}
        sync_nocodb_to_dev("test-proj")
        call_kwargs = mock_get.call_args[1]
        params = call_kwargs.get("params", {})
        self.assertNotIn("sort", params)


class TestGetAllRows(unittest.TestCase):
    @patch("scripts.nocodb_sync.requests.get")
    def test_returns_list_from_response(self, mock_get):
        mock_get.return_value.json.return_value = {
            "list": [{"Id": 1, "Name": "A"}, {"Id": 2, "Name": "B"}]
        }
        rows = _get_all_rows("tbl_abc123")
        self.assertEqual(len(rows), 2)

    @patch("scripts.nocodb_sync.requests.get")
    def test_fetches_without_sort_param(self, mock_get):
        mock_get.return_value.json.return_value = {"list": []}
        _get_all_rows("tbl_abc123")
        params = mock_get.call_args[1].get("params", {})
        self.assertNotIn("sort", params)


class TestInsertRowAtTop(unittest.TestCase):
    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_new_row_is_posted_first(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [
            {"Id": 1, "Name": "Old A", "Status": "idea", "Notiz": ""},
            {"Id": 2, "Name": "Old B", "Status": "done", "Notiz": ""},
        ]
        _insert_row_at_top("tbl_abc123", {"Name": "New", "Status": "discussed"})
        first_post = mock_post.call_args_list[0][1]["json"]
        self.assertEqual(first_post["Name"], "New")

    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_old_rows_reinserted_in_order(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [
            {"Id": 1, "Name": "Old A", "Status": "idea", "Notiz": ""},
            {"Id": 2, "Name": "Old B", "Status": "done", "Notiz": ""},
        ]
        _insert_row_at_top("tbl_abc123", {"Name": "New", "Status": "discussed"})
        names = [c[1]["json"]["Name"] for c in mock_post.call_args_list]
        self.assertEqual(names, ["New", "Old A", "Old B"])

    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_deletes_existing_rows_before_reinsert(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [
            {"Id": 1, "Name": "X", "Status": "idea", "Notiz": ""},
            {"Id": 2, "Name": "Y", "Status": "idea", "Notiz": ""},
        ]
        _insert_row_at_top("tbl_abc123", {"Name": "Z", "Status": "idea"})
        delete_ids = {d["Id"] for d in mock_delete.call_args[1]["json"]}
        self.assertEqual(delete_ids, {1, 2})


class TestInsertRowAfter(unittest.TestCase):
    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_inserts_after_named_row(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [
            {"Id": 1, "Name": "Feature A", "Status": "idea", "Notiz": ""},
            {"Id": 2, "Name": "Feature B", "Status": "idea", "Notiz": ""},
        ]
        _insert_row_after("tbl_abc123", "Feature A", {"Name": "New", "Status": "discussed"})
        names = [c[1]["json"]["Name"] for c in mock_post.call_args_list]
        self.assertEqual(names, ["Feature A", "New", "Feature B"])

    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_appends_at_bottom_when_after_not_found(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [
            {"Id": 1, "Name": "Feature A", "Status": "idea", "Notiz": ""},
        ]
        _insert_row_after("tbl_abc123", "NonExistent", {"Name": "New", "Status": "idea"})
        names = [c[1]["json"]["Name"] for c in mock_post.call_args_list]
        self.assertEqual(names[-1], "New")


class TestMoveRowToTop(unittest.TestCase):
    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_named_row_is_first_after_move(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [
            {"Id": 1, "Name": "Feature A", "Status": "idea", "Notiz": ""},
            {"Id": 2, "Name": "Feature B", "Status": "planned", "Notiz": ""},
            {"Id": 3, "Name": "Feature C", "Status": "done", "Notiz": ""},
        ]
        _move_row_to_top("tbl_abc123", "Feature B")
        names = [c[1]["json"]["Name"] for c in mock_post.call_args_list]
        self.assertEqual(names[0], "Feature B")

    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_all_rows_preserved_after_move(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [
            {"Id": 1, "Name": "A", "Status": "idea", "Notiz": ""},
            {"Id": 2, "Name": "B", "Status": "done", "Notiz": ""},
        ]
        _move_row_to_top("tbl_abc123", "B")
        names = [c[1]["json"]["Name"] for c in mock_post.call_args_list]
        self.assertEqual(set(names), {"A", "B"})

    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_no_op_when_name_not_found(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [{"Id": 1, "Name": "A", "Status": "idea", "Notiz": ""}]
        _move_row_to_top("tbl_abc123", "Missing")
        mock_delete.assert_not_called()
        mock_post.assert_not_called()


class TestUpsertFeatureWithPosition(unittest.TestCase):
    @patch("scripts.nocodb_sync._insert_row_at_top")
    @patch("scripts.nocodb_sync.find_row", return_value=None)
    def test_calls_insert_at_top_for_new_row(self, mock_find, mock_insert_top):
        upsert_feature("tbl_abc123", "New Feature", "discussed", insert_position="top")
        mock_insert_top.assert_called_once()
        payload = mock_insert_top.call_args[0][1]
        self.assertEqual(payload["Name"], "New Feature")

    @patch("scripts.nocodb_sync._insert_row_after")
    @patch("scripts.nocodb_sync.find_row", return_value=None)
    def test_calls_insert_after_when_after_name_set(self, mock_find, mock_insert_after):
        upsert_feature("tbl_abc123", "New", "discussed", after_name="Feature X")
        mock_insert_after.assert_called_once()
        self.assertEqual(mock_insert_after.call_args[0][1], "Feature X")

    @patch("scripts.nocodb_sync.find_row", return_value={"Id": 5})
    @patch("scripts.nocodb_sync.requests.patch")
    def test_patches_existing_row_regardless_of_position(self, mock_patch, mock_find):
        upsert_feature("tbl_abc123", "Existing", "planned", insert_position="top")
        mock_patch.assert_called_once()
        body = mock_patch.call_args[1]["json"]
        self.assertEqual(body[0]["Id"], 5)


class TestSyncDevToNocodbWithPosition(unittest.TestCase):
    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    @patch("scripts.nocodb_sync.upsert_feature")
    def test_passes_insert_position_to_upsert(self, mock_upsert, mock_load):
        sync_dev_to_nocodb("test-proj", "Feature", "discussed", insert_position="top")
        call_kwargs = mock_upsert.call_args[1]
        self.assertEqual(call_kwargs["insert_position"], "top")

    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    @patch("scripts.nocodb_sync.upsert_feature")
    def test_passes_after_name_to_upsert(self, mock_upsert, mock_load):
        sync_dev_to_nocodb("test-proj", "Feature", "idea", after_name="Feature X")
        call_kwargs = mock_upsert.call_args[1]
        self.assertEqual(call_kwargs["after_name"], "Feature X")


class TestMoveRowToEnd(unittest.TestCase):
    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_named_row_is_last_after_move(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [
            {"Id": 1, "Name": "Feature A", "Status": "idea", "Notiz": ""},
            {"Id": 2, "Name": "Feature B", "Status": "planned", "Notiz": ""},
            {"Id": 3, "Name": "Feature C", "Status": "done", "Notiz": ""},
        ]
        _move_row_to_end("tbl_abc123", "Feature A")
        names = [c[1]["json"]["Name"] for c in mock_post.call_args_list]
        self.assertEqual(names[-1], "Feature A")

    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_all_rows_preserved_after_move(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [
            {"Id": 1, "Name": "A", "Status": "idea", "Notiz": ""},
            {"Id": 2, "Name": "B", "Status": "done", "Notiz": ""},
        ]
        _move_row_to_end("tbl_abc123", "A")
        names = [c[1]["json"]["Name"] for c in mock_post.call_args_list]
        self.assertEqual(set(names), {"A", "B"})

    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    def test_no_op_when_name_not_found(self, mock_post, mock_delete, mock_rows):
        mock_rows.return_value = [{"Id": 1, "Name": "A", "Status": "idea", "Notiz": ""}]
        _move_row_to_end("tbl_abc123", "Missing")
        mock_delete.assert_not_called()
        mock_post.assert_not_called()


class TestRegenerateStatusRoadmap(unittest.TestCase):
    STATUS = """# Project Status — test-proj
Active: Feature A
Phase: plan
Updated: 2026-06-30
## Roadmap
- [idea]      Feature A
- [done]      Feature B
- [planned]   Stale Only In Status
"""

    def _run(self, entries):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "STATUS.md"
            p.write_text(self.STATUS)
            regenerate_status_roadmap(p, entries)
            return p.read_text()

    def test_full_projection_matches_nocodb_order_including_done(self):
        text = self._run([
            {"name": "testi test", "status": "idea"},
            {"name": "Feature A", "status": "discussed"},
            {"name": "Feature B", "status": "done"},
        ])
        lines = [l for l in text.splitlines() if l.startswith("- [")]
        self.assertEqual(lines, [
            "- [idea]      testi test",
            "- [discussed] Feature A",
            "- [done]      Feature B",
        ])

    def test_status_only_row_is_dropped(self):
        text = self._run([{"name": "Feature A", "status": "idea"}])
        self.assertNotIn("Stale Only In Status", text)

    def test_empty_name_skipped(self):
        text = self._run([
            {"name": "", "status": "idea"},
            {"name": "Feature A", "status": "idea"},
        ])
        lines = [l for l in text.splitlines() if l.startswith("- [")]
        self.assertEqual(len(lines), 1)

    def test_preserves_trailing_section(self):
        status = self.STATUS + "\n## Notes\nkeep me\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "STATUS.md"
            p.write_text(status)
            regenerate_status_roadmap(p, [{"name": "Feature A", "status": "idea"}])
            out = p.read_text()
        self.assertIn("## Notes", out)
        self.assertIn("keep me", out)


if __name__ == "__main__":
    unittest.main()

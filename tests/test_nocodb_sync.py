import json, os, sys, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("NOCODB_API_URL", "http://localhost:8090")
os.environ.setdefault("NOCODB_API_TOKEN", "test_token")
os.environ.setdefault("NOCODB_BASE_ID", "test_base")

from scripts.nocodb_sync import (
    _headers, _table_url, load_nocodb_table_id, find_row, upsert_feature,
    sync_dev_to_nocodb,
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
        self.assertIn("/5", url)
        payload = mock_patch.call_args[1]["json"]
        self.assertIn("specs/foo.md", payload.get("Notiz", ""))


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
            "tbl_abc123", "My Feature", "planned", spec="specs/foo.md", plan=""
        )

    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="")
    @patch("scripts.nocodb_sync.upsert_feature")
    def test_skips_when_no_table_id(self, mock_upsert, mock_load):
        sync_dev_to_nocodb("unknown", "Feature", "idea")
        mock_upsert.assert_not_called()


import tempfile
from scripts.nocodb_sync import rebuild_nocodb_table, sync_rebuild
from scripts.nocodb_create_table import create_nocodb_table, write_table_id_to_registry


class TestRebuildNocobdTable(unittest.TestCase):
    @patch("scripts.nocodb_sync.upsert_feature")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.get")
    def test_deletes_all_then_reinserts(self, mock_get, mock_delete, mock_upsert):
        mock_get.return_value.json.return_value = {
            "list": [{"Id": 1}, {"Id": 2}]
        }
        items = [("idea", "Feature A"), ("done", "Feature B")]
        rebuild_nocodb_table("tbl_abc123", items)

        delete_body = mock_delete.call_args[1]["json"]
        self.assertEqual(delete_body, [{"Id": 1}, {"Id": 2}])

        self.assertEqual(mock_upsert.call_count, 2)
        mock_upsert.assert_any_call("tbl_abc123", "Feature A", "idea")
        mock_upsert.assert_any_call("tbl_abc123", "Feature B", "done")

    @patch("scripts.nocodb_sync.upsert_feature")
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.get")
    def test_skips_delete_when_table_empty(self, mock_get, mock_delete, mock_upsert):
        mock_get.return_value.json.return_value = {"list": []}
        rebuild_nocodb_table("tbl_abc123", [("idea", "New Feature")])
        mock_delete.assert_not_called()
        mock_upsert.assert_called_once_with("tbl_abc123", "New Feature", "idea")


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
        self.assertEqual(items_arg[0], ("idea", "Feature A"))
        self.assertEqual(items_arg[1], ("done", "Feature B"))

    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="")
    @patch("scripts.nocodb_sync.rebuild_nocodb_table")
    def test_skips_when_no_table_id(self, mock_rebuild, mock_load):
        sync_rebuild("unknown-slug")
        mock_rebuild.assert_not_called()


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


if __name__ == "__main__":
    unittest.main()

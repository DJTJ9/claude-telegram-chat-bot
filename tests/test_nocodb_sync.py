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


class TestUpsertFeaturePosition(unittest.TestCase):
    @patch("scripts.nocodb_sync.find_row", return_value=None)
    @patch("scripts.nocodb_sync.requests.post")
    def test_includes_position_in_payload(self, mock_post, mock_find):
        upsert_feature("tbl_abc123", "Feature A", "idea", position=3)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["Position"], 3)

    @patch("scripts.nocodb_sync.find_row", return_value=None)
    @patch("scripts.nocodb_sync.requests.post")
    def test_omits_position_when_none(self, mock_post, mock_find):
        upsert_feature("tbl_abc123", "Feature A", "idea")
        payload = mock_post.call_args[1]["json"]
        self.assertNotIn("Position", payload)


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
from scripts.nocodb_create_table import create_nocodb_table, write_table_id_to_registry


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
        self.assertIn("Status", titles)
        self.assertIn("Position", titles)
        self.assertIn("Notiz", titles)


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

import json, os, sys, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("NOCODB_API_URL", "http://localhost:8090")
os.environ.setdefault("NOCODB_API_TOKEN", "test_token")
os.environ.setdefault("NOCODB_BASE_ID", "test_base")

from scripts.nocodb_sync import (
    _headers, _table_url, load_nocodb_table_id, find_row, upsert_feature,
    sync_dev_to_nocodb, sync_nocodb_to_dev, _get_all_rows, _open_order,
    _OPEN_ORDER_BASE, _DONE_ORDER_BASE,
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
    @patch("scripts.nocodb_sync.requests.patch")
    @patch("scripts.nocodb_sync.find_row", return_value=None)
    @patch("scripts.nocodb_sync.requests.post")
    def test_creates_row_when_not_found(self, mock_post, mock_find, mock_patch):
        mock_post.return_value.json.return_value = {"Id": 7}
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


class TestSyncDevToNocodb(unittest.TestCase):
    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    @patch("scripts.nocodb_sync.upsert_feature")
    def test_calls_upsert_with_correct_args(self, mock_upsert, mock_load):
        sync_dev_to_nocodb("test-proj", "My Feature", "planned", spec="specs/foo.md")
        mock_upsert.assert_called_once_with(
            "tbl_abc123", "My Feature", "planned", spec="specs/foo.md", plan="", notiz=None)

    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="")
    @patch("scripts.nocodb_sync.upsert_feature")
    def test_skips_when_no_table_id(self, mock_upsert, mock_load):
        sync_dev_to_nocodb("unknown", "Feature", "idea")
        mock_upsert.assert_not_called()


import tempfile
from scripts.nocodb_sync import regenerate_status_roadmap
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


class TestUpsertFeatureInPlace(unittest.TestCase):
    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    @patch("scripts.nocodb_sync.requests.patch")
    @patch("scripts.nocodb_sync.find_row", return_value={"Id": 5})
    def test_done_patches_in_place_and_moves_to_end(self, mock_find, mock_patch, mock_post, mock_delete):
        upsert_feature("tbl_abc123", "Feature A", "done")
        mock_delete.assert_not_called()
        mock_post.assert_not_called()
        body = mock_patch.call_args[1]["json"]
        self.assertEqual(body[0]["Id"], 5)
        self.assertEqual(body[0]["Status"], "done")
        # done → nc_order groß (Basis + Id) → Tabellenende
        self.assertEqual(body[0]["nc_order"], "1000005")

    @patch("scripts.nocodb_sync.requests.delete")
    @patch("scripts.nocodb_sync.requests.post")
    @patch("scripts.nocodb_sync.requests.patch")
    @patch("scripts.nocodb_sync.find_row", return_value={"Id": 5})
    def test_non_done_status_change_does_not_reorder(self, mock_find, mock_patch, mock_post, mock_delete):
        upsert_feature("tbl_abc123", "Feature A", "planned")
        mock_delete.assert_not_called()
        mock_post.assert_not_called()
        body = mock_patch.call_args[1]["json"]
        self.assertEqual(body[0]["Status"], "planned")
        self.assertNotIn("nc_order", body[0])

    @patch("scripts.nocodb_sync.requests.patch")
    @patch("scripts.nocodb_sync.requests.post")
    @patch("scripts.nocodb_sync.find_row", return_value=None)
    def test_new_row_posts_then_patches_nc_order_before_done(self, mock_find, mock_post, mock_patch):
        mock_post.return_value.json.return_value = {"Id": 34}
        upsert_feature("tbl_abc123", "New Idea", "idea")
        post_body = mock_post.call_args[1]["json"]
        self.assertEqual(post_body["Name"], "New Idea")
        self.assertNotIn("nc_order", post_body)
        patch_body = mock_patch.call_args[1]["json"]
        self.assertEqual(patch_body[0]["Id"], 34)
        self.assertEqual(patch_body[0]["nc_order"], _open_order(34))
        # Neue Idee landet OBEN im offenen Block, aber IMMER positiv und
        # unter allen bestehenden offenen Rows (>= _OPEN_ORDER_BASE) → ganz oben.
        order = float(patch_body[0]["nc_order"])
        self.assertGreater(order, 0)
        self.assertLess(order, _OPEN_ORDER_BASE)

    def test_open_order_strictly_decreases_with_id(self):
        # Größere Id (= neuere Row) muss strikt KLEINER sortieren → weiter oben,
        # an den Anfang des offenen Blocks. Immer positiv, unter _OPEN_ORDER_BASE.
        orders = [float(_open_order(i)) for i in (1, 34, 35, 41, 45, 46)]
        self.assertEqual(orders, sorted(orders, reverse=True))
        self.assertEqual(len(set(orders)), len(orders))
        self.assertTrue(all(0 < o < _OPEN_ORDER_BASE for o in orders))


class TestSyncDevToNocodbInPlace(unittest.TestCase):
    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    @patch("scripts.nocodb_sync.upsert_feature")
    def test_calls_upsert_without_position_args(self, mock_upsert, mock_load):
        sync_dev_to_nocodb("test-proj", "My Feature", "planned", spec="specs/foo.md")
        mock_upsert.assert_called_once_with(
            "tbl_abc123", "My Feature", "planned", spec="specs/foo.md", plan="", notiz=None)


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


import subprocess

class TestRemovedFlagsAndFunctions(unittest.TestCase):
    def test_removed_functions_not_importable(self):
        import scripts.nocodb_sync as m
        for fn in ("_insert_row_at_top", "_insert_row_after", "_move_row_to_top",
                   "_move_row_to_end", "rebuild_nocodb_table", "sync_rebuild",
                   "_reorder_status_roadmap"):
            self.assertFalse(hasattr(m, fn), f"{fn} should be removed")

    def test_help_has_no_removed_flags(self):
        out = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "scripts" / "nocodb_sync.py"), "--help"],
            capture_output=True, text=True).stdout
        for flag in ("--insert-position", "--after", "--move-to-top", "--move-to-end", "--rebuild"):
            self.assertNotIn(flag, out, f"{flag} should be gone")


class TestUpsertFeatureNotiz(unittest.TestCase):
    @patch("scripts.nocodb_sync.requests.patch")
    @patch("scripts.nocodb_sync.find_row", return_value={"Id": 5})
    def test_notiz_is_written(self, mock_find, mock_patch):
        upsert_feature("tbl_abc123", "Feature A", "idea", notiz="Kontext hier")
        body = mock_patch.call_args[1]["json"]
        self.assertEqual(body[0]["Notiz"], "Kontext hier")

    @patch("scripts.nocodb_sync.requests.patch")
    @patch("scripts.nocodb_sync.find_row", return_value={"Id": 5})
    def test_without_notiz_field_is_untouched(self, mock_find, mock_patch):
        upsert_feature("tbl_abc123", "Feature A", "planned")
        body = mock_patch.call_args[1]["json"]
        self.assertNotIn("Notiz", body[0])

    @patch("scripts.nocodb_sync.requests.patch")
    @patch("scripts.nocodb_sync.find_row", return_value={"Id": 5})
    def test_empty_notiz_clears_field(self, mock_find, mock_patch):
        upsert_feature("tbl_abc123", "Feature A", "idea", notiz="")
        body = mock_patch.call_args[1]["json"]
        self.assertEqual(body[0]["Notiz"], "")

    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    @patch("scripts.nocodb_sync.upsert_feature")
    def test_sync_passes_notiz_through(self, mock_upsert, mock_load):
        sync_dev_to_nocodb("test-proj", "My Feature", "idea", notiz="Kontext")
        self.assertEqual(mock_upsert.call_args[1]["notiz"], "Kontext")

    def test_help_has_notiz_flag(self):
        out = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "scripts" / "nocodb_sync.py"),
             "--help"], capture_output=True, text=True).stdout
        self.assertIn("--notiz", out)


from scripts.nocodb_sync import merge_status_roadmap


class TestMergeStatusRoadmap(unittest.TestCase):
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
            merge_status_roadmap(p, entries)
            return p.read_text()

    def test_nocodb_entries_sorted_by_order(self):
        text = self._run([
            {"name": "Feature B", "status": "done"},
            {"name": "Feature A", "status": "discussed"},
        ])
        lines = [l for l in text.splitlines() if l.startswith("- [")]
        self.assertEqual(lines[:2], [
            "- [done]".ljust(14) + "Feature B",
            "- [discussed]".ljust(14) + "Feature A",
        ])

    def test_local_only_row_survives_at_end(self):
        text = self._run([
            {"name": "Feature A", "status": "discussed"},
            {"name": "Feature B", "status": "done"},
        ])
        lines = [l for l in text.splitlines() if l.startswith("- [")]
        self.assertEqual(lines[-1], "- [planned]".ljust(14) + "Stale Only In Status")

    def test_preserves_trailing_section(self):
        status = self.STATUS + "\n## Notes\nkeep me\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "STATUS.md"
            p.write_text(status)
            merge_status_roadmap(p, [{"name": "Feature A", "status": "idea"}])
            out = p.read_text()
        self.assertIn("## Notes", out)
        self.assertIn("keep me", out)


from scripts.nocodb_sync import reorder_vision_roadmap


class TestReorderVisionRoadmap(unittest.TestCase):
    VISION = """# VISION — Test Proj
## Was ist das Projekt?
Testprojekt.
## Roadmap
- [idea]      Feature A
- ✅ Feature B   ← implementiert 2026-06-01
- [planned]   Feature C
"""

    def _run(self, entries):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "VISION.md"
            p.write_text(self.VISION)
            reorder_vision_roadmap(p, entries)
            return p.read_text()

    def test_done_line_stays_position_fixed(self):
        text = self._run([
            {"name": "Feature C", "status": "planned"},
            {"name": "Feature A", "status": "discussed"},
        ])
        lines = [l for l in text.splitlines() if l.startswith("- ")]
        self.assertEqual(lines[1], "- ✅ Feature B   ← implementiert 2026-06-01")

    def test_open_lines_reordered_by_nocodb_order(self):
        text = self._run([
            {"name": "Feature C", "status": "planned"},
            {"name": "Feature A", "status": "discussed"},
        ])
        lines = [l for l in text.splitlines() if l.startswith("- ")]
        open_lines = [l for l in lines if not l.startswith("- ✅")]
        self.assertEqual(open_lines, [
            "- [planned]".ljust(14) + "Feature C",
            "- [discussed]".ljust(14) + "Feature A",
        ])

    def test_missing_open_feature_appended_at_block_end(self):
        text = self._run([
            {"name": "Feature A", "status": "idea"},
            {"name": "Feature C", "status": "planned"},
            {"name": "Brand New Idea", "status": "idea"},
        ])
        lines = [l for l in text.splitlines() if l.startswith("- ")]
        self.assertEqual(lines[-1], "- [idea]".ljust(14) + "Brand New Idea")


from scripts.nocodb_sync import sync_nocodb_reorder


class TestSyncNocodbReorder(unittest.TestCase):
    @patch("scripts.nocodb_sync.reorder_vision_roadmap")
    @patch("scripts.nocodb_sync.merge_status_roadmap")
    @patch("scripts.nocodb_sync._update_status_active")
    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    def test_active_set_unconditional(self, mock_load, mock_rows, mock_active,
                                       mock_merge, mock_reorder):
        mock_rows.return_value = [
            {"Name": "Feature A", "Status": "done"},
            {"Name": "Feature B", "Status": "planned"},
        ]
        sync_nocodb_reorder("test-proj")
        mock_active.assert_called_once()
        args, kwargs = mock_active.call_args
        self.assertEqual(args[1], "Feature B")
        self.assertEqual(kwargs.get("conditional"), False)

    @patch("scripts.nocodb_sync.reorder_vision_roadmap")
    @patch("scripts.nocodb_sync.merge_status_roadmap")
    @patch("scripts.nocodb_sync._update_status_active")
    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="tbl_abc123")
    def test_calls_merge_and_reorder_with_same_entries(self, mock_load, mock_rows,
                                                        mock_active, mock_merge, mock_reorder):
        mock_rows.return_value = [{"Name": "Feature A", "Status": "idea"}]
        sync_nocodb_reorder("test-proj")
        mock_merge.assert_called_once()
        mock_reorder.assert_called_once()
        merge_entries = mock_merge.call_args[0][1]
        reorder_entries = mock_reorder.call_args[0][1]
        self.assertEqual(merge_entries, reorder_entries)
        self.assertEqual(merge_entries, [{"name": "Feature A", "status": "idea"}])

    @patch("scripts.nocodb_sync._get_all_rows")
    @patch("scripts.nocodb_sync.load_nocodb_table_id", return_value="")
    def test_skips_when_no_table_id(self, mock_load, mock_rows):
        sync_nocodb_reorder("unknown")
        mock_rows.assert_not_called()

    def test_help_has_nocodb_reorder_direction(self):
        out = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "scripts" / "nocodb_sync.py"),
             "--help"], capture_output=True, text=True).stdout
        self.assertIn("nocodb-reorder", out)

    def test_nocodb_reorder_requires_slug(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "scripts" / "nocodb_sync.py"),
             "--direction", "nocodb-reorder"],
            capture_output=True, text=True,
            env={**os.environ, "NOCODB_API_URL": "http://localhost:8090"})
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.setup_notion_structure import SUB_PAGES, create_sub_pages, find_organizer_page


class TestFindOrganizerPage(unittest.TestCase):
    def test_returns_page_id_from_claude_response(self):
        with patch("scripts.setup_notion_structure.run_claude",
                   return_value='{"page_id": "abc00000000000000000000000000001"}') as mock:
            result = find_organizer_page()
        self.assertEqual(result, "abc00000000000000000000000000001")
        self.assertIn("Organizer", mock.call_args[0][0])

    def test_raises_on_invalid_json(self):
        with patch("scripts.setup_notion_structure.run_claude", return_value="kein JSON"):
            with self.assertRaises(Exception):
                find_organizer_page()


class TestCreateSubPages(unittest.TestCase):
    def _mock_responses(self):
        return [json.dumps({"page_id": f"page{i:028d}"}) for i in range(len(SUB_PAGES))]

    def test_creates_one_call_per_sub_page(self):
        with patch("scripts.setup_notion_structure.run_claude", side_effect=self._mock_responses()) as mock:
            create_sub_pages("parent0000000000000000000000001")
        self.assertEqual(mock.call_count, len(SUB_PAGES))

    def test_prompt_contains_parent_page_id(self):
        with patch("scripts.setup_notion_structure.run_claude", side_effect=self._mock_responses()) as mock:
            create_sub_pages("parent0000000000000000000000001")
        for c in mock.call_args_list:
            self.assertIn("parent0000000000000000000000001", c[0][0])

    def test_returns_all_slugs(self):
        expected_slugs = {slug for _, slug in SUB_PAGES}
        with patch("scripts.setup_notion_structure.run_claude", side_effect=self._mock_responses()):
            result = create_sub_pages("parent0000000000000000000000001")
        self.assertEqual(set(result.keys()), expected_slugs)

    def test_prompt_contains_page_title(self):
        with patch("scripts.setup_notion_structure.run_claude", side_effect=self._mock_responses()) as mock:
            create_sub_pages("parent0000000000000000000000001")
        first_prompt = mock.call_args_list[0][0][0]
        self.assertIn(SUB_PAGES[0][0], first_prompt)


from scripts.setup_notion_structure import create_databases, DB_DEFINITIONS


class TestCreateDatabases(unittest.TestCase):
    def _sub_page_ids(self):
        slugs = [slug for _, slug in SUB_PAGES]
        return {slug: f"page{i:028d}" for i, slug in enumerate(slugs)}

    def _mock_db_responses(self):
        return [json.dumps({"database_id": f"db{i:029d}"}) for i in range(len(DB_DEFINITIONS))]

    def test_creates_one_db_per_definition(self):
        with patch("scripts.setup_notion_structure.run_claude", side_effect=self._mock_db_responses()) as mock:
            create_databases(self._sub_page_ids())
        self.assertEqual(mock.call_count, len(DB_DEFINITIONS))

    def test_prompt_contains_parent_sub_page_id(self):
        sub_ids = self._sub_page_ids()
        with patch("scripts.setup_notion_structure.run_claude", side_effect=self._mock_db_responses()) as mock:
            create_databases(sub_ids)
        first_db_slug = DB_DEFINITIONS[0]["sub_page"]
        first_prompt = mock.call_args_list[0][0][0]
        self.assertIn(sub_ids[first_db_slug], first_prompt)

    def test_returns_all_db_names(self):
        with patch("scripts.setup_notion_structure.run_claude", side_effect=self._mock_db_responses()):
            result = create_databases(self._sub_page_ids())
        expected = {d["name"] for d in DB_DEFINITIONS}
        self.assertEqual(set(result.keys()), expected)

    def test_tasks_db_prompt_contains_zyklus_property(self):
        with patch("scripts.setup_notion_structure.run_claude", side_effect=self._mock_db_responses()) as mock:
            create_databases(self._sub_page_ids())
        tasks_call = next(c for c in mock.call_args_list if "Zyklus" in c[0][0])
        self.assertIn("Zyklus", tasks_call[0][0])


from scripts.setup_notion_structure import migrate_data


class TestMigrateData(unittest.TestCase):
    def _new_db_ids(self):
        return {
            "tasks": "newtasksdb000000000000000000001",
            "sport-challenges": "newsportdb000000000000000000001",
            "archiv": "newarchivdb000000000000000000001",
        }

    def test_runs_three_migrations(self):
        with patch("scripts.setup_notion_structure.run_claude", return_value="3 Einträge migriert.") as mock:
            migrate_data(self._new_db_ids())
        self.assertEqual(mock.call_count, 3)

    def test_tasks_prompt_references_old_tagesorganizer_id(self):
        with patch("scripts.setup_notion_structure.run_claude", return_value="OK") as mock:
            migrate_data(self._new_db_ids())
        prompts = [c[0][0] for c in mock.call_args_list]
        tasks_prompt = next(p for p in prompts if "c9d2abbe" in p)
        self.assertIn("newtasksdb000000000000000000001", tasks_prompt)

    def test_sport_prompt_references_old_sport_id(self):
        with patch("scripts.setup_notion_structure.run_claude", return_value="OK") as mock:
            migrate_data(self._new_db_ids())
        prompts = [c[0][0] for c in mock.call_args_list]
        sport_prompt = next(p for p in prompts if "fd7c0b6b" in p)
        self.assertIn("newsportdb000000000000000000001", sport_prompt)

    def test_archiv_prompt_references_old_archiv_id(self):
        with patch("scripts.setup_notion_structure.run_claude", return_value="OK") as mock:
            migrate_data(self._new_db_ids())
        prompts = [c[0][0] for c in mock.call_args_list]
        archiv_prompt = next(p for p in prompts if "abb5abd8" in p)
        self.assertIn("newarchivdb000000000000000000001", archiv_prompt)


if __name__ == "__main__":
    unittest.main()

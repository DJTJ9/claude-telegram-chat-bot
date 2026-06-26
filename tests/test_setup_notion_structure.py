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


if __name__ == "__main__":
    unittest.main()

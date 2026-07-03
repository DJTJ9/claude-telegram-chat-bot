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
os.environ.setdefault("NOCODB_FOCUS_TABLE_ID", "tbl_focus")

from core.nocodb_direct import (
    mark_done, reschedule, add_idea, mark_sport_done,
    _habit_due_today, fetch_habits_due,
    fetch_project_features, set_focus_project, get_focus_project,
    fetch_project_bilanz, fetch_abend_data,
    instantiate_recurring_tasks, promote_backlog_item,
    fetch_open_tasks, update_task,
)


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


class TestFetchBacklogItems(unittest.TestCase):
    @patch("core.nocodb_direct.requests.get")
    def test_returns_sorted_list(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "list": [
                {"Id": 1, "Name": "Task A", "Priorität": "Niedrig"},
                {"Id": 2, "Name": "Task B", "Priorität": "Hoch"},
            ]
        }
        from core.nocodb_direct import fetch_backlog_items
        items = fetch_backlog_items()
        self.assertEqual(items[0]["name"], "Task B")
        self.assertEqual(items[0]["id"], "2")

    @patch("core.nocodb_direct.requests.get")
    def test_returns_empty_on_error(self, mock_get):
        mock_get.return_value.status_code = 500
        from core.nocodb_direct import fetch_backlog_items
        self.assertEqual(fetch_backlog_items(), [])


class TestCreateBacklogItem(unittest.TestCase):
    @patch("core.nocodb_direct.requests.post")
    def test_posts_to_backlog_table(self, mock_post):
        mock_post.return_value.status_code = 200
        from core.nocodb_direct import create_backlog_item
        result = create_backlog_item("Neue Aufgabe", "Mittel")
        self.assertTrue(result)
        url = mock_post.call_args[0][0]
        self.assertIn("tbl_backlog", url)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["Name"], "Neue Aufgabe")
        self.assertEqual(payload["Status"], "Offen")
        self.assertEqual(payload["Priorität"], "Mittel")


class TestHabitDueToday(unittest.TestCase):
    def test_taeglich_always_due(self):
        self.assertTrue(_habit_due_today("täglich", weekday=2))

    def test_specific_weekday_matches(self):
        self.assertTrue(_habit_due_today("montags", weekday=0))

    def test_specific_weekday_does_not_match_other_day(self):
        self.assertFalse(_habit_due_today("montags", weekday=1))

    def test_wochentags_true_on_weekday(self):
        self.assertTrue(_habit_due_today("wochentags", weekday=3))

    def test_wochentags_false_on_weekend(self):
        self.assertFalse(_habit_due_today("wochentags", weekday=5))

    def test_wochenends_true_on_saturday(self):
        self.assertTrue(_habit_due_today("wochenends", weekday=5))

    def test_unknown_format_defaults_to_due(self):
        self.assertTrue(_habit_due_today("alle 3 Tage", weekday=0))

    def test_empty_zyklus_defaults_to_due(self):
        self.assertTrue(_habit_due_today("", weekday=0))


class TestFetchHabitsDue(unittest.TestCase):
    @patch("core.nocodb_direct.requests.get")
    def test_filters_done_and_keeps_due(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Name": "Laufen", "Kategorie": "Gesundheit", "Zyklus": "täglich", "Status": "Not Started"},
            {"Id": 2, "Name": "Meditieren", "Kategorie": "Gesundheit", "Zyklus": "montags", "Status": "Not Started"},
            {"Id": 3, "Name": "Lesen", "Kategorie": "Lernen", "Zyklus": "täglich", "Status": "Done"},
        ]}
        result = fetch_habits_due("2026-07-06")  # Montag
        names = [h["name"] for h in result]
        self.assertEqual(names, ["Laufen", "Meditieren"])

    @patch("core.nocodb_direct.requests.get")
    def test_excludes_habit_not_due_today(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Name": "Meditieren", "Kategorie": "Gesundheit", "Zyklus": "montags", "Status": "Not Started"},
        ]}
        result = fetch_habits_due("2026-07-07")  # Dienstag
        self.assertEqual(result, [])


class TestFetchProjectFeatures(unittest.TestCase):
    @patch("core.nocodb_direct.requests.get")
    def test_returns_top_5_non_done_names_in_order(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Name": "Feature A", "Status": "idea"},
            {"Id": 2, "Name": "Feature B", "Status": "done"},
            {"Id": 3, "Name": "Feature C", "Status": "planned"},
            {"Id": 4, "Name": "Feature D", "Status": "discussed"},
            {"Id": 5, "Name": "Feature E", "Status": "idea"},
            {"Id": 6, "Name": "Feature F", "Status": "idea"},
        ]}
        result = fetch_project_features("tbl_proj")
        self.assertEqual(result, ["Feature A", "Feature C", "Feature D", "Feature E", "Feature F"])

    def test_returns_empty_list_without_table_id(self):
        self.assertEqual(fetch_project_features(""), [])


class TestFocusProject(unittest.TestCase):
    @patch("core.nocodb_direct.requests.post")
    @patch("core.nocodb_direct.requests.get")
    def test_set_focus_project_creates_row_when_none_exists(self, mock_get, mock_post):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": []}
        mock_post.return_value.status_code = 200
        result = set_focus_project("shopping-navigator")
        self.assertTrue(result)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["Slug"], "shopping-navigator")

    @patch("core.nocodb_direct.requests.patch")
    @patch("core.nocodb_direct.requests.get")
    def test_set_focus_project_patches_existing_row(self, mock_get, mock_patch):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [{"Id": 9, "Slug": "old-slug"}]}
        mock_patch.return_value.status_code = 200
        result = set_focus_project("new-slug")
        self.assertTrue(result)
        payload = mock_patch.call_args[1]["json"]
        self.assertEqual(payload[0]["Id"], 9)
        self.assertEqual(payload[0]["Slug"], "new-slug")

    @patch("core.nocodb_direct.requests.get")
    def test_get_focus_project_returns_slug(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [{"Id": 9, "Slug": "shopping-navigator"}]}
        self.assertEqual(get_focus_project(), "shopping-navigator")

    @patch("core.nocodb_direct.requests.get")
    def test_get_focus_project_returns_none_when_empty(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": []}
        self.assertIsNone(get_focus_project())


class TestFetchProjectBilanz(unittest.TestCase):
    @patch("core.nocodb_direct.requests.get")
    def test_counts_done_and_open_rows(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Name": "Feature A", "Status": "done"},
            {"Id": 2, "Name": "Feature B", "Status": "idea"},
            {"Id": 3, "Name": "Feature C", "Status": "planned"},
            {"Id": 4, "Name": "Feature D", "Status": "done"},
        ]}
        result = fetch_project_bilanz("tbl_proj")
        self.assertEqual(result, {"done": 2, "open": 2})

    def test_returns_zero_counts_without_table_id(self):
        self.assertEqual(fetch_project_bilanz(""), {"done": 0, "open": 0})


class TestFetchAbendDataBilanzHabits(unittest.TestCase):
    @patch("core.nocodb_direct.fetch_project_bilanz")
    @patch("core.nocodb_direct.load_registry")
    @patch("core.nocodb_direct.get_focus_project")
    @patch("core.nocodb_direct.fetch_habits_due")
    @patch("core.nocodb_direct.requests.get")
    def test_populates_missed_habits_and_projekt_bilanz(
        self, mock_get, mock_habits_due, mock_focus, mock_registry, mock_bilanz
    ):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": []}
        mock_habits_due.return_value = [{"name": "Laufen", "id": "3"}]
        mock_focus.return_value = "shopping-navigator"
        mock_registry.return_value = [
            {"slug": "shopping-navigator", "name": "Shopping Navigator", "nocodb_table_id": "tbl_proj"}
        ]
        mock_bilanz.return_value = {"done": 2, "open": 1}

        result = fetch_abend_data("2026-07-06")

        self.assertEqual(result["missed_habits"], [{"name": "Laufen", "id": "3"}])
        self.assertEqual(result["projekt_bilanz"],
                         [{"name": "Shopping Navigator", "done": 2, "open": 1}])
        mock_bilanz.assert_called_once_with("tbl_proj")

    @patch("core.nocodb_direct.load_registry")
    @patch("core.nocodb_direct.get_focus_project")
    @patch("core.nocodb_direct.fetch_habits_due")
    @patch("core.nocodb_direct.requests.get")
    def test_empty_projekt_bilanz_when_no_focus_project(
        self, mock_get, mock_habits_due, mock_focus, mock_registry
    ):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": []}
        mock_habits_due.return_value = []
        mock_focus.return_value = None

        result = fetch_abend_data("2026-07-06")

        self.assertEqual(result["projekt_bilanz"], [])
        mock_registry.assert_not_called()

    @patch("core.nocodb_direct.load_registry")
    @patch("core.nocodb_direct.get_focus_project")
    @patch("core.nocodb_direct.fetch_habits_due")
    @patch("core.nocodb_direct.requests.get")
    def test_empty_projekt_bilanz_when_focus_project_has_no_table_id(
        self, mock_get, mock_habits_due, mock_focus, mock_registry
    ):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": []}
        mock_habits_due.return_value = []
        mock_focus.return_value = "dart-app"
        mock_registry.return_value = [{"slug": "dart-app", "name": "DartApp"}]

        result = fetch_abend_data("2026-07-06")

        self.assertEqual(result["projekt_bilanz"], [])


class TestInstantiateRecurringTasks(unittest.TestCase):
    @patch("core.nocodb_direct.create_task")
    @patch("core.nocodb_direct.requests.get")
    def test_creates_instance_for_due_template_without_existing_instance(self, mock_get, mock_create):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Title": "Sport", "Zyklus": "täglich", "Priorität": "Mittel", "Datum": None, "Status": "Not started"},
        ]}
        mock_create.return_value = True
        result = instantiate_recurring_tasks("2026-07-06")  # Montag
        self.assertEqual(result, ["Sport"])
        mock_create.assert_called_once_with("Sport", "2026-07-06", "Mittel")

    @patch("core.nocodb_direct.create_task")
    @patch("core.nocodb_direct.requests.get")
    def test_skips_template_when_instance_already_exists_today(self, mock_get, mock_create):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Title": "Sport", "Zyklus": "täglich", "Priorität": "Mittel", "Datum": None, "Status": "Not started"},
            {"Id": 2, "Title": "Sport", "Zyklus": None, "Priorität": "Mittel", "Datum": "2026-07-06", "Status": "Not started"},
        ]}
        result = instantiate_recurring_tasks("2026-07-06")
        self.assertEqual(result, [])
        mock_create.assert_not_called()

    @patch("core.nocodb_direct.create_task")
    @patch("core.nocodb_direct.requests.get")
    def test_skips_template_not_due_today(self, mock_get, mock_create):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Title": "Meditieren", "Zyklus": "montags", "Priorität": "Niedrig", "Datum": None, "Status": "Not started"},
        ]}
        result = instantiate_recurring_tasks("2026-07-07")  # Dienstag
        self.assertEqual(result, [])
        mock_create.assert_not_called()

    @patch("core.nocodb_direct.requests.get")
    def test_returns_empty_list_without_templates(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Title": "Einkaufen", "Zyklus": None, "Priorität": "Niedrig", "Datum": "2026-07-06", "Status": "Not started"},
        ]}
        self.assertEqual(instantiate_recurring_tasks("2026-07-06"), [])


class TestPromoteBacklogItem(unittest.TestCase):
    @patch("core.nocodb_direct.archive_backlog_item")
    @patch("core.nocodb_direct.create_task")
    @patch("core.nocodb_direct.requests.get")
    def test_creates_task_and_archives_on_success(self, mock_get, mock_create, mock_archive):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"Id": 7, "Name": "Umzugskartons besorgen", "Priorität": "Mittel"}
        mock_create.return_value = True
        mock_archive.return_value = True
        result = promote_backlog_item(7, "2026-07-06")
        self.assertTrue(result)
        mock_create.assert_called_once_with("Umzugskartons besorgen", "2026-07-06", "Mittel")
        mock_archive.assert_called_once_with(7)

    @patch("core.nocodb_direct.archive_backlog_item")
    @patch("core.nocodb_direct.create_task")
    @patch("core.nocodb_direct.requests.get")
    def test_defaults_to_niedrig_when_prio_missing(self, mock_get, mock_create, mock_archive):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"Id": 8, "Name": "Ohne Prio"}
        mock_create.return_value = True
        mock_archive.return_value = True
        promote_backlog_item(8, "2026-07-06")
        mock_create.assert_called_once_with("Ohne Prio", "2026-07-06", "Niedrig")

    @patch("core.nocodb_direct.requests.get")
    def test_returns_false_when_row_not_found(self, mock_get):
        mock_get.return_value.status_code = 404
        self.assertFalse(promote_backlog_item(999, "2026-07-06"))

    @patch("core.nocodb_direct.archive_backlog_item")
    @patch("core.nocodb_direct.create_task")
    @patch("core.nocodb_direct.requests.get")
    def test_returns_false_when_create_task_fails(self, mock_get, mock_create, mock_archive):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"Id": 7, "Name": "X", "Priorität": "Hoch"}
        mock_create.return_value = False
        result = promote_backlog_item(7, "2026-07-06")
        self.assertFalse(result)
        mock_archive.assert_not_called()


class TestFetchOpenTasks(unittest.TestCase):
    @patch("core.nocodb_direct.requests.get")
    def test_returns_open_tasks_mapped(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": [
            {"Id": 1, "Title": "Task A", "Datum": "2026-07-05", "Priorität": "Hoch"},
            {"Id": 2, "Title": "Task B", "Datum": None, "Priorität": "Niedrig"},
        ]}
        result = fetch_open_tasks()
        self.assertEqual(result, [
            {"id": "1", "name": "Task A", "datum": "2026-07-05", "prio": "Hoch"},
            {"id": "2", "name": "Task B", "datum": None, "prio": "Niedrig"},
        ])

    @patch("core.nocodb_direct.requests.get")
    def test_filters_status_not_done(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"list": []}
        fetch_open_tasks()
        params = mock_get.call_args[1]["params"]
        self.assertIn("neq", params["where"])
        self.assertIn("Done", params["where"])

    @patch("core.nocodb_direct.requests.get")
    def test_error_status_returns_empty_list(self, mock_get):
        mock_get.return_value.status_code = 500
        self.assertEqual(fetch_open_tasks(), [])


class TestUpdateTask(unittest.TestCase):
    @patch("core.nocodb_direct.requests.patch")
    def test_patches_only_given_field(self, mock_patch):
        mock_patch.return_value.status_code = 200
        result = update_task(9, title="Neuer Name")
        self.assertTrue(result)
        payload = mock_patch.call_args[1]["json"]
        self.assertEqual(payload[0], {"Id": 9, "Title": "Neuer Name"})

    @patch("core.nocodb_direct.requests.patch")
    def test_patches_all_fields(self, mock_patch):
        mock_patch.return_value.status_code = 200
        update_task(9, title="X", datum="2026-07-10", prio="Hoch")
        payload = mock_patch.call_args[1]["json"]
        self.assertEqual(payload[0], {"Id": 9, "Title": "X", "Datum": "2026-07-10", "Priorität": "Hoch"})

    def test_no_fields_returns_true_without_request(self):
        self.assertTrue(update_task(9))


if __name__ == "__main__":
    unittest.main()

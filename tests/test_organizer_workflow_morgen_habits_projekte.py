"""Source inspection tests for Workflow Morgen: Habits + Projekte-Sektionen."""

import unittest


def _src():
    with open("bots/organizer.py", encoding="utf-8") as f:
        return f.read()


class TestHabitMessageFixed(unittest.TestCase):
    def test_send_habit_message_uses_zyklus_field(self):
        src = _src()
        idx = src.index("def _send_habit_message(")
        block = src[idx:idx + 400]
        self.assertIn("habit['zyklus']", block)
        self.assertNotIn("interval", block)

    def test_habits_header_in_moin_messages(self):
        self.assertIn("🔁 Fällig heute", _src())

    def test_dead_proj_tasks_block_removed(self):
        self.assertNotIn("🏗️ Projekt-Tasks heute", _src())


class TestHabitDoneCallbackUsesNocodb(unittest.TestCase):
    def test_habit_done_handler_calls_mark_habit_done(self):
        src = _src()
        idx = src.index('data.startswith("habit_done:")')
        block = src[idx:idx + 400]
        self.assertIn("nocodb_direct.mark_habit_done(int(pid))", block)

    def test_habit_done_no_longer_uses_run_claude(self):
        src = _src()
        idx = src.index('data.startswith("habit_done:")')
        next_elif = src.index("elif data.startswith(", idx + 1)
        block = src[idx:next_elif]
        self.assertNotIn("run_claude(", block)
        self.assertNotIn("HABIT_DONE_SYSTEM_PROMPT", block)

    def test_habit_done_system_prompt_constant_removed(self):
        self.assertNotIn("HABIT_DONE_SYSTEM_PROMPT =", _src())


class TestSportChallengeHeader(unittest.TestCase):
    def test_sport_header_present(self):
        src = _src()
        idx = src.index("def _send_habits_sport_message(")
        end_idx = src.index("\n\n\n", idx)
        block = src[idx:end_idx]
        self.assertIn("🔁 Sport Challenge", block)


class TestProjectFeaturesSection(unittest.TestCase):
    def test_send_project_features_defined(self):
        self.assertIn("def _send_project_features(", _src())

    def test_send_project_features_uses_focus_and_fetch(self):
        src = _src()
        idx = src.index("def _send_project_features(")
        block = src[idx:idx + 700]
        self.assertIn("nocodb_direct.get_focus_project()", block)
        self.assertIn("nocodb_direct.fetch_project_features(", block)
        self.assertIn("🚀", block)

    def test_project_features_called_after_sport_in_morgen(self):
        src = _src()
        morgen_idx = src.index('elif kind == "morgen":')
        sport_idx = src.index("_send_habits_sport_message(", morgen_idx)
        feat_idx = src.index("_send_project_features(chat_id)", morgen_idx)
        self.assertLess(sport_idx, feat_idx)


class TestFocusPickerButton(unittest.TestCase):
    def test_focus_pick_button_in_abend_messages(self):
        src = _src()
        idx = src.index("def _send_abend_messages(")
        end_idx = src.index("\n\n\n", idx)
        block = src[idx:end_idx]
        self.assertIn('"callback_data": "focus_pick"', block)
        self.assertIn("🚀 Projekt für morgen wählen", block)


class TestFocusPickCallbacks(unittest.TestCase):
    def test_focus_pick_list_handler_exists(self):
        self.assertIn('data == "focus_pick"', _src())

    def test_focus_pick_select_handler_validates_slug(self):
        src = _src()
        idx = src.index('data.startswith("focus_pick:")')
        block = src[idx:idx + 450]
        self.assertIn("valid_slugs", block)
        self.assertIn("nocodb_direct.set_focus_project(slug)", block)

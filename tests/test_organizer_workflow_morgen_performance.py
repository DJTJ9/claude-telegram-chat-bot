"""Source inspection tests for Workflow Morgen: Performance + Nachrichtenkonsolidierung."""

import unittest


def _src():
    with open("bots/organizer.py", encoding="utf-8") as f:
        return f.read()


class TestZyklenUsesNocodb(unittest.TestCase):
    def test_morgen_calls_instantiate_recurring_tasks(self):
        src = _src()
        morgen_idx = src.index('elif kind == "morgen":')
        next_elif = src.index('elif kind ==', morgen_idx + 1)
        block = src[morgen_idx:next_elif]
        self.assertIn("nocodb_direct.instantiate_recurring_tasks(today)", block)

    def test_instanz_zyklen_function_removed(self):
        self.assertNotIn("def _instanz_zyklen(", _src())

    def test_zyklen_system_prompt_removed(self):
        self.assertNotIn("ZYKLEN_INSTANZ_SYSTEM_PROMPT =", _src())


class TestMoinMessagesConsolidated(unittest.TestCase):
    def test_moin_sends_termine_and_tasks_in_one_message(self):
        src = _src()
        idx = src.index("def _send_moin_messages(")
        end_idx = src.index("\n\n\n", idx)
        block = src[idx:end_idx]
        send_calls = block.count("send_message(TOKEN, CHAT_ID")
        # genau 2: Header-Nachricht + eine konsolidierte Termine+Tasks-Nachricht (oder Fallback)
        self.assertEqual(send_calls, 2)

    def test_moin_task_buttons_use_multi_row_keyboard(self):
        src = _src()
        idx = src.index("def _send_moin_messages(")
        end_idx = src.index("\n\n\n", idx)
        block = src[idx:end_idx]
        self.assertIn("buttons.append(", block)
        self.assertIn('"inline_keyboard": buttons', block)

    def test_moin_no_longer_handles_habits(self):
        src = _src()
        idx = src.index("def _send_moin_messages(")
        end_idx = src.index("\n\n\n", idx)
        block = src[idx:end_idx]
        self.assertNotIn('data.get("habits"', block)


class TestHabitsSportMessageConsolidated(unittest.TestCase):
    def test_send_habits_sport_message_defined(self):
        self.assertIn("def _send_habits_sport_message(", _src())

    def test_habits_sport_message_uses_both_callback_prefixes(self):
        src = _src()
        idx = src.index("def _send_habits_sport_message(")
        end_idx = src.index("\n\n\n", idx)
        block = src[idx:end_idx]
        self.assertIn('"habit_done:', block)
        self.assertIn('"sport_done:', block)
        self.assertIn('"inline_keyboard": buttons', block)

    def test_send_sport_challenges_function_removed(self):
        self.assertNotIn("def _send_sport_challenges(", _src())

    def test_morgen_calls_habits_sport_message_after_moin(self):
        src = _src()
        morgen_idx = src.index('elif kind == "morgen":')
        next_elif = src.index('elif kind ==', morgen_idx + 1)
        block = src[morgen_idx:next_elif]
        moin_idx = block.index("_send_moin_messages(data)")
        habits_sport_idx = block.index("_send_habits_sport_message(")
        feat_idx = block.index("_send_project_features(chat_id)")
        self.assertLess(moin_idx, habits_sport_idx)
        self.assertLess(habits_sport_idx, feat_idx)

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

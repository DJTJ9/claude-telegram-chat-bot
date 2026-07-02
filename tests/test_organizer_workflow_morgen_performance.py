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

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

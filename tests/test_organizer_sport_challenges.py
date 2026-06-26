"""Source inspection tests for Sport-Challenges Morgen-Integration."""

import unittest


def _src():
    with open("bots/organizer.py", encoding="utf-8") as f:
        return f.read()


class TestSportChallengesPrompts(unittest.TestCase):
    def test_db_id_constant(self):
        self.assertIn('SPORT_CHALLENGES_DB_ID = "fd7c0b6b4a774a6788ead7d0a093ed42"', _src())

    def test_sport_challenges_system_prompt_defined(self):
        self.assertIn("SPORT_CHALLENGES_SYSTEM_PROMPT", _src())

    def test_sport_done_system_prompt_defined(self):
        self.assertIn("SPORT_DONE_SYSTEM_PROMPT", _src())

    def test_random_imported(self):
        self.assertIn("import random", _src())

    def test_send_sport_challenges_defined(self):
        self.assertIn("def _send_sport_challenges(", _src())

    def test_send_sport_challenges_uses_random_choice(self):
        self.assertIn("random.choice(", _src())

    def test_sport_done_callback_data(self):
        self.assertIn('"sport_done:', _src())


class TestSportDoneCallback(unittest.TestCase):
    def test_sport_done_handler_exists(self):
        self.assertIn('data.startswith("sport_done:")', _src())

    def test_sport_done_uses_sport_done_prompt(self):
        src = _src()
        sport_done_idx = src.index('data.startswith("sport_done:")')
        prompt_idx = src.index("SPORT_DONE_SYSTEM_PROMPT", sport_done_idx)
        self.assertLess(sport_done_idx, prompt_idx)

    def test_sport_done_calls_edit_message(self):
        src = _src()
        sport_done_idx = src.index('data.startswith("sport_done:")')
        edit_idx = src.index("edit_message(", sport_done_idx)
        self.assertLess(sport_done_idx, edit_idx)


class TestMorgenFlowWiring(unittest.TestCase):
    def test_send_sport_challenges_called_in_morgen(self):
        src = _src()
        morgen_idx = src.index('elif kind == "morgen":')
        sport_call_idx = src.index("_send_sport_challenges(chat_id)", morgen_idx)
        self.assertLess(morgen_idx, sport_call_idx)

    def test_sport_challenges_after_moin_messages(self):
        src = _src()
        moin_idx = src.index("_send_moin_messages(data)")
        sport_idx = src.index("_send_sport_challenges(chat_id)")
        self.assertLess(moin_idx, sport_idx)

    def test_claude_md_has_sport_challenges_section(self):
        with open("CLAUDE.md", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Sport Challenges", content)
        self.assertIn("fd7c0b6b4a774a6788ead7d0a093ed42", content)

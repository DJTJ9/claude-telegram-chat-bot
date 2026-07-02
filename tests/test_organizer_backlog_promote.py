"""Source inspection tests for Backlog-Button verbessern (Promote/Planen)."""

import unittest


def _src():
    with open("bots/organizer.py", encoding="utf-8") as f:
        return f.read()


class TestBacklogListButtons(unittest.TestCase):
    def test_backlog_list_has_promote_button(self):
        src = _src()
        idx = src.index('"callback_data": f"backlog_done:{item[\'id\']}"')
        block = src[idx:idx + 200]
        self.assertIn("backlog_promote:", block)


class TestBacklogPromoteHandler(unittest.TestCase):
    def test_backlog_promote_shows_date_buttons(self):
        src = _src()
        idx = src.index('data.startswith("backlog_promote:")')
        block = src[idx:idx + 600]
        self.assertIn("backlog_promote_d:", block)
        self.assertIn("Datum eingeben", block)

    def test_backlog_promote_d_resolves_date_key(self):
        src = _src()
        idx = src.index('data.startswith("backlog_promote_d:")')
        block = src[idx:idx + 700]
        self.assertIn("_resolve_date_key(", block)
        self.assertIn("nocodb_direct.promote_backlog_item(", block)

    def test_backlog_promote_d_freitext_sets_callback_state(self):
        src = _src()
        idx = src.index('data.startswith("backlog_promote_d:")')
        block = src[idx:idx + 700]
        self.assertIn('"backlog_promote_freitext"', block)


class TestBacklogPromoteFreitext(unittest.TestCase):
    def test_message_handler_has_freitext_branch(self):
        src = _src()
        idx = src.index('cb["action"] == "backlog_promote_freitext"')
        block = src[idx:idx + 500]
        self.assertIn("_parse_user_date(", block)
        self.assertIn("nocodb_direct.promote_backlog_item(", block)

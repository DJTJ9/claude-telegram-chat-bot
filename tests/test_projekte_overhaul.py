import pathlib, unittest

SRC = (pathlib.Path(__file__).parent.parent / "scripts" / "nocodb_sync.py").read_text()

class TestNocobdSyncBugStatus(unittest.TestCase):
    def test_bug_in_status_choices(self):
        self.assertIn('"bug"', SRC)

BRAIN_SRC = (pathlib.Path(__file__).parent.parent / "bots" / "brain.py").read_text()

class TestRelayGate(unittest.TestCase):
    def test_notifications_enabled_checked_in_relay(self):
        idx = BRAIN_SRC.index("def _check_relay_question")
        snippet = BRAIN_SRC[idx:idx+400]
        self.assertIn("notifications_enabled", snippet)

    def test_settings_read_before_pq_path(self):
        idx = BRAIN_SRC.index("def _check_relay_question")
        snippet = BRAIN_SRC[idx:idx+400]
        notify_pos = snippet.index("notifications_enabled")
        pq_pos = snippet.index("pending_question.json")
        self.assertLess(notify_pos, pq_pos)

ORG_SRC = (pathlib.Path(__file__).parent.parent / "bots" / "organizer.py").read_text()

class TestKbState(unittest.TestCase):
    def test_kb_state_global_defined(self):
        self.assertIn("_kb_state: dict", ORG_SRC)

    def test_projekte_data_global_defined(self):
        self.assertIn("_projekte_data: dict", ORG_SRC)

    def test_main_reply_kb_function(self):
        self.assertIn("def _main_reply_kb()", ORG_SRC)

    def test_projekte_reply_kb_function(self):
        self.assertIn("def _projekte_reply_kb(", ORG_SRC)

    def test_project_action_kb_function(self):
        self.assertIn("def _project_action_kb()", ORG_SRC)

    def test_notify_an_in_main_kb(self):
        idx = ORG_SRC.index("def _main_reply_kb()")
        snippet = ORG_SRC[idx:idx+300]
        self.assertIn("Notify AN", snippet)

    def test_projekte_in_main_kb(self):
        idx = ORG_SRC.index("def _main_reply_kb()")
        snippet = ORG_SRC[idx:idx+300]
        self.assertIn("📁 Projekte", snippet)

    def test_notify_handler_sets_notifications_enabled(self):
        self.assertIn('"notifications_enabled"', ORG_SRC)

    def test_projekte_button_sets_kb_state(self):
        self.assertIn('_kb_state[chat_id] = "projekte"', ORG_SRC)

    def test_projekte_state_zurück_sets_main(self):
        self.assertIn('_kb_state[chat_id] = "main"', ORG_SRC)

if __name__ == "__main__":
    unittest.main()

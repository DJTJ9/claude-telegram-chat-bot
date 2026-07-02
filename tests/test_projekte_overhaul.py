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

if __name__ == "__main__":
    unittest.main()

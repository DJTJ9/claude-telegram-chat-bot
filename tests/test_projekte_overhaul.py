import pathlib, unittest

SRC = (pathlib.Path(__file__).parent.parent / "scripts" / "nocodb_sync.py").read_text()

class TestNocobdSyncBugStatus(unittest.TestCase):
    def test_bug_in_status_choices(self):
        self.assertIn('"bug"', SRC)

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

    def test_projekte_in_main_kb(self):
        idx = ORG_SRC.index("def _main_reply_kb()")
        snippet = ORG_SRC[idx:idx+300]
        self.assertIn("📁 Projekte", snippet)

    def test_projekte_button_sets_kb_state(self):
        self.assertIn('_kb_state[chat_id] = "projekte"', ORG_SRC)

    def test_projekte_state_zurück_sets_main(self):
        self.assertIn('_kb_state[chat_id] = "main"', ORG_SRC)

class TestProjectActionState(unittest.TestCase):
    def test_send_dev_status_defined(self):
        self.assertIn("def _send_dev_status(", ORG_SRC)

    def test_dev_status_reads_status_md(self):
        idx = ORG_SRC.index("def _send_dev_status(")
        snippet = ORG_SRC[idx:idx+400]
        self.assertIn("STATUS.md", snippet)

    def test_project_state_zurück_sets_projekte(self):
        occurrences = ORG_SRC.count('_kb_state[chat_id] = "projekte"')
        self.assertGreaterEqual(occurrences, 2)

    def test_idee_starts_idea_workflow(self):
        self.assertIn('"idea_for_project:name"', ORG_SRC)

    def test_dev_status_called_in_project_state(self):
        self.assertIn("_send_dev_status(chat_id, slug)", ORG_SRC)

    def test_bug_sets_bug_capture_state(self):
        self.assertIn('_kb_state[chat_id] = f"bug_capture:{slug}"', ORG_SRC)

class TestBugCapture(unittest.TestCase):
    def test_summarize_bug_defined(self):
        self.assertIn("def _summarize_bug(", ORG_SRC)

    def test_summarize_bug_uses_groq(self):
        idx = ORG_SRC.index("def _summarize_bug(")
        snippet = ORG_SRC[idx:idx+300]
        self.assertIn("Groq", snippet)

    def test_bug_capture_state_checked(self):
        self.assertIn('startswith("bug_capture:")', ORG_SRC)

    def test_bug_capture_calls_nocodb_sync(self):
        idx = ORG_SRC.index('startswith("bug_capture:")')
        snippet = ORG_SRC[idx:idx+500]
        self.assertIn("nocodb_sync.py", snippet)

    def test_bug_capture_uses_insert_position_top(self):
        idx = ORG_SRC.index('startswith("bug_capture:")')
        snippet = ORG_SRC[idx:idx+700]
        self.assertIn("insert-position", snippet)

    def test_bug_feature_name_prefix(self):
        self.assertIn('"Bug: "', ORG_SRC)

    def test_abbrechen_returns_to_project_state(self):
        idx = ORG_SRC.index('startswith("bug_capture:")')
        snippet = ORG_SRC[idx:idx+400]
        self.assertIn("⬅️ Abbrechen", snippet)

if __name__ == "__main__":
    unittest.main()

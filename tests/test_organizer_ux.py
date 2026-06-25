"""Tests for Organizer Bot UX Overhaul — source inspection based."""


def _src():
    with open("bots/organizer.py", encoding="utf-8") as f:
        return f.read()


import unittest


class TestRoutingSkeleton(unittest.TestCase):
    def test_new_keyboard_buttons(self):
        src = _src()
        for btn in ["📋 Task", "📅 Termin", "💡 Ideen", "📚 Lern",
                    "🌅 Morgen", "🌙 Abend", "📆 Woche", "📥 Backlog", "🗂️ Projekte"]:
            self.assertIn(btn, src, f"Missing button: {btn}")

    def test_workflow_global(self):
        self.assertIn("_workflow: dict = {}", _src())

    def test_button_map(self):
        self.assertIn("BUTTON_MAP", _src())

    def test_start_workflow_defined(self):
        self.assertIn("def start_workflow(", _src())

    def test_handle_workflow_step_defined(self):
        self.assertIn("def handle_workflow_step(", _src())

    def test_routing_order_in_main(self):
        src = _src()
        wf_idx = src.index("handle_workflow_step(text, chat_id, today)")
        btn_idx = src.index("if t in BUTTON_MAP")
        self.assertLess(wf_idx, btn_idx)


class TestTaskAndLernWorkflows(unittest.TestCase):
    def test_task_steps(self):
        src = _src()
        self.assertIn('"task:name"', src)
        self.assertIn('"task:priority"', src)

    def test_task_priority_callback(self):
        self.assertIn('"task:priority:', _src())

    def test_lern_steps(self):
        src = _src()
        self.assertIn('"lern:name"', src)
        self.assertIn('"lern:kategorie"', src)
        self.assertIn('"lern:prioritaet"', src)

    def test_lern_callbacks(self):
        src = _src()
        self.assertIn('"lern:kategorie:', src)
        self.assertIn('"lern:prioritaet:', src)

    def test_abort_callback(self):
        self.assertIn('"wf:abort"', _src())


class TestTerminIdeenCallbacks(unittest.TestCase):
    def test_termin_priority_callback(self):
        self.assertIn('"termin:priority:', _src())

    def test_ideen_typ_callback(self):
        src = _src()
        self.assertIn('"ideen:typ:', src)
        self.assertIn('"ideen:typ:spieleidee"', src)

    def test_ideen_name_step_exists(self):
        self.assertIn('"ideen:name"', _src())

    def test_ideen_details_step_exists(self):
        self.assertIn('"ideen:details"', _src())


class TestMorgenDoneButtons(unittest.TestCase):
    def test_moin_uses_per_item_done_button(self):
        src = _src()
        moin_start = src.index("def _send_moin_messages(")
        moin_end = src.index("\ndef ", moin_start + 1)
        moin_body = src[moin_start:moin_end]
        self.assertIn('f"done:{pid}"', moin_body)
        self.assertIn('task["name"]', moin_body)
        self.assertNotIn("_task_buttons(pid)", moin_body)


class TestProjekteView(unittest.TestCase):
    def test_builder_defined(self):
        self.assertIn("def _build_projekte_message(", _src())

    def test_section_divider(self):
        self.assertIn("━━", _src())

    def test_standup_callback(self):
        src = _src()
        self.assertIn('data.startswith("standup:")', src)
        self.assertIn("STATUS.md", src)

    def test_projekte_in_start_workflow(self):
        src = _src()
        self.assertIn('"projekte"', src)
        self.assertIn("_build_projekte_message()", src)


class TestCleanup(unittest.TestCase):
    def test_no_pending_task_input(self):
        self.assertNotIn("pending_task_input", _src())

    def test_no_vs_state(self):
        self.assertNotIn("vs_state", _src())

    def test_no_proj_state(self):
        self.assertNotIn("proj_state", _src())

    def test_no_conversation_history(self):
        self.assertNotIn("conversation_history", _src())

    def test_no_hilfe_text(self):
        self.assertNotIn("HILFE_TEXT", _src())

    def test_no_dispatch_command(self):
        self.assertNotIn("def _dispatch_command(", _src())

    def test_no_nlp_fallback(self):
        self.assertNotIn("run_claude_with_history", _src())

    def test_removed_system_prompts(self):
        src = _src()
        for name in ["TASK_SYSTEM_PROMPT", "FOKUS_SYSTEM_PROMPT",
                     "VERSCHIEBEN_SYSTEM_PROMPT", "STATUS_SYSTEM_PROMPT",
                     "CHAT_SYSTEM_PROMPT", "SUCHE_SYSTEM_PROMPT"]:
            self.assertNotIn(name, src, f"Should be removed: {name}")


if __name__ == "__main__":
    unittest.main()

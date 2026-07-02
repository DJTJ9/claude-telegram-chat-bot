import unittest

def _src():
    with open("bots/organizer.py", encoding="utf-8") as f:
        return f.read()

def _settings_src():
    with open("core/settings.py", encoding="utf-8") as f:
        return f.read()


class TestEnergieLevel(unittest.TestCase):
    def test_energie_icons_defined(self):
        self.assertIn("ENERGIE_ICONS", _src())

    def test_energie_in_button_map(self):
        self.assertIn('"🔋 Energie"', _src())
        self.assertIn('"energie"', _src())

    def test_energie_in_reply_keyboard(self):
        src = _src()
        self.assertIn("🔋 Energie", src)
        self.assertIn("🔄 Zyklen", src)

    def test_energie_workflow_kind(self):
        self.assertIn('kind == "energie"', _src())

    def test_energie_callback_handler(self):
        self.assertIn('data.startswith("energie:")', _src())

    def test_energie_settings_keys(self):
        src = _src()
        self.assertIn('"energie_level"', src)
        self.assertIn('"energie_updated"', src)

    def test_energie_defaults_in_settings_py(self):
        src = _settings_src()
        self.assertIn('"energie_level"', src)
        self.assertIn('"energie_updated"', src)

    def test_energie_command_registered(self):
        src = _src()
        self.assertIn('"command": "energie"', src)


class TestWochensicht(unittest.TestCase):
    def test_wochensicht_prompt_defined(self):
        self.assertIn("WOCHENSICHT_SYSTEM_PROMPT", _src())

    def test_wochensicht_prompt_forward(self):
        src = _src()
        idx = src.index("WOCHENSICHT_SYSTEM_PROMPT")
        snippet = src[idx:idx+400]
        self.assertIn("heute+7", snippet)

    def test_woche_handler_uses_new_prompt(self):
        src = _src()
        woche_idx = src.index('kind == "woche"')
        snippet = src[woche_idx:woche_idx+200]
        self.assertIn("WOCHENSICHT_SYSTEM_PROMPT", snippet)


class TestZyklenCRUD(unittest.TestCase):
    def test_zyklen_list_prompt(self):
        self.assertIn("ZYKLEN_LIST_SYSTEM_PROMPT", _src())

    def test_zyklen_neu_prompt(self):
        self.assertIn("ZYKLEN_NEU_SYSTEM_PROMPT", _src())

    def test_zyklen_delete_prompt(self):
        self.assertIn("ZYKLEN_DELETE_SYSTEM_PROMPT", _src())

    def test_zyklen_workflow_kind(self):
        self.assertIn('kind == "zyklen"', _src())

    def test_zyklen_neu_steps(self):
        src = _src()
        self.assertIn('"zyklen:name"', src)
        self.assertIn('"zyklen:rhythmus"', src)

    def test_zyklen_callbacks(self):
        src = _src()
        self.assertIn('"zyklen:rhythmus:', src)
        self.assertIn('data.startswith("zyklen_del:")', src)

    def test_zyklen_wochentag_buttons(self):
        src = _src()
        self.assertIn("wöchentlich_mo", src)
        self.assertIn("wöchentlich_fr", src)


class TestEnergieFilter(unittest.TestCase):
    def test_moin_reads_energie_level(self):
        src = _src()
        moin_idx = src.index("def _send_moin_messages(")
        snippet = src[moin_idx:moin_idx+2000]
        self.assertIn("energie_level", snippet)

    def test_moin_energie_sorting(self):
        src = _src()
        moin_idx = src.index("def _send_moin_messages(")
        snippet = src[moin_idx:moin_idx+2000]
        self.assertIn('"niedrig"', snippet)
        self.assertIn('"hoch"', snippet.lower())

    def test_moin_energie_in_header(self):
        src = _src()
        moin_idx = src.index("def _send_moin_messages(")
        snippet = src[moin_idx:moin_idx+2000]
        self.assertIn("ENERGIE_ICONS", snippet)

    def test_verschieben_marker(self):
        src = _src()
        moin_idx = src.index("def _send_moin_messages(")
        snippet = src[moin_idx:moin_idx+2500]
        self.assertIn("Verschieben", snippet)

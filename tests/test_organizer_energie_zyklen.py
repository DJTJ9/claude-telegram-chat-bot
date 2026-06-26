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


class TestZyklenInstanziierung(unittest.TestCase):
    def test_instanz_zyklen_defined(self):
        self.assertIn("def _instanz_zyklen(", _src())

    def test_instanz_prompt_defined(self):
        self.assertIn("ZYKLEN_INSTANZ_SYSTEM_PROMPT", _src())

    def test_instanz_zyklen_called_in_morgen(self):
        src = _src()
        morgen_idx = src.index('kind == "morgen"')
        snippet = src[morgen_idx:morgen_idx+400]
        self.assertIn("_instanz_zyklen(", snippet)

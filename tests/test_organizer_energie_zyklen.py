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

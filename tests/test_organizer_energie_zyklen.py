import os
import sys
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
    def test_wochensicht_prompt_removed(self):
        self.assertNotIn("WOCHENSICHT_SYSTEM_PROMPT", _src())

    def test_woche_handler_uses_fetch_woche_data(self):
        src = _src()
        woche_idx = src.index('kind == "woche"')
        snippet = src[woche_idx:woche_idx + 600]
        self.assertIn("fetch_woche_data", snippet)

    def test_woche_frieze_marker_present(self):
        self.assertIn("_build_wochenfries", _src())

    def test_woche_prio_icons_defined(self):
        src = _src()
        idx = src.index("_format_woche_message")
        snippet = src[idx:idx + 1200]
        self.assertIn("🔴", snippet)
        self.assertIn("🟡", snippet)
        self.assertIn("🟢", snippet)


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


os.environ.setdefault("NOTION_TOKEN", "test")
os.environ.setdefault("TOKEN_ORGANIZER", "test")
os.environ.setdefault("GROQ_API_KEY", "test")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import bots.organizer as org


class TestWocheFormatting(unittest.TestCase):
    def test_build_wochenfries_labels_and_markers(self):
        # 2026-07-06 is a Monday
        fries = org._build_wochenfries("2026-07-06", ["2026-07-07", "2026-07-10"])
        days = fries.split("·")
        self.assertEqual(len(days), 7)
        self.assertEqual(
            [d.rstrip("🔴") for d in days],
            ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
        )
        # only Di (07-07) and Fr (07-10) should carry the marker
        expected_markers = ["Mo", "Di🔴", "Mi", "Do", "Fr🔴", "Sa", "So"]
        self.assertEqual(days, expected_markers)

    def test_build_wochenfries_no_termine(self):
        fries = org._build_wochenfries("2026-07-06", [])
        self.assertEqual(fries, "Mo·Di·Mi·Do·Fr·Sa·So")
        self.assertNotIn("🔴", fries)

    def _sample_data(self):
        return {
            "start": "2026-07-06",
            "end": "2026-07-12",
            "appointments": [
                {"datum": "2026-07-08", "time": "14:00", "name": "Zahnarzt"},
            ],
            "tasks": [
                {"name": "Rechnung stellen", "prio": "Hoch"},
                {"name": "Wäsche waschen", "prio": "Niedrig"},
            ],
            "habits": [
                {"name": "Sport", "zyklus": "täglich"},
            ],
            "backlog": [
                {"id": "b1", "name": "Umzugskartons besorgen"},
            ],
            "termin_days": ["2026-07-08"],
        }

    def test_format_woche_message_returns_tuple(self):
        result = org._format_woche_message(self._sample_data())
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        text, buttons = result
        self.assertIsInstance(text, str)
        self.assertIsInstance(buttons, list)

    def test_format_woche_message_termine_grouped_by_day(self):
        text, _ = org._format_woche_message(self._sample_data())
        from datetime import date as _date
        expected_day_header = _date.fromisoformat("2026-07-08").strftime("%a %d.%m")
        self.assertIn(expected_day_header, text)
        self.assertIn("14:00  Zahnarzt", text)

    def test_format_woche_message_tasks_grouped_by_prio(self):
        text, _ = org._format_woche_message(self._sample_data())
        hoch_idx = text.index("🔴 Hoch")
        niedrig_idx = text.index("🟢 Niedrig")
        self.assertLess(hoch_idx, niedrig_idx)
        self.assertIn("Rechnung stellen", text[hoch_idx:niedrig_idx])
        self.assertIn("Wäsche waschen", text[niedrig_idx:])

    def test_format_woche_message_habits_have_prefix(self):
        text, _ = org._format_woche_message(self._sample_data())
        self.assertIn("🔁 Sport (täglich)", text)

    def test_format_woche_message_backlog_buttons(self):
        text, buttons = org._format_woche_message(self._sample_data())
        self.assertIn("Umzugskartons besorgen", text)
        self.assertEqual(len(buttons), 1)
        button = buttons[0][0]
        self.assertTrue(button["callback_data"].startswith("woche_promote:"))
        self.assertEqual(button["callback_data"], "woche_promote:b1")

    def test_format_woche_message_empty_sections(self):
        empty_data = {
            "start": "2026-07-06",
            "end": "2026-07-12",
            "appointments": [],
            "tasks": [],
            "habits": [],
            "backlog": [],
            "termin_days": [],
        }
        text, buttons = org._format_woche_message(empty_data)
        self.assertIn("(keine Termine diese Woche)", text)
        self.assertIn("(keine Tasks diese Woche)", text)
        self.assertIn("(keine fälligen Habits)", text)
        self.assertIn("(kein Backlog mit Priorität Hoch)", text)
        self.assertEqual(buttons, [])

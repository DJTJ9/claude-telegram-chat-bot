import os, sys, unittest
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("NOCODB_API_URL", "http://localhost")
os.environ.setdefault("NOCODB_API_TOKEN", "tok")
os.environ.setdefault("NOCODB_TASKS_TABLE_ID", "t1")
os.environ.setdefault("NOCODB_SPORT_TABLE_ID", "t2")
os.environ.setdefault("NOCODB_IDEENSAMMLUNG_TABLE_ID", "t3")
os.environ.setdefault("NOCODB_BACKLOG_TABLE_ID", "t4")
os.environ.setdefault("NOCODB_ARCHIV_TABLE_ID", "t5")
os.environ.setdefault("NOCODB_HABITS_TABLE_ID", "t6")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x:y")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123")

from bots.organizer import _parse_user_date

TODAY = date(2026, 7, 2)  # Thursday, weekday=3


class TestParseUserDate(unittest.TestCase):
    def test_heute(self):
        self.assertEqual(_parse_user_date("heute", TODAY), "2026-07-02T09:00:00")

    def test_morgen(self):
        self.assertEqual(_parse_user_date("morgen", TODAY), "2026-07-03T09:00:00")

    def test_uebermorgen(self):
        self.assertEqual(_parse_user_date("übermorgen", TODAY), "2026-07-04T09:00:00")

    def test_heute_mit_uhrzeit_colon(self):
        self.assertEqual(_parse_user_date("heute um 14:30", TODAY), "2026-07-02T14:30:00")

    def test_morgen_mit_uhrzeit(self):
        self.assertEqual(_parse_user_date("morgen um 09:00", TODAY), "2026-07-03T09:00:00")

    def test_uhr_format(self):
        self.assertEqual(_parse_user_date("morgen 15 uhr", TODAY), "2026-07-03T15:00:00")

    def test_iso_datum(self):
        self.assertEqual(_parse_user_date("2026-08-15", TODAY), "2026-08-15T09:00:00")

    def test_punkt_datum(self):
        self.assertEqual(_parse_user_date("15.08.", TODAY), "2026-08-15T09:00:00")

    def test_wochentag_montag(self):
        # Thursday → next Monday = 2026-07-06 (+3 days)
        self.assertEqual(_parse_user_date("montag", TODAY), "2026-07-06T09:00:00")

    def test_wochentag_freitag(self):
        # Thursday → next Friday = 2026-07-03 (+1 day)
        self.assertEqual(_parse_user_date("freitag", TODAY), "2026-07-03T09:00:00")

    def test_wochentag_donnerstag_same_day_next_week(self):
        # Thursday → next Thursday = 2026-07-09 (+7 days, not 0)
        self.assertEqual(_parse_user_date("donnerstag", TODAY), "2026-07-09T09:00:00")

    def test_unbekanntes_datum_returns_none(self):
        self.assertIsNone(_parse_user_date("bald", TODAY))

    def test_leerer_string_returns_heute(self):
        self.assertEqual(_parse_user_date("", TODAY), "2026-07-02T09:00:00")


if __name__ == "__main__":
    unittest.main()

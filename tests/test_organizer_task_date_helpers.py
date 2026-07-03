import os, sys
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

from bots.organizer import _task_date_from_choice, _task_date_from_freitext

TODAY = date(2026, 7, 3)


def test_heute_returns_today_iso():
    assert _task_date_from_choice("heute", TODAY) == "2026-07-03"


def test_morgen_returns_tomorrow_iso():
    assert _task_date_from_choice("morgen", TODAY) == "2026-07-04"


def test_spaeter_returns_none():
    assert _task_date_from_choice("spaeter", TODAY) is None


def test_unknown_choice_returns_none():
    assert _task_date_from_choice("???", TODAY) is None


def test_freitext_valid_date_strips_time():
    result = _task_date_from_freitext("15.07.", TODAY)
    assert result == "2026-07-15"
    assert "T" not in result


def test_freitext_weekday_strips_time():
    result = _task_date_from_freitext("montag", TODAY)
    assert result is not None
    assert "T" not in result


def test_freitext_invalid_returns_none():
    assert _task_date_from_freitext("blabla", TODAY) is None

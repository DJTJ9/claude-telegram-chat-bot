import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.nocodb_direct import fetch_tasks_today, fetch_abend_data, fetch_sport_challenges
from datetime import date


def test_fetch_tasks_today_returns_correct_shape():
    result = fetch_tasks_today(date.today().isoformat())
    assert isinstance(result, dict)
    assert set(result.keys()) >= {"date", "appointments", "tasks", "habits", "proj_tasks"}
    assert isinstance(result["appointments"], list)
    assert isinstance(result["tasks"], list)


def test_fetch_tasks_today_ids_are_strings():
    result = fetch_tasks_today(date.today().isoformat())
    for item in result["appointments"] + result["tasks"]:
        assert isinstance(item["id"], str)
        assert item["id"].isdigit()


def test_fetch_abend_data_returns_correct_shape():
    result = fetch_abend_data(date.today().isoformat())
    assert isinstance(result, dict)
    assert set(result.keys()) >= {"date", "done", "open", "missed_habits", "projekt_bilanz"}


def test_fetch_sport_challenges_returns_list():
    result = fetch_sport_challenges()
    assert isinstance(result, list)
    for ch in result:
        assert "name" in ch and "id" in ch and "kategorie" in ch
        assert isinstance(ch["id"], str)

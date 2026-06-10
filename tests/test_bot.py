import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bot import normalize_voice

def test_doppelpunkt_lower():
    assert normalize_voice("task doppelpunkt bug fixen") == "task: bug fixen"

def test_doppelpunkt_upper():
    assert normalize_voice("Task Doppelpunkt bug fixen") == "Task: bug fixen"

def test_komma():
    assert normalize_voice("eins komma fünf") == "eins, fünf"

def test_punkt():
    assert normalize_voice("Ende punkt") == "Ende."

def test_no_change():
    assert normalize_voice("moin") == "moin"

def test_combined():
    assert normalize_voice("status doppelpunkt sport erledigt") == "status: sport erledigt"

def test_status_prefix_detection():
    text = "status: sport erledigt"
    assert text.lower().startswith("status:")
    assert text[7:].strip() == "sport erledigt"

def test_status_prefix_voice():
    text = normalize_voice("status doppelpunkt sport erledigt")
    assert text.lower().startswith("status:")
    assert text[7:].strip() == "sport erledigt"

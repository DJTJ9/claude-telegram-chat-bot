from pathlib import Path
src = (Path(__file__).parent.parent / "bots/organizer.py").read_text(encoding="utf-8")


def test_nocodb_import_present():
    assert "from core import nocodb_direct" in src


def test_morgen_uses_fetch_tasks_today():
    assert "nocodb_direct.fetch_tasks_today" in src


def test_sport_challenges_uses_nocodb():
    assert "nocodb_direct.fetch_sport_challenges" in src


def test_moin_json_prompt_removed():
    assert "MOIN_JSON_SYSTEM_PROMPT" not in src


def test_moin_system_prompt_removed():
    assert "MOIN_SYSTEM_PROMPT" not in src


def test_sport_challenges_prompt_removed():
    assert "SPORT_CHALLENGES_SYSTEM_PROMPT" not in src


def test_abend_uses_fetch_abend_data():
    assert "nocodb_direct.fetch_abend_data" in src


def test_abend_json_prompt_removed():
    assert "ABEND_JSON_SYSTEM_PROMPT" not in src


def test_abend_system_prompt_removed():
    assert "ABEND_SYSTEM_PROMPT" not in src


def test_done_callback_uses_nocodb():
    assert "nocodb_direct.mark_done" in src


def test_sport_done_callback_uses_nocodb():
    assert "nocodb_direct.mark_sport_done" in src


def test_reschedule_uses_nocodb():
    assert "nocodb_direct.reschedule" in src


def test_int_conversion_in_callbacks():
    assert "int(pid)" in src

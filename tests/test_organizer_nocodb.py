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


def test_task_priority_callback_uses_nocodb():
    idx = src.index('data.startswith("task:priority:")')
    snippet = src[idx:idx+300]
    assert "nocodb_direct.create_task" in snippet


def test_task_priority_no_backlog_system_prompt():
    idx = src.index('data.startswith("task:priority:")')
    snippet = src[idx:idx+300]
    assert "BACKLOG_SYSTEM_PROMPT" not in snippet


def test_task_priority_confirmation_message():
    idx = src.index('data.startswith("task:priority:")')
    snippet = src[idx:idx+300]
    assert "✅ Task angelegt" in snippet


def test_backlog_list_uses_fetch_backlog_items():
    assert "nocodb_direct.fetch_backlog_items" in src


def test_backlog_list_no_backlog_json_prompt():
    idx = src.index('"backlog_list"')
    snippet = src[idx:idx+700]
    assert "BACKLOG_JSON_SYSTEM_PROMPT" not in snippet


def test_backlog_new_workflow_exists():
    assert '"backlog_new"' in src
    assert "backlog_new:name" in src


def test_backlog_new_uses_create_backlog_item():
    assert "nocodb_direct.create_backlog_item" in src


def test_backlog_new_button_in_backlog_list():
    idx = src.index('kind == "backlog_list"')
    snippet = src[idx:idx+700]
    assert "backlog:new" in snippet


def test_termin_priority_no_llm_call():
    idx = src.index('data.startswith("termin:priority:")')
    snippet = src[idx:idx+450]
    assert "run_claude" not in snippet
    assert "TERMIN_SYSTEM_PROMPT" not in snippet


def test_termin_priority_uses_parse_user_date():
    idx = src.index('data.startswith("termin:priority:")')
    snippet = src[idx:idx+450]
    assert "_parse_user_date" in snippet


def test_termin_priority_uses_create_task():
    idx = src.index('data.startswith("termin:priority:")')
    snippet = src[idx:idx+550]
    assert "nocodb_direct.create_task" in snippet

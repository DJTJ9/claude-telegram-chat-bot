import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import bot

BACKLOG_ID = bot.BACKLOG_DATA_SOURCE_ID
ARCHIV_ID = bot.ARCHIV_DATA_SOURCE_ID

def test_backlog_id_is_set():
    assert BACKLOG_ID and BACKLOG_ID != "<BACKLOG_DATA_SOURCE_ID>"

def test_archiv_id_is_set():
    assert ARCHIV_ID and ARCHIV_ID != "<ARCHIV_DATA_SOURCE_ID>"

def test_backlog_system_prompt_contains_backlog_id():
    assert BACKLOG_ID in bot.BACKLOG_SYSTEM_PROMPT

def test_backlog_list_prompt_contains_backlog_id():
    assert BACKLOG_ID in bot.BACKLOG_LIST_SYSTEM_PROMPT

def test_archive_loop_prompt_contains_both_ids():
    assert BACKLOG_ID in bot.ARCHIVE_LOOP_SYSTEM_PROMPT
    assert ARCHIV_ID in bot.ARCHIVE_LOOP_SYSTEM_PROMPT

def test_archive_task_prompt_contains_archiv_id():
    assert ARCHIV_ID in bot.ARCHIVE_TASK_SYSTEM_PROMPT

def test_backlog_promote_prompt_contains_backlog_id():
    assert BACKLOG_ID in bot.BACKLOG_PROMOTE_SYSTEM_PROMPT

def test_backlog_in_reply_keyboard():
    all_buttons = [btn for row in bot.REPLY_KEYBOARD["keyboard"] for btn in row]
    assert "backlog" in all_buttons

def test_backlog_list_prompt_response_format():
    assert "📌 Backlog" in bot.BACKLOG_LIST_SYSTEM_PROMPT
    assert "offen" in bot.BACKLOG_LIST_SYSTEM_PROMPT

def test_hilfe_contains_backlog():
    assert "backlog:" in bot.HILFE_TEXT
    assert "backlog" in bot.HILFE_TEXT

def test_backlog_system_prompt_response_format():
    assert "📌 Backlog-Task angelegt" in bot.BACKLOG_SYSTEM_PROMPT

def test_backlog_system_prompt_status_offen():
    assert "Offen" in bot.BACKLOG_SYSTEM_PROMPT

import json
from unittest.mock import patch

def test_run_archive_once_calls_run_claude():
    calls = []
    with patch("bot.run_claude", lambda prompt, system_prompt=None, **kw: calls.append(system_prompt) or "✅ Archiviert: 0 Tasks"):
        bot._run_archive_once()
    assert any(bot.ARCHIV_DATA_SOURCE_ID in (sp or "") for sp in calls)

def test_archive_migration_runs_if_flag_missing(tmp_path):
    (tmp_path / "settings.json").write_text('{"notifications_enabled": true}')
    calls = []
    with patch("bot.run_claude", lambda *a, **kw: calls.append(True) or "Nichts zu archivieren."):
        bot._run_migration(str(tmp_path))
    assert len(calls) >= 1
    settings = json.loads((tmp_path / "settings.json").read_text())
    assert settings.get("archive_migration_done") is True

def test_archive_migration_skipped_if_flag_set(tmp_path):
    (tmp_path / "settings.json").write_text('{"notifications_enabled": true, "archive_migration_done": true}')
    calls = []
    with patch("bot.run_claude", lambda *a, **kw: calls.append(True) or ""):
        bot._run_migration(str(tmp_path))
    assert len(calls) == 0

def test_status_erledigt_triggers_archive(monkeypatch):
    archive_calls = []
    monkeypatch.setattr(bot, "_run_archive_once", lambda: archive_calls.append(True))
    status_text = "Sport erledigt"
    if any(w in status_text.lower() for w in ("erledigt", "fertig", "done")):
        bot._run_archive_once()
    assert len(archive_calls) == 1

def test_status_in_arbeit_does_not_trigger_archive(monkeypatch):
    archive_calls = []
    monkeypatch.setattr(bot, "_run_archive_once", lambda: archive_calls.append(True))
    status_text = "Sport in arbeit"
    if any(w in status_text.lower() for w in ("erledigt", "fertig", "done")):
        bot._run_archive_once()
    assert len(archive_calls) == 0

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

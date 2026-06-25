import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _import():
    import importlib
    import scripts.notion_sync as m
    importlib.reload(m)
    return m


def test_build_sync_prompt_discussed():
    m = _import()
    prompt = m.build_sync_prompt("telegram-bot-army", "My Feature", "discussed",
                                 spec="topics/foo/specs/2026-06-25-my-feature-design.md",
                                 db_id="db-123")
    assert "db-123" in prompt
    assert "My Feature" in prompt
    assert "Discussed" in prompt
    assert "Offen" in prompt
    assert "topics/foo/specs/2026-06-25-my-feature-design.md" in prompt
    assert "telegram-bot-army" in prompt


def test_build_sync_prompt_planned():
    m = _import()
    prompt = m.build_sync_prompt("my-slug", "Feature B", "planned",
                                 plan="topics/my-slug/plans/2026-06-25-feature-b.md",
                                 db_id="db-456")
    assert "Planned" in prompt
    assert "In Arbeit" in prompt
    assert "topics/my-slug/plans/2026-06-25-feature-b.md" in prompt


def test_build_sync_prompt_done():
    m = _import()
    prompt = m.build_sync_prompt("my-slug", "Feature C", "done", db_id="db-789")
    assert "Done" in prompt
    assert "Fertig" in prompt


def test_main_skips_when_no_db_id(capsys):
    m = _import()
    m.ARBEIT_DB_ID = ""
    import sys as _sys
    with patch.object(_sys, "argv", ["notion_sync.py", "--slug", "s",
                                      "--feature", "f", "--status", "done"]):
        try:
            m.main()
        except SystemExit as e:
            assert e.code == 0


def test_main_calls_run_claude():
    m = _import()
    m.ARBEIT_DB_ID = "real-db-id"
    with patch("scripts.notion_sync.run_claude", return_value="OK") as mock_rc:
        import sys as _sys
        with patch.object(_sys, "argv", ["notion_sync.py", "--slug", "my-slug",
                                          "--feature", "My Feature", "--status", "discussed",
                                          "--spec", "topics/my-slug/specs/spec.md"]):
            m.main()
        mock_rc.assert_called_once()
        prompt_arg = mock_rc.call_args[0][0]
        assert "My Feature" in prompt_arg
        assert "Discussed" in prompt_arg

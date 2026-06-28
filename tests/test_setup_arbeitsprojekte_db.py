import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _import():
    import importlib
    import scripts.setup_arbeitsprojekte_db as m
    importlib.reload(m)
    return m


def test_build_setup_prompt_contains_properties():
    m = _import()
    prompt = m.build_setup_prompt("db-test-123")
    assert "db-test-123" in prompt
    assert "Typ" in prompt
    assert "Projekt" in prompt
    assert "Feature" in prompt
    assert "Idee" in prompt
    assert "Phase" in prompt
    assert "Status" in prompt
    assert "Offen" in prompt
    assert "Notiz" in prompt
    assert "Archiviere" in prompt


def test_main_skips_when_no_db_id(capsys):
    m = _import()
    m.ARBEIT_DB_ID = ""
    with patch.object(sys, "argv", ["setup_arbeitsprojekte_db.py"]):
        try:
            m.main()
        except SystemExit as e:
            assert e.code == 0


def test_main_calls_run_claude_and_subprocess():
    m = _import()
    m.ARBEIT_DB_ID = "real-db-id"
    with patch("scripts.setup_arbeitsprojekte_db.run_claude", return_value="OK") as mock_rc:
        with patch("scripts.setup_arbeitsprojekte_db.subprocess.run") as mock_sp:
            with patch.object(sys, "argv", ["setup_arbeitsprojekte_db.py"]):
                m.main()
            mock_rc.assert_called_once()
            prompt_arg = mock_rc.call_args[0][0]
            assert "real-db-id" in prompt_arg
            assert "Archiviere" in prompt_arg
            mock_sp.assert_called_once()
            sp_args = mock_sp.call_args[0][0]
            assert "notion_sync.py" in str(sp_args)
            assert "--all" in sp_args

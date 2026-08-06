import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import sharky

REGISTRY = [
    {"slug": "desk-buddy", "path_windows": "C:\\Projekte\\DeskBuddy"},
    {"slug": "dart-app", "path_windows": "C:\\Unity\\Aktuelle Projekte\\DartTrainingsApp"},
    {"slug": "job-scanner", "path_windows": ""},
]


def test_resolve_slug_returns_windows_path():
    assert sharky.resolve_slug(REGISTRY, "desk-buddy") == "C:\\Projekte\\DeskBuddy"


def test_resolve_slug_keeps_spaces():
    assert sharky.resolve_slug(REGISTRY, "dart-app") == \
        "C:\\Unity\\Aktuelle Projekte\\DartTrainingsApp"


def test_resolve_slug_unknown_fails_hard():
    with pytest.raises(SystemExit) as e:
        sharky.resolve_slug(REGISTRY, "gibtsnicht")
    assert "gibtsnicht" in str(e.value)


def test_resolve_slug_without_path_windows_fails_hard():
    with pytest.raises(SystemExit) as e:
        sharky.resolve_slug(REGISTRY, "job-scanner")
    assert "path_windows" in str(e.value)


def test_session_name_with_and_without_slug():
    assert sharky.session_name("game-skill") == "sharky-game-skill"
    assert sharky.session_name("") == "sharky"


def test_ps_quote_doubles_single_quotes():
    assert sharky.ps_quote("O'Brien") == "'O''Brien'"


def test_remote_cmd_cds_and_exports_session():
    assert sharky.remote_cmd("C:\\Projekte\\DeskBuddy", "sharky-desk-buddy", ["--continue"]) == (
        "cd 'C:\\Projekte\\DeskBuddy'; $env:SHARKY_TMUX='sharky-desk-buddy'; "
        "claude.exe '--continue'"
    )


def test_remote_cmd_quotes_paths_with_spaces():
    cmd = sharky.remote_cmd("C:\\Unity\\Aktuelle Projekte\\DartTrainingsApp",
                            "sharky-dart-app", [])
    assert cmd.startswith("cd 'C:\\Unity\\Aktuelle Projekte\\DartTrainingsApp';")


def test_remote_cmd_without_path_has_no_cd():
    assert sharky.remote_cmd("", "sharky", []) == \
        "$env:SHARKY_TMUX='sharky'; claude.exe"


def test_tmux_argv_attaches_when_session_exists():
    assert sharky.tmux_argv("sharky-x", "irrelevant", True) == \
        ["tmux", "attach", "-t", "sharky-x"]


def test_tmux_argv_creates_session_with_ssh():
    argv = sharky.tmux_argv("sharky-x", "claude.exe", False)
    assert argv[:4] == ["tmux", "new", "-s", "sharky-x"]
    assert argv[4].startswith("ssh -t sharky ")


def test_split_args_takes_leading_slug_only():
    assert sharky.split_args(["game-skill", "--continue"]) == ("game-skill", ["--continue"])
    assert sharky.split_args(["--continue"]) == ("", ["--continue"])
    assert sharky.split_args([]) == ("", [])

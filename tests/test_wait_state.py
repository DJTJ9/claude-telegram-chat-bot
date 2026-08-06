import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import wait_state


def _local(monkeypatch, tmp_path):
    monkeypatch.setenv("WORK_DIR", str(tmp_path))
    monkeypatch.setenv("WAIT_STATE_REMOTE", "0")


def _fake_ssh(monkeypatch, tmp_path, sleep=0):
    """ssh-Attrappe auf dem PATH: protokolliert argv, beantwortet die 4 Kommandoformen."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "ssh.log"
    stdin_log = tmp_path / "ssh.stdin"
    fake = bin_dir / "ssh"
    fake.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        f"{'sleep ' + str(sleep) if sleep else 'true'}\n"
        "case \"$*\" in\n"
        f'  *"cat > "*) cat >> "{stdin_log}"; exit 0 ;;\n'
        '  *"test -e"*) exit 1 ;;\n'
        '  *"capture-pane"*) printf "Frage?\\nA) Ja\\n"; exit 0 ;;\n'
        '  *"cat "*) printf "inhalt"; exit 0 ;;\n'
        "esac\n"
        "exit 0\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv("WAIT_STATE_REMOTE", "1")
    monkeypatch.setenv("WAIT_STATE_HOST", "dev")
    monkeypatch.setenv("WAIT_STATE_REMOTE_WORK_DIR", "/srv/bot")
    return log, stdin_log


def test_local_write_read_roundtrip(monkeypatch, tmp_path):
    _local(monkeypatch, tmp_path)
    wait_state.write("pending_wait_s1.json", '{"slug": "x"}')
    assert (tmp_path / "pending_wait_s1.json").exists()
    assert wait_state.read("pending_wait_s1.json") == '{"slug": "x"}'


def test_local_read_missing_returns_empty(monkeypatch, tmp_path):
    _local(monkeypatch, tmp_path)
    assert wait_state.read("fehlt.json") == ""


def test_local_exists_and_delete(monkeypatch, tmp_path):
    _local(monkeypatch, tmp_path)
    wait_state.write("turn_ended_s1.flag", "")
    assert wait_state.exists("turn_ended_s1.flag") is True
    wait_state.delete("turn_ended_s1.flag")
    assert wait_state.exists("turn_ended_s1.flag") is False


def test_local_delete_missing_is_silent(monkeypatch, tmp_path):
    _local(monkeypatch, tmp_path)
    wait_state.delete("gibtsnicht.flag")


def test_remote_write_pipes_content_over_ssh(monkeypatch, tmp_path):
    log, stdin_log = _fake_ssh(monkeypatch, tmp_path)
    wait_state.write("pending_wait_s1.json", '{"slug": "x"}')
    assert "cat > /srv/bot/pending_wait_s1.json" in log.read_text()
    assert stdin_log.read_text() == '{"slug": "x"}'


def test_remote_read_returns_stdout(monkeypatch, tmp_path):
    _fake_ssh(monkeypatch, tmp_path)
    assert wait_state.read("pending_wait_s1.json") == "inhalt"


def test_remote_exists_uses_test_e_and_maps_returncode(monkeypatch, tmp_path):
    log, _ = _fake_ssh(monkeypatch, tmp_path)
    assert wait_state.exists("turn_ended_s1.flag") is False
    assert "test -e /srv/bot/turn_ended_s1.flag" in log.read_text()


def test_remote_delete_uses_rm_f(monkeypatch, tmp_path):
    log, _ = _fake_ssh(monkeypatch, tmp_path)
    wait_state.delete("pending_wait_s1.notified")
    assert "rm -f /srv/bot/pending_wait_s1.notified" in log.read_text()


def test_remote_uses_connect_timeout_and_batchmode(monkeypatch, tmp_path):
    log, _ = _fake_ssh(monkeypatch, tmp_path)
    wait_state.delete("x.flag")
    line = log.read_text()
    assert "BatchMode=yes" in line and "ConnectTimeout=3" in line


def test_remote_timeout_returns_empty_instead_of_raising(monkeypatch, tmp_path):
    _fake_ssh(monkeypatch, tmp_path, sleep=5)
    monkeypatch.setenv("WAIT_STATE_TIMEOUT", "1")
    assert wait_state.read("pending_wait_s1.json") == ""
    assert wait_state.exists("pending_wait_s1.json") is False


def test_pane_local_uses_tmux_pane(monkeypatch, tmp_path):
    _local(monkeypatch, tmp_path)
    monkeypatch.setenv("TMUX_PANE", "%7")
    monkeypatch.setenv("SHARKY_TMUX", "sharky-x")
    assert wait_state.pane() == "%7"


def test_pane_remote_uses_sharky_tmux(monkeypatch, tmp_path):
    _fake_ssh(monkeypatch, tmp_path)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    monkeypatch.setenv("SHARKY_TMUX", "sharky-game-skill")
    assert wait_state.pane() == "sharky-game-skill"


def test_capture_pane_remote_goes_through_ssh(monkeypatch, tmp_path):
    log, _ = _fake_ssh(monkeypatch, tmp_path)
    out = wait_state.capture_pane("sharky-game-skill")
    assert "Frage?" in out
    assert "tmux capture-pane -p -t sharky-game-skill" in log.read_text()


def test_capture_pane_empty_target_returns_empty(monkeypatch, tmp_path):
    _fake_ssh(monkeypatch, tmp_path)
    assert wait_state.capture_pane("") == ""


def test_remote_decodes_as_utf8_not_locale_default(monkeypatch, tmp_path):
    """Auf Windows waere die Locale-Default cp1252 — der Fragetext kaeme als Mojibake an."""
    seen = {}
    real_run = wait_state.subprocess.run

    def spy(argv, **kwargs):
        seen.update(kwargs)
        return real_run(["true"], capture_output=True, text=True)

    _fake_ssh(monkeypatch, tmp_path)
    monkeypatch.setattr(wait_state.subprocess, "run", spy)
    wait_state.capture_pane("sharky-x")
    assert seen.get("encoding") == "utf-8"
    assert seen.get("errors") == "replace"

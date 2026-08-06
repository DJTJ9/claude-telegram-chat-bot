#!/usr/bin/env python3
"""Resolver fuer die drei Wait-Notify-Dateien der Claude-Hooks.

Auf dem Server (Linux) liest und schreibt er lokal in WORK_DIR — Verhalten wie bisher.
Laeuft Claude auf sharky (Windows), muessen die Dateien trotzdem im WORK_DIR des Servers
landen: nur dort pollt der Brain Bot. Dann geht jeder Zugriff ueber `ssh dev`.

Alle Remote-Calls sind fail-quiet und hart getimeoutet — on_notification.py hat 10 s
Hook-Budget, ein haengendes SSH darf es nicht aufbrauchen.
"""
import os
import shlex
import subprocess
from pathlib import Path

REMOTE_DEFAULT_WORK_DIR = "/root/projekte/telegram-bot-army"
CONNECT_TIMEOUT = 3


def _remote() -> bool:
    forced = os.environ.get("WAIT_STATE_REMOTE", "")
    if forced:
        return forced == "1"
    return os.name == "nt"


def _host() -> str:
    return os.environ.get("WAIT_STATE_HOST", "dev")


def _timeout() -> float:
    return float(os.environ.get("WAIT_STATE_TIMEOUT", "6"))


def _work_dir() -> Path:
    return Path(os.environ.get("WORK_DIR", str(Path(__file__).parent.parent)))


def _target(name: str) -> str:
    remote_dir = os.environ.get("WAIT_STATE_REMOTE_WORK_DIR", REMOTE_DEFAULT_WORK_DIR)
    return shlex.quote(f"{remote_dir}/{name}")


def _ssh(command: str, stdin: str = ""):
    """CompletedProcess oder None — None heisst: Rueckkanal gerade nicht verfuegbar."""
    argv = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={CONNECT_TIMEOUT}",
            _host(), command]
    try:
        return subprocess.run(argv, input=stdin, capture_output=True,
                              text=True, timeout=_timeout())
    except Exception:
        return None


def write(name: str, content: str) -> None:
    if _remote():
        _ssh(f"cat > {_target(name)}", stdin=content)
        return
    (_work_dir() / name).write_text(content)


def read(name: str) -> str:
    """Inhalt, oder "" wenn die Datei fehlt bzw. der Zugriff scheitert."""
    if _remote():
        r = _ssh(f"cat {_target(name)} 2>/dev/null")
        return r.stdout if r and r.returncode == 0 else ""
    try:
        return (_work_dir() / name).read_text()
    except OSError:
        return ""


def exists(name: str) -> bool:
    if _remote():
        r = _ssh(f"test -e {_target(name)}")
        return bool(r) and r.returncode == 0
    return (_work_dir() / name).exists()


def delete(name: str) -> None:
    if _remote():
        _ssh(f"rm -f {_target(name)}")
        return
    (_work_dir() / name).unlink(missing_ok=True)


def pane() -> str:
    """Capture-Ziel: lokal die tmux-Pane, remote die Server-Session aus sharky.py."""
    if _remote():
        return os.environ.get("SHARKY_TMUX", "")
    return os.environ.get("TMUX_PANE", "")


def capture_pane(target: str) -> str:
    if not target:
        return ""
    if _remote():
        r = _ssh(f"tmux capture-pane -p -t {shlex.quote(target)}")
        return r.stdout if r and r.returncode == 0 else ""
    try:
        return subprocess.run(["tmux", "capture-pane", "-p", "-t", target],
                              capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return ""

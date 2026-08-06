#!/usr/bin/env python3
"""Ein-Wort-Einstieg vom Server auf den Windows-Rechner sharky.

    sharky [<slug>] [claude-args...]

Baut (oder attacht) eine tmux-Session auf dem Server, die per `ssh -t sharky` eine
native Claude-Code-Session (claude.exe) in einer PowerShell haelt. Die Persistenz
liegt damit auf dem 24/7-Server, nicht auf Windows — ein Handy-Netzwechsel kostet
nur das aeussere SSH.

Ohne <slug> landet die Session im Windows-Home (kein cd).
"""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

HUB_DIR = Path(os.environ.get("HUB_DIR", "/root/projects-hub"))
SSH_HOST = "sharky"


def load_registry() -> list:
    return json.loads((HUB_DIR / "projects-registry.json").read_text(encoding="utf-8"))


def resolve_slug(registry: list, slug: str) -> str:
    """Windows-Pfad eines Slugs. Fail-hard statt stillem cd ins Home."""
    for entry in registry:
        if entry.get("slug") == slug:
            win = entry.get("path_windows") or ""
            if not win:
                raise SystemExit(
                    f"sharky: '{slug}' hat kein path_windows in der Registry")
            return win
    raise SystemExit(f"sharky: unbekannter Slug '{slug}'")


def ps_quote(s: str) -> str:
    """PowerShell-Single-Quote-Literal: innen wird ' verdoppelt."""
    return "'" + s.replace("'", "''") + "'"


def session_name(slug: str) -> str:
    return f"sharky-{slug}" if slug else "sharky"


def remote_cmd(win_path: str, session: str, claude_args: list) -> str:
    """PowerShell-Einzeiler, der auf sharky laeuft.

    SHARKY_TMUX reicht die Server-Session-Kennung durch: auf Windows ist TMUX_PANE
    leer, weil tmux auf dem Server laeuft — wait_state.py braucht das Ziel fuer
    `tmux capture-pane`.
    """
    parts = []
    if win_path:
        parts.append(f"cd {ps_quote(win_path)};")
    parts.append(f"$env:SHARKY_TMUX={ps_quote(session)};")
    parts.append("claude.exe")
    parts.extend(ps_quote(a) for a in claude_args)
    return " ".join(parts)


def tmux_argv(session: str, remote: str, exists: bool) -> list:
    if exists:
        return ["tmux", "attach", "-t", session]
    return ["tmux", "new", "-s", session,
            f"ssh -t {SSH_HOST} {shlex.quote(remote)}"]


def session_exists(session: str) -> bool:
    return subprocess.run(["tmux", "has-session", "-t", session],
                          capture_output=True).returncode == 0


def split_args(argv: list) -> tuple:
    """Fuehrendes Nicht-Flag ist der Slug, der Rest geht an claude."""
    args = list(argv)
    if args and not args[0].startswith("-"):
        return args.pop(0), args
    return "", args


def main(argv: list) -> int:
    slug, claude_args = split_args(argv)
    win_path = resolve_slug(load_registry(), slug) if slug else ""
    session = session_name(slug)
    cmd = tmux_argv(session, remote_cmd(win_path, session, claude_args),
                    session_exists(session))
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

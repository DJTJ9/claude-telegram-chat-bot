#!/usr/bin/env python3
"""Notification-Hook: schreibt pending_wait_<session_id>.json, wenn eine
gebundene dev-Session auf Input wartet. Brain Bot pollt diese Files."""
import json, os, subprocess, sys, time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))


def main() -> int:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return 0

    session_id = data.get("session_id", "")
    message = data.get("message", "")
    if not session_id:
        return 0

    # Permission-Prompts laufen bereits über on_permission.py
    if "permission" in message.lower():
        return 0

    # Turn bereits beendet (Stop-Hook lief) → generisches Idle-Warten am
    # Prompt-Ende, keine echte blockierende Frage. Nur benachrichtigen, wenn der
    # Agent mitten im Turn wartet (UserPromptSubmit löscht das Flag beim Turn-Start).
    if (WORK_DIR / f"turn_ended_{session_id}.flag").exists():
        return 0

    session_path = WORK_DIR / "dev_sessions" / f"{session_id}.json"
    if not session_path.exists():
        return 0
    try:
        sdata = json.loads(session_path.read_text())
    except Exception:
        return 0
    slug = sdata.get("active_dev_slug") or ""
    if not slug:
        return 0

    impl_until = sdata.get("implementation_mode_until")
    if sdata.get("implementation_mode") and impl_until:
        try:
            if datetime.now() < datetime.fromisoformat(impl_until):
                return 0
        except (ValueError, TypeError):
            pass

    pane = os.environ.get("TMUX_PANE", "")
    if not pane:
        return 0

    try:
        capture = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", pane],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        capture = ""
    lines = [l for l in capture.splitlines() if l.strip()]
    question = "\n".join(lines[-15:])

    (WORK_DIR / f"pending_wait_{session_id}.json").write_text(json.dumps({
        "slug": slug,
        "pane": pane,
        "question": question,
        "timestamp": time.time(),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Notification-Hook: schreibt pending_wait_<session_id>.json, wenn eine
gebundene dev-Session auf Input wartet. Brain Bot pollt diese Files."""
import json, os, subprocess, sys, time
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))


def main() -> int:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return 0

    session_id = data.get("session_id", "")
    if not session_id:
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

    pane = os.environ.get("TMUX_PANE", "")
    question = ""
    if pane:
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
        "feature": sdata.get("active_dev_feature") or "",
        "pane": pane,
        "question": question,
        "timestamp": time.time(),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())

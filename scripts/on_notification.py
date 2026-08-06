#!/usr/bin/env python3
"""Notification-Hook: schreibt pending_wait_<session_id>.json, wenn eine
gebundene dev-Session auf Input wartet. Brain Bot pollt diese Files.

Die Wait-Dateien gehen ueber wait_state: laeuft Claude auf sharky (Windows),
landen sie per ssh im WORK_DIR des Servers, wo der Bot pollt."""
import json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import wait_state

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
    if wait_state.exists(f"turn_ended_{session_id}.flag"):
        return 0

    # Die Session-Bindung ist maschinenlokal (set_session.py schreibt dort, wo
    # claude laeuft) — bleibt lokal, anders als die Wait-Dateien.
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

    pane = wait_state.pane()
    question = ""
    if pane:
        lines = [l for l in wait_state.capture_pane(pane).splitlines() if l.strip()]
        question = "\n".join(lines[-15:])

    wait_state.write(f"pending_wait_{session_id}.json", json.dumps({
        "slug": slug,
        "feature": sdata.get("active_dev_feature") or "",
        "pane": pane,
        "question": question,
        "timestamp": time.time(),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())

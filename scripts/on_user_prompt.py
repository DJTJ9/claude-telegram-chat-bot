#!/usr/bin/env python3
"""UserPromptSubmit-Hook: löscht das turn_ended-Flag beim Turn-Start.
Dadurch darf on_notification.py wieder benachrichtigen, wenn der Agent später
mitten im Turn auf eine echte Antwort wartet (z.B. AskUserQuestion)."""
import json, os, sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))

try:
    _sid = json.loads(sys.stdin.read()).get("session_id", "")
except Exception:
    _sid = ""
if _sid:
    (WORK_DIR / f"turn_ended_{_sid}.flag").unlink(missing_ok=True)
sys.exit(0)

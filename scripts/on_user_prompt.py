#!/usr/bin/env python3
"""UserPromptSubmit-Hook: löscht das turn_ended-Flag beim Turn-Start.
Dadurch darf on_notification.py wieder benachrichtigen, wenn der Agent später
mitten im Turn auf eine echte Antwort wartet (z.B. AskUserQuestion)."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import wait_state

try:
    _sid = json.loads(sys.stdin.read()).get("session_id", "")
except Exception:
    _sid = ""
if _sid:
    wait_state.delete(f"turn_ended_{_sid}.flag")
sys.exit(0)

import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import wait_state

try:
    _sid = json.loads(sys.stdin.read()).get("session_id", "")
except Exception:
    _sid = ""
if _sid:
    wait_state.delete(f"pending_wait_{_sid}.json")
    wait_state.delete(f"pending_wait_{_sid}.notified")
    # Turn beendet: markiert, dass ein danach feuerndes Idle-Notification kein
    # echtes Warten auf eine Antwort ist (on_notification.py skippt dann).
    wait_state.write(f"turn_ended_{_sid}.flag", "")

import json, os, sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))

try:
    _sid = json.loads(sys.stdin.read()).get("session_id", "")
except Exception:
    _sid = ""
if _sid:
    (WORK_DIR / f"pending_wait_{_sid}.json").unlink(missing_ok=True)
    # Turn beendet: markiert, dass ein danach feuerndes Idle-Notification kein
    # echtes Warten auf eine Antwort ist (on_notification.py skippt dann).
    (WORK_DIR / f"turn_ended_{_sid}.flag").write_text("")

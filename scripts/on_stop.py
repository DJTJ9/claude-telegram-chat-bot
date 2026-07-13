import os, sys, json, requests
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

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

TOKEN = os.environ.get("TOKEN_PERMISSIONS")
MY_CHAT_ID = int(os.environ.get("CHAT_ID", "8896609541"))

if not TOKEN:
    sys.exit(0)

if os.environ.get("CLAUDE_AUTOMATED") == "1":
    sys.exit(0)

settings_path = PROJECT_DIR / "settings.json"
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text())
        if not settings.get("notifications_enabled", True):
            sys.exit(0)
    except Exception:
        pass

try:
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": MY_CHAT_ID, "text": "✅ Claude Code Task abgeschlossen"},
        timeout=10,
    )
except Exception:
    pass

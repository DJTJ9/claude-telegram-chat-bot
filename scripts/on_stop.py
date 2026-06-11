import os, sys, json, requests
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

# Load .env manually
env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

TOKEN = os.environ.get("TELEGRAM_TOKEN")
MY_CHAT_ID = 8896609541

if not TOKEN:
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

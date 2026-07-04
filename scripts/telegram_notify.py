import os, sys, requests
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(PROJECT_DIR))
from core.settings import load_settings
from core.routing import get_notify_token, get_chat_id

_args = sys.argv[1:]
bot_override = None
if len(_args) >= 2 and _args[0] == "--bot":
    bot_override = _args[1]
    _args = _args[2:]

if not _args:
    sys.exit(0)

settings = load_settings()
if not settings.get("notifications_enabled", True):
    sys.exit(0)

token = os.environ.get(f"TOKEN_{bot_override.upper()}") if bot_override else get_notify_token(settings)
chat_id = get_chat_id()

if not token:
    sys.exit(0)

try:
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": _args[0]},
        timeout=10,
    )
except Exception:
    pass

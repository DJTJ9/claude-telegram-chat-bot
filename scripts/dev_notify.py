"""Pflicht-Notify für /dev finish — bewusst NICHT über telegram_notify.py,
da dessen --bot-Flag die Meldung fest an den brain-Bot adressiert, statt sie
über active_session zu routen."""
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

args = sys.argv[1:]
if len(args) < 3 or args[0] != "--bot":
    sys.exit(0)

bot_name, message = args[1], args[2]
token = os.environ.get(f"TOKEN_{bot_name.upper()}")
chat_id = os.environ.get("CHAT_ID", "8896609541")

if not token:
    sys.exit(0)

try:
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": int(chat_id), "text": message},
        timeout=10,
    )
    if r.status_code != 200:
        print(f"dev_notify HTTP {r.status_code}: {r.text}")
except Exception as exc:
    print(f"dev_notify FEHLER: {exc}")

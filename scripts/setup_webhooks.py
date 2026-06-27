#!/usr/bin/env python3
import os, requests
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

BASE_URL = "https://code.thinkshark.de"

BOTS = [
    ("TOKEN_BRAIN",       "brain"),
    ("TOKEN_ORGANIZER",   "organizer"),
    ("TOKEN_TEACH",       "teach"),
    ("TOKEN_PERMISSIONS", "permissions"),
]

for env_key, name in BOTS:
    token = os.environ[env_key]
    url = f"{BASE_URL}/webhook/{name}/{token}"
    r = requests.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        json={"url": url},
    )
    result = r.json()
    if result.get("ok"):
        print(f"✅ {name}: {url}")
    else:
        print(f"❌ {name}: {result.get('description', result)}")

#!/usr/bin/env python3
"""Seed example habits into NocoDB habits table."""
import os, sys
from pathlib import Path
import requests

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

NOCODB_API_URL = os.environ.get("NOCODB_API_URL", "")
NOCODB_API_TOKEN = os.environ.get("NOCODB_API_TOKEN", "")
HABITS_TABLE_ID = os.environ.get("NOCODB_HABITS_TABLE_ID", "")

HABITS = [
    {"Name": "Meditation",  "Kategorie": "Gesundheit",  "Zyklus": "täglich",    "Status": "Not Started"},
    {"Name": "Lesen",       "Kategorie": "Lernen",       "Zyklus": "täglich",    "Status": "Not Started"},
    {"Name": "Sport",       "Kategorie": "Gesundheit",  "Zyklus": "wochentags", "Status": "Not Started"},
    {"Name": "Dankbarkeit", "Kategorie": "Gesundheit",  "Zyklus": "täglich",    "Status": "Not Started"},
    {"Name": "Journaling",  "Kategorie": "Lernen",       "Zyklus": "täglich",    "Status": "Not Started"},
]


def main() -> None:
    if not (NOCODB_API_URL and HABITS_TABLE_ID):
        print("⚠️  NOCODB_API_URL or NOCODB_HABITS_TABLE_ID not set", file=sys.stderr)
        sys.exit(1)
    headers = {"xc-token": NOCODB_API_TOKEN, "Content-Type": "application/json"}
    url = f"{NOCODB_API_URL}/api/v2/tables/{HABITS_TABLE_ID}/records"
    for habit in HABITS:
        r = requests.post(url, headers=headers, json=habit)
        status = "✅" if r.status_code == 200 else f"⚠️  {r.status_code}"
        print(f"{status} {habit['Name']}")


if __name__ == "__main__":
    main()

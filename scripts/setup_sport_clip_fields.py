#!/usr/bin/env python3
"""Einmalig: legt die Spalten Medium (Attachment), Quelle (URL), Notiz (LongText)
in der NocoDB Sport Challenges Table an. Idempotent — vorhandene Spalten werden übersprungen."""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

API_URL = os.environ.get("NOCODB_API_URL", "http://localhost:8090")
TOKEN = os.environ.get("NOCODB_API_TOKEN", "")
TABLE_ID = os.environ.get("NOCODB_SPORT_TABLE_ID", "")

FIELDS = [
    {"title": "Medium", "uidt": "Attachment"},
    {"title": "Quelle", "uidt": "URL"},
    {"title": "Notiz", "uidt": "LongText"},
]


def main() -> int:
    headers = {"xc-token": TOKEN, "Content-Type": "application/json"}
    # Meta-API läuft auf dem Host ohne Workspace/Base-Pfad-Präfix der Daten-API
    _parts = urlsplit(API_URL)
    meta_url = f"{_parts.scheme}://{_parts.netloc}/api/v2/meta/tables/{TABLE_ID}"
    r = requests.get(meta_url, headers=headers)
    if r.status_code != 200:
        print(f"Meta-GET fehlgeschlagen: {r.status_code} {r.text[:200]}")
        return 1
    existing = {c["title"] for c in r.json().get("columns", [])}
    for field in FIELDS:
        if field["title"] in existing:
            print(f"übersprungen (existiert): {field['title']}")
            continue
        r = requests.post(f"{meta_url}/columns", headers=headers, json=field)
        if r.status_code not in (200, 201):
            print(f"FEHLER bei {field['title']}: {r.status_code} {r.text[:200]}")
            return 1
        print(f"angelegt: {field['title']} ({field['uidt']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

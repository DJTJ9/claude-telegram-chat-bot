#!/usr/bin/env python3
"""Promote a Backlog item to a Task with a week date."""
import os, sys, requests
from pathlib import Path

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

NOCODB_API_URL = os.environ.get("NOCODB_API_URL", "http://localhost:8090")
NOCODB_API_TOKEN = os.environ.get("NOCODB_API_TOKEN", "")
TASKS_TABLE_ID = os.environ.get("NOCODB_TASKS_TABLE_ID", "")
BACKLOG_TABLE_ID = os.environ.get("NOCODB_BACKLOG_TABLE_ID", "")


def _headers() -> dict:
    return {"xc-token": NOCODB_API_TOKEN, "Content-Type": "application/json"}


def _url(table_id: str) -> str:
    return f"{NOCODB_API_URL}/api/v2/tables/{table_id}/records"


def fetch_open_backlog() -> list:
    r = requests.get(_url(BACKLOG_TABLE_ID), headers=_headers(),
                     params={"where": "(Status,eq,Offen)", "limit": 100})
    return r.json().get("list", []) if r.status_code == 200 else []


def promote_to_task(name: str, prioritaet: str, datum: str) -> bool:
    r = requests.post(_url(TASKS_TABLE_ID), headers=_headers(), json={
        "Name": name,
        "Status": "Not started",
        "Priorität": prioritaet,
        "Datum": datum,
    })
    return r.status_code == 200


def main() -> None:
    if not TASKS_TABLE_ID or not BACKLOG_TABLE_ID:
        print("⚠️  NOCODB_TASKS_TABLE_ID and NOCODB_BACKLOG_TABLE_ID must be set", file=sys.stderr)
        sys.exit(1)

    items = fetch_open_backlog()
    if not items:
        print("Keine offenen Backlog-Items.")
        return

    print("Offene Backlog-Items:")
    for i, item in enumerate(items, 1):
        prio = item.get("Priorität", "-")
        print(f"  {i}. [{prio}] {item['Name']}")

    raw = input("\nNummer + Datum (z.B. '2 2026-07-03'): ").strip()
    parts = raw.split()
    if len(parts) != 2:
        print("⚠️  Format: <Nummer> <YYYY-MM-DD>")
        sys.exit(1)

    idx = int(parts[0]) - 1
    datum = parts[1]
    item = items[idx]
    ok = promote_to_task(item["Name"], item.get("Priorität", "Mittel"), datum)
    if ok:
        print(f"✅ '{item['Name']}' als Task für {datum} erstellt.")
    else:
        print("⚠️  Fehler beim Erstellen des Tasks.")


if __name__ == "__main__":
    main()

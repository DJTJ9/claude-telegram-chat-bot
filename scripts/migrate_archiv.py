#!/usr/bin/env python3
"""Migrate entries from old Task-Archiv DB to new Archiv DB."""
import os, sys, json
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import urllib.request

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
OLD_DB = "abb5abd8-e320-4796-bbf6-941feb9007b9"
NEW_DB = "38b4bba29c558102b9aecb790594aff6"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def notion_request(method, path, body=None):
    url = f"https://api.notion.com/v1{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def query_all(db_id):
    results, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        resp = notion_request("POST", f"/databases/{db_id}/query", body)
        results.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp["next_cursor"]
    return results


def get_title(page):
    t = page["properties"].get("Name", {}).get("title", [])
    return t[0]["plain_text"] if t else ""


def get_date(page, prop):
    d = page["properties"].get(prop, {}).get("date")
    return d["start"] if d else None


def build_props(src):
    p = src["properties"]
    props = {"Name": {"title": p.get("Name", {}).get("title", [])}}

    status = p.get("Status", {}).get("select")
    if status:
        props["Status"] = {"select": {"name": status["name"]}}

    prio = p.get("Priorität", {}).get("select")
    if prio:
        props["Priorität"] = {"select": {"name": prio["name"]}}

    datum = p.get("Datum", {}).get("date")
    if datum:
        props["Datum"] = {"date": datum}

    bereich = p.get("Bereich", {}).get("select")
    if bereich:
        props["Bereich"] = {"select": {"name": bereich["name"]}}

    notiz = p.get("Notiz", {}).get("rich_text", [])
    if notiz:
        props["Notiz"] = {"rich_text": notiz}

    arch = p.get("Archiviert am", {}).get("date")
    if arch:
        props["Archiviert am"] = {"date": arch}

    return props


def main():
    print("Lese alte Archiv-DB...")
    old_entries = query_all(OLD_DB)
    print(f"  {len(old_entries)} Eintraege gefunden")

    print("Lese neue Archiv-DB...")
    new_entries = query_all(NEW_DB)
    print(f"  {len(new_entries)} Eintraege vorhanden")

    existing = set()
    for e in new_entries:
        name = get_title(e)
        arch = get_date(e, "Archiviert am")
        existing.add((name, arch))

    migrated = 0
    skipped = 0
    for entry in old_entries:
        name = get_title(entry)
        arch = get_date(entry, "Archiviert am")
        if (name, arch) in existing:
            skipped += 1
            continue
        props = build_props(entry)
        notion_request("POST", "/pages", {"parent": {"database_id": NEW_DB}, "properties": props})
        existing.add((name, arch))
        migrated += 1

    print(f"Uebersprungen (Duplikate): {skipped}")
    print(f"{migrated} Archiv-Eintraege migriert.")


if __name__ == "__main__":
    main()

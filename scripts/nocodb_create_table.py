#!/usr/bin/env python3
"""Create per-project NocoDB tables."""
import argparse, json, os, sys
from pathlib import Path
import requests

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

NOCODB_API_URL = os.environ.get("NOCODB_API_URL", "")
NOCODB_API_TOKEN = os.environ.get("NOCODB_API_TOKEN", "")
NOCODB_BASE_ID = os.environ.get("NOCODB_BASE_ID", "")
TASKS_TABLE_ID = os.environ.get("NOCODB_TASKS_TABLE_ID", "")


def _headers() -> dict:
    return {"xc-token": NOCODB_API_TOKEN, "Content-Type": "application/json"}


def create_nocodb_table(slug: str, name: str) -> str:
    url = f"{NOCODB_API_URL}/api/v1/db/meta/projects/{NOCODB_BASE_ID}/tables"
    payload = {
        "title": name,
        "columns": [
            {"title": "Name", "uidt": "SingleLineText"},
            {"title": "Status", "uidt": "SingleSelect",
             "dtxp": "'idea','discussed','planned','done'"},
            {"title": "Notiz", "uidt": "LongText"},
        ],
    }
    r = requests.post(url, headers=_headers(), json=payload)
    table_id = r.json().get("id", "")
    if not table_id:
        print(f"⚠️  Table creation failed: {r.json()}", file=sys.stderr)
        sys.exit(1)
    return table_id


def write_table_id_to_registry(slug: str, table_id: str,
                                registry_path: Path | None = None) -> None:
    if registry_path is None:
        hub_dir = Path(os.environ.get("HUB_DIR", ""))
        registry_path = hub_dir / "projects-registry.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    for entry in data:
        if entry.get("slug") == slug:
            entry["nocodb_table_id"] = table_id
            break
    registry_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def create_all_missing() -> None:
    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    registry_path = hub_dir / "projects-registry.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    for entry in data:
        if entry.get("nocodb_table_id"):
            print(f"Skipping {entry['slug']} (already has nocodb_table_id)")
            continue
        slug = entry["slug"]
        name = entry.get("name", slug)
        print(f"Creating table for {slug}...", flush=True)
        table_id = create_nocodb_table(slug, name)
        write_table_id_to_registry(slug, table_id, registry_path=registry_path)
        print(f"  → {table_id}")


def create_habits_table() -> str:
    url = f"{NOCODB_API_URL}/api/v1/db/meta/projects/{NOCODB_BASE_ID}/tables"
    payload = {
        "title": "habits",
        "columns": [
            {"title": "Name", "uidt": "SingleLineText"},
            {"title": "Kategorie", "uidt": "SingleSelect",
             "dtxp": "'Gesundheit','Lernen','Produktivität'"},
            {"title": "Zyklus", "uidt": "SingleLineText"},
            {"title": "Status", "uidt": "SingleSelect",
             "dtxp": "'Not Started','Done'"},
        ],
    }
    r = requests.post(url, headers=_headers(), json=payload)
    table_id = r.json().get("id", "")
    if not table_id:
        print(f"⚠️  Habits table creation failed: {r.json()}", file=sys.stderr)
        sys.exit(1)
    return table_id


def create_focus_table() -> str:
    url = f"{NOCODB_API_URL}/api/v1/db/meta/projects/{NOCODB_BASE_ID}/tables"
    payload = {
        "title": "focus",
        "columns": [
            {"title": "Slug", "uidt": "SingleLineText"},
            {"title": "Updated", "uidt": "Date"},
        ],
    }
    r = requests.post(url, headers=_headers(), json=payload)
    table_id = r.json().get("id", "")
    if not table_id:
        print(f"⚠️  Focus table creation failed: {r.json()}", file=sys.stderr)
        sys.exit(1)
    return table_id


def create_wochenplanung_view() -> str:
    # NocoDB 2026.06.2: view creation API (feature_api_view_v3) is disabled on free plan.
    # Try the API; on failure print manual setup instructions.
    meta_url = f"{NOCODB_API_URL}/api/v1/db/meta/tables/{TASKS_TABLE_ID}"
    r = requests.get(meta_url, headers=_headers())
    columns = r.json().get("columns", [])
    datum_col_id = next((c["id"] for c in columns if c["title"] == "Datum"), "")
    if not datum_col_id:
        print("⚠️  Datum column not found in Tasks table", file=sys.stderr)
        sys.exit(1)

    views_url = f"{NOCODB_API_URL}/api/v1/db/meta/tables/{TASKS_TABLE_ID}/views"
    r = requests.post(views_url, headers=_headers(), json={"title": "Wochenplanung", "type": 0})
    view_id = r.json().get("id", "")
    if not view_id:
        print("ℹ️  View-API nicht verfügbar (NocoDB free plan). Manuelle Einrichtung:")
        print("   1. NocoDB → Tasks-Tabelle → + (View hinzufügen) → Grid View 'Wochenplanung'")
        print("   2. Filter hinzufügen: Datum → is within → this week")
        print("   3. Sortierung: Datum → Aufsteigend")
        print(f"   (Datum-Spalten-ID für API: {datum_col_id})")
        return ""

    filter_url = f"{NOCODB_API_URL}/api/v1/db/meta/views/{view_id}/filters"
    requests.post(filter_url, headers=_headers(), json={
        "fk_column_id": datum_col_id,
        "comparison_op": "isWithin",
        "comparison_sub_op": "thisWeek",
        "logical_op": "and",
    })

    sort_url = f"{NOCODB_API_URL}/api/v1/db/meta/views/{view_id}/sorts"
    requests.post(sort_url, headers=_headers(), json={
        "fk_column_id": datum_col_id,
        "direction": "asc",
    })

    return view_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Create per-project NocoDB tables")
    parser.add_argument("--slug")
    parser.add_argument("--name")
    parser.add_argument("--all", dest="all_projects", action="store_true")
    parser.add_argument("--habits", action="store_true", help="Create habits table")
    parser.add_argument("--focus", action="store_true", help="Create focus table")
    parser.add_argument("--wochenplanung", action="store_true", help="Create Wochenplanung view on Tasks table")
    args = parser.parse_args()

    if not NOCODB_API_URL:
        print("⚠️  NOCODB_API_URL not set", file=sys.stderr)
        sys.exit(1)

    if args.all_projects:
        create_all_missing()
        return

    if args.habits:
        table_id = create_habits_table()
        print(f"habits table_id: {table_id}")
        return

    if args.focus:
        table_id = create_focus_table()
        print(f"focus table_id: {table_id}")
        return

    if args.wochenplanung:
        view_id = create_wochenplanung_view()
        print(f"Wochenplanung view_id: {view_id}")
        return

    if not (args.slug and args.name):
        parser.error("--slug and --name required when not using --all")

    table_id = create_nocodb_table(args.slug, args.name)
    write_table_id_to_registry(args.slug, table_id)
    print(table_id)


if __name__ == "__main__":
    main()

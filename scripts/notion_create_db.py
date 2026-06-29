#!/usr/bin/env python3
"""Create a per-project Notion DB on the Projekte page."""
import argparse, json, os, re, sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from core.claude import run_claude

PROJEKTE_PAGE_ID = os.environ.get("PROJEKTE_PAGE_ID", "")


def create_notion_db(slug: str, name: str) -> str:
    """Create Notion DB for project on Projekte page. Returns DB ID."""
    if not PROJEKTE_PAGE_ID:
        print("⚠️  PROJEKTE_PAGE_ID not set", file=sys.stderr)
        sys.exit(1)
    prompt = (
        f'Projekte-Seite (page_id: {PROJEKTE_PAGE_ID}).\n\n'
        f'Erstelle eine neue Datenbank:\n'
        f'- Titel: "{name}"\n'
        f'- Properties:\n'
        f'  - Name (title)\n'
        f'  - Status (select: idea, discussed, planned, done)\n'
        f'  - Aktiv (checkbox)\n'
        f'  - Position (number)\n'
        f'  - Notiz (rich_text)\n\n'
        f'Antworte NUR mit der neuen Datenbank-ID (UUID-Format, z.B. xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx).'
    )
    response = run_claude(prompt, automated=True)
    m = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', response)
    if not m:
        m = re.search(r'[0-9a-f]{32}', response)
    if not m:
        print(f"⚠️  Could not extract DB ID from: {response!r}", file=sys.stderr)
        sys.exit(1)
    return m.group()


def write_db_id_to_registry(slug: str, db_id: str) -> None:
    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    registry_path = hub_dir / "projects-registry.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    for entry in data:
        if entry.get("slug") == slug:
            entry["notion_db_id"] = db_id
            break
    registry_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def create_all_missing(hub_dir: Path) -> None:
    """Create Notion DBs for all registry projects without notion_db_id."""
    registry_path = hub_dir / "projects-registry.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    for entry in data:
        if entry.get("notion_db_id"):
            print(f"Skipping {entry['slug']} (already has notion_db_id)")
            continue
        slug = entry["slug"]
        name = entry.get("name", slug)
        print(f"Creating DB for {slug}...", flush=True)
        db_id = create_notion_db(slug, name)
        write_db_id_to_registry(slug, db_id)
        print(f"  → {db_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create per-project Notion DB")
    parser.add_argument("--slug")
    parser.add_argument("--name")
    parser.add_argument("--all", dest="all_projects", action="store_true",
                        help="Create DBs for all projects without notion_db_id")
    args = parser.parse_args()
    if args.all_projects:
        hub_dir = Path(os.environ.get("HUB_DIR", ""))
        if not hub_dir or not hub_dir.exists():
            print("⚠️  HUB_DIR not set or not found", file=sys.stderr)
            sys.exit(1)
        create_all_missing(hub_dir)
        return
    if not (args.slug and args.name):
        parser.error("--slug and --name required when not using --all")
    db_id = create_notion_db(args.slug, args.name)
    write_db_id_to_registry(args.slug, db_id)
    print(db_id)


if __name__ == "__main__":
    main()

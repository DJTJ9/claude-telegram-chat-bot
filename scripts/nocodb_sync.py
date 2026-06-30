#!/usr/bin/env python3
"""Sync Dev Skill feature status to NocoDB."""
import argparse, json, os, re, sys
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


def _headers() -> dict:
    return {"xc-token": NOCODB_API_TOKEN, "Content-Type": "application/json"}


def _table_url(table_id: str) -> str:
    return f"{NOCODB_API_URL}/api/v2/tables/{table_id}/records"


def load_registry() -> list:
    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    registry_path = hub_dir / "projects-registry.json"
    if not registry_path.exists():
        return []
    return json.loads(registry_path.read_text(encoding="utf-8"))


def load_nocodb_table_id(slug: str) -> str:
    for entry in load_registry():
        if entry.get("slug") == slug:
            return entry.get("nocodb_table_id", "")
    return ""


def find_row(table_id: str, name: str) -> dict | None:
    params = {"where": f"(Name,eq,{name})", "limit": 1}
    r = requests.get(_table_url(table_id), headers=_headers(), params=params)
    rows = r.json().get("list", [])
    return rows[0] if rows else None


def upsert_feature(table_id: str, name: str, status: str,
                   spec: str = "", plan: str = "") -> None:
    notiz_parts = []
    if spec:
        notiz_parts.append(f"Spec: {spec}")
    if plan:
        notiz_parts.append(f"Plan: {plan}")
    payload: dict = {"Name": name, "Status": status}
    if notiz_parts:
        payload["Notiz"] = "\n".join(notiz_parts)
    row = find_row(table_id, name)
    if row:
        requests.patch(f"{_table_url(table_id)}/{row['Id']}",
                       headers=_headers(), json=payload)
    else:
        requests.post(_table_url(table_id), headers=_headers(), json=payload)


def rebuild_nocodb_table(table_id: str, items: list[tuple[str, str]]) -> None:
    r = requests.get(_table_url(table_id), headers=_headers(),
                     params={"limit": 1000, "fields": "Id"})
    ids = [row["Id"] for row in r.json().get("list", [])]
    if ids:
        requests.delete(_table_url(table_id), headers=_headers(),
                        json=[{"Id": i} for i in ids])
    for status, name in items:
        upsert_feature(table_id, name, status)


def sync_rebuild(slug: str) -> None:
    table_id = load_nocodb_table_id(slug)
    if not table_id:
        print(f"⚠️  No nocodb_table_id for {slug}", file=sys.stderr)
        return
    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    data = parse_status_md(hub_dir / "topics" / slug / "STATUS.md")
    items = [(s, n) for s, n in data["items"]
             if s in ("idea", "discussed", "planned", "done")]
    rebuild_nocodb_table(table_id, items)
    print(f"Rebuilt {slug}: {len(items)} entries")


def sync_dev_to_nocodb(slug: str, feature: str, status: str,
                       spec: str = "", plan: str = "") -> None:
    table_id = load_nocodb_table_id(slug)
    if not table_id:
        print(f"⚠️  No nocodb_table_id for {slug} — skipping", file=sys.stderr)
        return
    upsert_feature(table_id, feature, status, spec=spec, plan=plan)
    print("OK")


def parse_status_md(path: Path) -> dict:
    slug = path.parent.name
    text = path.read_text(encoding="utf-8")
    active = phase = ""
    items = []
    for line in text.splitlines():
        if line.startswith("Active: "):
            val = line[len("Active: "):].strip()
            active = "" if val in ("(none)", "(keine aktive Entwicklung)") else val
        elif line.startswith("Phase: "):
            val = line[len("Phase: "):].strip()
            phase = "" if val == "(none)" else val
        else:
            m = re.match(r"^- \[(\w+)\]\s+(.+)$", line)
            if m:
                items.append((m.group(1), m.group(2).strip()))
    return {"slug": slug, "active": active, "phase": phase, "items": items}


def _update_status_active(path: Path, active: str, conditional: bool = False) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if conditional:
        m = re.search(r'^Active: (.*)$', text, re.MULTILINE)
        if m:
            current = m.group(1).strip()
            if current and current not in ("(none)", "(keine aktive Entwicklung)"):
                return
    display = active if active else "(keine aktive Entwicklung)"
    text = re.sub(r'^Active: .*$', f'Active: {display}', text, flags=re.MULTILINE)
    path.write_text(text, encoding="utf-8")


def _reorder_status_roadmap(path: Path, entries: list[dict]) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    roadmap_idx = text.find("## Roadmap")
    if roadmap_idx == -1:
        return
    after_header = roadmap_idx + len("## Roadmap")
    next_sec = text.find("\n## ", after_header)
    roadmap_text = text[after_header:next_sec] if next_sec != -1 else text[after_header:]
    tail = text[next_sec:] if next_sec != -1 else ""

    existing: dict = {}
    existing_lines: dict = {}
    for line in roadmap_text.splitlines():
        m = re.match(r'^- \[\w+\](\s+)(.+)$', line)
        if m:
            key = m.group(2).strip().lower()
            existing[key] = (m.group(1), m.group(2).strip())
            existing_lines[key] = line

    seen: set = set()
    reordered: list = []
    for entry in entries:
        name = entry.get("name", "").strip()
        key = name.lower()
        if not name or key not in existing:
            continue
        spacing, name_part = existing[key]
        reordered.append(f"- [{entry.get('status', 'idea')}]{spacing}{name_part}")
        seen.add(key)
    for key, line in existing_lines.items():
        if key not in seen:
            reordered.append(line)

    text = text[:after_header] + "\n" + "\n".join(reordered) + "\n" + tail
    path.write_text(text, encoding="utf-8")


def sync_nocodb_to_dev(slug: str) -> None:
    table_id = load_nocodb_table_id(slug)
    if not table_id:
        print(f"⚠️  No nocodb_table_id for {slug} — skipping", file=sys.stderr)
        return
    r = requests.get(_table_url(table_id), headers=_headers(),
                     params={"sort": "Id", "limit": 1000})
    entries = r.json().get("list", [])
    if not entries:
        print(f"nocodb-to-dev: keine Einträge in {slug}.")
        return
    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    non_done = [e for e in entries if e.get("Status") != "done"]
    auto_active = non_done[0]["Name"] if non_done else ""
    _update_status_active(hub_dir / "topics" / slug / "STATUS.md", auto_active, conditional=True)
    _reorder_status_roadmap(hub_dir / "topics" / slug / "STATUS.md",
                            [{"name": e["Name"], "status": e.get("Status", "idea")}
                             for e in non_done])
    print(f"nocodb-to-dev: {slug} — {len(non_done)} Features, aktiv: {auto_active or '(keines)'}")


def sync_all_to_nocodb(hub_dir: Path) -> None:
    for status_path in sorted(hub_dir.glob("topics/*/STATUS.md")):
        data = parse_status_md(status_path)
        if not data["items"] and not data["active"]:
            continue
        table_id = load_nocodb_table_id(data["slug"])
        if not table_id:
            print(f"Skipping {data['slug']} (no nocodb_table_id)")
            continue
        print(f"Syncing {data['slug']}...", flush=True)
        for status, name in data["items"]:
            if status in ("idea", "discussed", "planned", "done"):
                upsert_feature(table_id, name, status)
        print(f"  → {len(data['items'])} features synced")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync feature status to NocoDB")
    parser.add_argument("--slug")
    parser.add_argument("--feature")
    parser.add_argument("--status", choices=["idea", "discussed", "planned", "done"])
    parser.add_argument("--spec", default="")
    parser.add_argument("--plan", default="")
    parser.add_argument("--all", dest="all_projects", action="store_true")
    parser.add_argument("--rebuild", action="store_true",
                        help="Delete all rows and re-insert from STATUS.md (requires --slug)")
    parser.add_argument("--direction", choices=["dev-to-nocodb", "nocodb-to-dev"],
                        default="dev-to-nocodb")
    args = parser.parse_args()

    if not NOCODB_API_URL:
        print("⚠️  NOCODB_API_URL not set — skipping", file=sys.stderr)
        sys.exit(0)

    if args.rebuild:
        if not args.slug:
            parser.error("--rebuild requires --slug")
        sync_rebuild(args.slug)
        return

    if args.all_projects:
        hub_dir = Path(os.environ.get("HUB_DIR", ""))
        sync_all_to_nocodb(hub_dir)
        return

    if args.direction == "dev-to-nocodb":
        if not (args.slug and args.feature and args.status):
            parser.error("dev-to-nocodb requires --slug/--feature/--status")
        sync_dev_to_nocodb(args.slug, args.feature, args.status,
                           spec=args.spec, plan=args.plan)

    elif args.direction == "nocodb-to-dev":
        if not args.slug:
            parser.error("nocodb-to-dev requires --slug")
        sync_nocodb_to_dev(args.slug)


if __name__ == "__main__":
    main()

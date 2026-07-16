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


def _get_all_rows(table_id: str) -> list[dict]:
    r = requests.get(_table_url(table_id), headers=_headers(),
                     params={"limit": 1000})
    return r.json().get("list", [])


# nc_order-Schema: offene Features sortieren umgekehrt-chronologisch (Id-absteigend)
# im Bereich (0, _OPEN_ORDER_BASE) → eine neue Idee (größte Id) bekommt den
# KLEINSTEN Wert und landet damit ganz OBEN, vor allen älteren offenen Rows
# (die live mit dem alten Schema >= _OPEN_ORDER_BASE liegen) und immer vor dem
# done-Block. done-Features bekommen _DONE_ORDER_BASE + Id → stabil ganz ans Ende.
_OPEN_ORDER_BASE = 100_000
_DONE_ORDER_BASE = 1_000_000


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
        patch = {**payload, "Id": row["Id"]}
        if status == "done":
            patch["nc_order"] = str(_DONE_ORDER_BASE + row["Id"])
        requests.patch(_table_url(table_id), headers=_headers(), json=[patch])
    elif status == "done":
        _create_row_at_end(table_id, payload)
    else:
        _create_row_before_done(table_id, payload)


def _open_order(row_id: int) -> str:
    """nc_order für offene Features: streng monoton FALLEND über die Row-Id.

    Die Id ist auto-increment, eine neue Row trägt also die größte Id → kleinster
    Wert im offenen Bereich → landet ganz OBEN im offenen Block (vor den älteren
    Ideen). Bleibt strikt unter _OPEN_ORDER_BASE, damit neue Rows über allen
    bestehenden offenen Rows (die live noch mit dem alten Schema >= _OPEN_ORDER_BASE
    liegen) sortieren, und positiv, damit die Reihenfolge stabil bleibt. nc_order ist
    schreibbar, wird von der v2-API aber nie zurückgegeben — ein Wert allein aus
    der Id (ohne Lesen des Bestands) hält die Ordnung trotzdem deterministisch.
    """
    return str(_OPEN_ORDER_BASE - row_id)


def _create_row_before_done(table_id: str, payload: dict) -> None:
    """POST neue Row (landet zunächst irgendwo), dann PATCH nc_order → ans Ende
    des offenen Blocks, vor den done-Block. Berührt keine anderen Rows."""
    resp = requests.post(_table_url(table_id), headers=_headers(), json=payload)
    new_id = resp.json().get("Id")
    if new_id is not None:
        requests.patch(_table_url(table_id), headers=_headers(),
                       json=[{"Id": new_id, "nc_order": _open_order(new_id)}])


def _create_row_at_end(table_id: str, payload: dict) -> None:
    """POST neue Row, dann nc_order auf großen Wert → Tabellenende (done-Block)."""
    resp = requests.post(_table_url(table_id), headers=_headers(), json=payload)
    new_id = resp.json().get("Id")
    if new_id is not None:
        requests.patch(_table_url(table_id), headers=_headers(),
                       json=[{"Id": new_id, "nc_order": str(_DONE_ORDER_BASE + new_id)}])


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


def regenerate_status_roadmap(path: Path, entries: list[dict]) -> None:
    """Erzeugt den ## Roadmap-Block komplett neu aus `entries` (Reihenfolge =
    NocoDB nc_order). Keine STATUS-only-Zeilen überleben."""
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    roadmap_idx = text.find("## Roadmap")
    if roadmap_idx == -1:
        return
    after_header = roadmap_idx + len("## Roadmap")
    next_sec = text.find("\n## ", after_header)
    tail = text[next_sec:] if next_sec != -1 else ""
    lines = []
    for entry in entries:
        name = entry.get("name", "").strip()
        if not name:
            continue
        status = entry.get("status", "idea")
        lines.append(f"- [{status}]".ljust(14) + name)
    body = "\n" + "\n".join(lines) + "\n" if lines else "\n"
    path.write_text(text[:after_header] + body + tail, encoding="utf-8")


def sync_nocodb_to_dev(slug: str) -> None:
    table_id = load_nocodb_table_id(slug)
    if not table_id:
        print(f"⚠️  No nocodb_table_id for {slug} — skipping", file=sys.stderr)
        return
    r = requests.get(_table_url(table_id), headers=_headers(),
                     params={"limit": 1000})
    entries = r.json().get("list", [])
    if not entries:
        print(f"nocodb-to-dev: keine Einträge in {slug}.")
        return
    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    non_done = [e for e in entries if e.get("Status") != "done"]
    auto_active = non_done[0]["Name"] if non_done else ""
    _update_status_active(hub_dir / "topics" / slug / "STATUS.md", auto_active, conditional=True)
    regenerate_status_roadmap(hub_dir / "topics" / slug / "STATUS.md",
                              [{"name": e.get("Name", ""), "status": e.get("Status", "idea")}
                               for e in entries])
    print(f"nocodb-to-dev: {slug} — {len(entries)} Features, aktiv: {auto_active or '(keines)'}")


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
    parser.add_argument("--status", choices=["idea", "discussed", "planned", "done", "bug"])
    parser.add_argument("--spec", default="")
    parser.add_argument("--plan", default="")
    parser.add_argument("--all", dest="all_projects", action="store_true")
    parser.add_argument("--direction", choices=["dev-to-nocodb", "nocodb-to-dev"],
                        default="dev-to-nocodb")
    args = parser.parse_args()

    if not NOCODB_API_URL:
        print("⚠️  NOCODB_API_URL not set — skipping", file=sys.stderr)
        sys.exit(0)

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

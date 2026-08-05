#!/usr/bin/env python3
"""Sync Dev Skill feature status to NocoDB."""
import argparse, fcntl, json, os, re, sys
from contextlib import contextmanager
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


def _lock_path() -> Path:
    return Path(os.environ.get("WORK_DIR", str(PROJECT_DIR))) / "nocodb_sync.lock"


@contextmanager
def _sync_lock():
    """Globaler flock: serialisiert ALLE Sync-Richtungen über Sessions hinweg
    (H3+H6 — parallele dev-to-nocodb/nocodb-to-dev-Läufe raceten sonst auf
    Roadmap-Blöcken und NocoDB-Rows)."""
    p = _lock_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


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
                   spec: str = "", plan: str = "", notiz: str | None = None) -> None:
    payload: dict = {"Name": name, "Status": status}
    if notiz is not None:
        payload["Notiz"] = notiz
    else:
        notiz_parts = []
        if spec:
            notiz_parts.append(f"Spec: {spec}")
        if plan:
            notiz_parts.append(f"Plan: {plan}")
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


def _move_to_top(table_id: str, row_id: int) -> None:
    """PATCH nc_order = -row_id → Row ganz an den Anfang der Tabelle, über ALLE
    anderen (auch manuell in der UI hochgezogene). Ids steigen monoton, also ist
    -row_id garantiert kleiner als jeder nicht-negative Bestandswert und die
    zuletzt an-Top-gesetzte Row (größte Id) liegt oben. Kein GET nötig (nc_order
    wird von der v2-API nie zurückgegeben)."""
    requests.patch(_table_url(table_id), headers=_headers(),
                   json=[{"Id": row_id, "nc_order": str(-row_id)}])


def sync_dev_to_nocodb(slug: str, feature: str, status: str,
                       spec: str = "", plan: str = "", notiz: str | None = None,
                       top: bool = False) -> None:
    table_id = load_nocodb_table_id(slug)
    if not table_id:
        print(f"⚠️  No nocodb_table_id for {slug} — skipping", file=sys.stderr)
        return
    upsert_feature(table_id, feature, status, spec=spec, plan=plan, notiz=notiz)
    if top:
        row = find_row(table_id, feature)
        if row:
            _move_to_top(table_id, row["Id"])
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


_STATUS_RANK = {"idea": 0, "discussed": 1, "planned": 2, "in_progress": 3, "done": 4}


def _dedup_entries(entries: list[dict]) -> list[dict]:
    """Kollabiert Einträge mit gleichem Namen auf den höchsten Status (done
    gewinnt), an der Position des höchststufigen Vorkommens. Namenlose
    (null/leer) Einträge fallen raus. Macht den Sync robust gegen NocoDB-
    Duplikate und Streu-Records — der Roadmap-Zustand bleibt sauber, egal wie
    die Tabelle manuell verwaltet wird."""
    best: dict[str, tuple[int, int, dict]] = {}
    for i, e in enumerate(entries):
        name = (e.get("name") or "").strip()
        if not name:
            continue
        rank = _STATUS_RANK.get(e.get("status", "idea"), 0)
        cur = best.get(name)
        if cur is None or rank > cur[0]:
            best[name] = (rank, i, e)
    return [e for _, _, e in sorted(best.values(), key=lambda t: t[1])]


def merge_status_roadmap(path: Path, entries: list[dict]) -> None:
    """Projiziert den ## Roadmap-Block aus `entries` (Reihenfolge = NocoDB
    nc_order). Lokale Zeilen ohne NocoDB-Match überleben ans Blockende statt
    gewiped zu werden (Merge statt Wipe, H3); lokale Zeilen mit höherem
    Status gewinnen gegen die NocoDB-Zeile gleichen Namens (H6)."""
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    roadmap_idx = text.find("## Roadmap")
    if roadmap_idx == -1:
        return
    after_header = roadmap_idx + len("## Roadmap")
    next_sec = text.find("\n## ", after_header)
    block = text[after_header:next_sec] if next_sec != -1 else text[after_header:]
    tail = text[next_sec:] if next_sec != -1 else ""

    local_items = []
    for line in block.splitlines():
        m = re.match(r"^- \[(\w+)\]\s+(.+)$", line)
        if m:
            local_items.append((m.group(1), m.group(2).strip()))

    # casefold: eine lokale Zeile, die dasselbe Feature nur anders geschrieben
    # meint (z.B. "prompt injection…" vs. NocoDB "Prompt injection…"), matcht und
    # überlebt NICHT als Zombie-Duplikat — NocoDB bleibt die Wahrheit.
    nocodb_names = {(e.get("name") or "").strip().casefold()
                    for e in entries if (e.get("name") or "").strip()}

    # Rank-Guard (H6): lokale Zeile mit höherem Status gewinnt gegen die
    # NocoDB-Zeile gleichen Namens — kein Status-Downgrade durch den Sync.
    local_rank = {name.casefold(): (_STATUS_RANK.get(status, 0), status)
                  for status, name in local_items}

    lines = []
    for entry in entries:
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        status = entry.get("status", "idea")
        lr = local_rank.get(name.casefold())
        if lr and lr[0] > _STATUS_RANK.get(status, 0):
            status = lr[1]
        lines.append(f"- [{status}]".ljust(14) + name)

    for status, name in local_items:
        if name.casefold() not in nocodb_names:
            lines.append(f"- [{status}]".ljust(14) + name)

    body = "\n" + "\n".join(lines) + "\n" if lines else "\n"
    path.write_text(text[:after_header] + body + tail, encoding="utf-8")


def reorder_vision_roadmap(path: Path, entries: list[dict]) -> None:
    """`- ✅ …`-Zeilen bleiben positionsfest. Offene Slots (`- [status] …`) werden
    mit den offenen NocoDB-Features (Status != done) in NocoDB-Order befüllt —
    per Namens-Match gegen die bereits in VISION vorhandenen offenen Zeilen.
    NocoDB-Features ohne VISION-Match (nie über /dev idea erfasst) landen ans
    Blockende statt einen Slot zu belegen."""
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    roadmap_idx = text.find("## Roadmap")
    if roadmap_idx == -1:
        return
    after_header = roadmap_idx + len("## Roadmap")
    next_sec = text.find("\n## ", after_header)
    block = text[after_header:next_sec] if next_sec != -1 else text[after_header:]
    tail = text[next_sec:] if next_sec != -1 else ""

    slots = []
    open_names = set()
    for line in block.splitlines():
        if not line.strip():
            continue
        if line.startswith("- ✅"):
            slots.append(("done", line))
        else:
            m = re.match(r"^- \[(\w+)\]\s+(.+)$", line)
            if m:
                slots.append(("open", None))
                open_names.add(m.group(2).strip())

    open_entries = [e for e in entries if e.get("status") != "done"]
    matched = [e for e in open_entries if (e.get("name") or "").strip() in open_names]
    unmatched = [e for e in open_entries if (e.get("name") or "").strip() not in open_names]

    queue = list(matched)
    new_lines = []
    for kind, val in slots:
        if kind == "done":
            new_lines.append(val)
        elif queue:
            entry = queue.pop(0)
            name = (entry.get("name") or "").strip()
            status = entry.get("status", "idea")
            new_lines.append(f"- [{status}]".ljust(14) + name)
    for entry in queue:
        name = (entry.get("name") or "").strip()
        status = entry.get("status", "idea")
        new_lines.append(f"- [{status}]".ljust(14) + name)
    for entry in unmatched:
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        status = entry.get("status", "idea")
        new_lines.append(f"- [{status}]".ljust(14) + name)

    body = "\n" + "\n".join(new_lines) + "\n" if new_lines else "\n"
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
    entries = _dedup_entries([{"name": e.get("Name", ""), "status": e.get("Status", "idea")}
                              for e in entries])
    non_done = [e for e in entries if e["status"] != "done"]
    auto_active = non_done[0]["name"] if non_done else ""
    _update_status_active(hub_dir / "topics" / slug / "STATUS.md", auto_active, conditional=True)
    merge_status_roadmap(hub_dir / "topics" / slug / "STATUS.md", entries)
    print(f"nocodb-to-dev: {slug} — {len(entries)} Features, aktiv: {auto_active or '(keines)'}")


def sync_nocodb_reorder(slug: str) -> None:
    table_id = load_nocodb_table_id(slug)
    if not table_id:
        print(f"⚠️  No nocodb_table_id for {slug} — skipping", file=sys.stderr)
        return
    rows = _get_all_rows(table_id)
    if not rows:
        print(f"nocodb-reorder: keine Einträge in {slug}.")
        return
    entries = _dedup_entries([{"name": r.get("Name", ""), "status": r.get("Status", "idea")}
                              for r in rows])
    non_done = [e for e in entries if e["status"] != "done"]
    auto_active = non_done[0]["name"] if non_done else ""
    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    status_path = hub_dir / "topics" / slug / "STATUS.md"
    vision_path = hub_dir / "topics" / slug / "VISION.md"
    _update_status_active(status_path, auto_active, conditional=False)
    merge_status_roadmap(status_path, entries)
    reorder_vision_roadmap(vision_path, entries)
    print(f"nocodb-reorder: {slug} — {len(entries)} Features, aktiv: {auto_active or '(keines)'}")


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
    parser.add_argument("--notiz", default=None)
    parser.add_argument("--all", dest="all_projects", action="store_true")
    parser.add_argument("--top", action="store_true",
                        help="Row nach dem Sync ganz an den Tabellenanfang setzen")
    parser.add_argument("--direction", choices=["dev-to-nocodb", "nocodb-to-dev", "nocodb-reorder"],
                        default="dev-to-nocodb")
    args = parser.parse_args()

    if not NOCODB_API_URL:
        print("⚠️  NOCODB_API_URL not set — skipping", file=sys.stderr)
        sys.exit(0)

    with _sync_lock():
        if args.all_projects:
            hub_dir = Path(os.environ.get("HUB_DIR", ""))
            sync_all_to_nocodb(hub_dir)
            return

        if args.direction == "dev-to-nocodb":
            if not (args.slug and args.feature and args.status):
                parser.error("dev-to-nocodb requires --slug/--feature/--status")
            sync_dev_to_nocodb(args.slug, args.feature, args.status,
                               spec=args.spec, plan=args.plan, notiz=args.notiz, top=args.top)

        elif args.direction == "nocodb-to-dev":
            if not args.slug:
                parser.error("nocodb-to-dev requires --slug")
            sync_nocodb_to_dev(args.slug)

        elif args.direction == "nocodb-reorder":
            if not args.slug:
                parser.error("nocodb-reorder requires --slug")
            sync_nocodb_reorder(args.slug)


if __name__ == "__main__":
    main()

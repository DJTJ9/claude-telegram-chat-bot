#!/usr/bin/env python3
"""Sync Dev Skill feature status to Notion Arbeitsprojekte DB."""
import argparse, json, os, re, sys, time
from datetime import datetime
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

ARBEIT_DB_ID = os.environ.get("ARBEIT_DB_ID", "")

_STATUS_MAP = {
    "idea":      ("Idee",      "Offen"),
    "discussed": ("Discussed", "Offen"),
    "planned":   ("Planned",   "In Arbeit"),
    "done":      ("Done",      "Fertig"),
}


def load_notion_db_id(slug: str) -> str:
    """Read notion_db_id for slug from projects-registry.json."""
    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    registry_path = hub_dir / "projects-registry.json"
    if not registry_path.exists():
        return ""
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    for entry in data:
        if entry.get("slug") == slug:
            return entry.get("notion_db_id", "")
    return ""


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


def _extract_json_array(text: str) -> list:
    """Extract first JSON array from Claude's response text."""
    m = re.search(r'\[.*?\]', text, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return []


def _append_ideas_to_file(path: Path, ideas: list[str]) -> list[str]:
    """Append new [idea] lines to file's Roadmap section. Returns added names."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    existing = {
        m.group(1).lower().strip()
        for m in re.finditer(r'^- \[\w+\]\s+(.+)$', text, re.MULTILINE)
    }
    to_add = [n for n in ideas if n.lower().strip() not in existing]
    if not to_add:
        return []
    new_lines = "\n".join(f"- [idea]      {n}" for n in to_add)
    roadmap_idx = text.find("## Roadmap")
    if roadmap_idx == -1:
        text = text.rstrip() + f"\n\n## Roadmap\n{new_lines}\n"
    else:
        next_sec = text.find("\n## ", roadmap_idx + len("## Roadmap"))
        if next_sec == -1:
            text = text.rstrip() + "\n" + new_lines + "\n"
        else:
            text = text[:next_sec] + "\n" + new_lines + text[next_sec:]
    path.write_text(text, encoding="utf-8")
    return to_add


def sync_notion_to_dev(slug: str | None) -> None:
    """Pull Idee-entries from Notion and append to STATUS.md + VISION.md."""
    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    if not hub_dir or not hub_dir.exists():
        print("⚠️  HUB_DIR not set or not found", file=sys.stderr)
        sys.exit(1)

    slug_filter = f" mit Projekt={slug}" if slug else ""
    prompt = (
        f"Arbeitsprojekte-Datenbank (data_source_id: {ARBEIT_DB_ID}).\n\n"
        f"Suche alle Einträge mit Typ=Idee{slug_filter}.\n"
        "Antworte NUR mit einem JSON-Array. Format:\n"
        '[{"name": "Featurename", "projekt": "slug-oder-leer"}]\n'
        "Falls keine Einträge gefunden: []"
    )

    response = run_claude(prompt, automated=True)
    entries = _extract_json_array(response)
    if not entries:
        print("notion-to-dev: keine neuen Ideen gefunden.")
        return

    by_slug: dict[str, list[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        proj = str(entry.get("projekt", slug or "")).strip()
        if not name:
            continue
        if slug and proj and proj != slug:
            continue
        by_slug.setdefault(proj or "general", []).append(name)

    total_added = 0
    for proj_slug, names in by_slug.items():
        status_path = hub_dir / "topics" / proj_slug / "STATUS.md"
        vision_path = hub_dir / "topics" / proj_slug / "VISION.md"
        added = _append_ideas_to_file(status_path, names)
        _append_ideas_to_file(vision_path, names)
        if added:
            total_added += len(added)
            print(f"{proj_slug}: {len(added)} neue Ideen — {', '.join(added)}")

    if total_added == 0:
        print("notion-to-dev: alle Ideen bereits bekannt.")


def build_sync_prompt(slug: str, feature: str, status: str,
                      spec: str | None = None, plan: str | None = None,
                      db_id: str = "") -> str:
    phase, notion_status = _STATUS_MAP[status]
    extras = f"\n   - Projekt: {slug}"
    if spec:
        extras += f"\n   - Spec: {spec}"
    if plan:
        extras += f"\n   - Plan: {plan}"
    update_extras = f", Projekt={slug}"
    if spec:
        update_extras += f", Spec={spec}"
    if plan:
        update_extras += f", Plan={plan}"
    return f"""Arbeitsprojekte-Datenbank (data_source_id: {db_id}).

1. Suche Eintrag mit Typ=Feature und Name="{feature}".
2. Falls gefunden: Aktualisiere Phase={phase}, Status={notion_status}{update_extras}.
3. Falls nicht gefunden: Lege neuen Eintrag an:
   - Name: {feature}
   - Typ: Feature
   - Phase: {phase}
   - Status: {notion_status}{extras}
   - Elterneintrag: Suche Projekt mit Name={slug}, verknüpfe falls vorhanden.

Antworte nur mit "OK" wenn erfolgreich."""


def build_bulk_sync_prompt(slug: str, items: list, active: str, phase: str,
                            db_id: str) -> str:
    lines = [f"Arbeitsprojekte-Datenbank (data_source_id: {db_id}).", ""]
    step = 1
    if active:
        lines += [
            f'{step}. Suche Eintrag mit Typ=Projekt und Name="{slug}".',
            f'   Falls gefunden: Setze Notiz="Aktiv: {active} | Phase: {phase}".',
            f'   Falls nicht gefunden: Lege neuen Eintrag an: Name={slug}, Typ=Projekt,'
            f' Notiz="Aktiv: {active} | Phase: {phase}".',
            "",
        ]
        step += 1
    for status, name in items:
        if status not in _STATUS_MAP:
            continue
        notion_phase, notion_status = _STATUS_MAP[status]
        lines += [
            f'{step}. Suche Eintrag mit Typ=Feature und Name="{name}".',
            f'   Falls gefunden: Aktualisiere Phase={notion_phase}, Status={notion_status}, Projekt={slug}.',
            f'   Falls nicht gefunden: Lege neuen Eintrag an: Name={name}, Typ=Feature,'
            f' Phase={notion_phase}, Status={notion_status}, Projekt={slug}.',
            "",
        ]
        step += 1
    lines.append('Antworte nur mit "OK" wenn erfolgreich.')
    return "\n".join(lines)


def build_per_project_sync_prompt(slug: str, feature: str, status: str,
                                   spec: str | None, plan: str | None,
                                   db_id: str) -> str:
    """Prompt for per-project Notion DB (schema: Name, Status, Aktiv, Position, Notiz)."""
    done_block = ""
    if status == "done":
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        position = 2_000_000_000 - int(time.time())
        done_block = (
            f'\n   - Notiz: "Abgeschlossen: {timestamp}"'
            f"\n   - Position: {position}"
            f"\n   - Aktiv: false"
        )
    notiz_extras = ""
    if spec:
        notiz_extras += f"\n   - Notiz-Ergänzung: Spec: {spec}"
    if plan:
        notiz_extras += f"\n   - Notiz-Ergänzung: Plan: {plan}"
    new_position_block = "" if status == "done" else (
        "\n   - Position: (ermittle aktuellen Maximalwert des Position-Felds in der DB,"
        " setze Position = Max + 100; falls keine Einträge vorhanden: Position = 100)"
    )
    return (
        f"Datenbank (data_source_id: {db_id}).\n\n"
        f'1. Suche Eintrag mit Name="{feature}".\n'
        f"2. Falls gefunden: Aktualisiere Status={status}{done_block}.\n"
        f"3. Falls nicht gefunden: Lege neuen Eintrag an:\n"
        f"   - Name: {feature}\n"
        f"   - Status: {status}{done_block}{new_position_block}{notiz_extras}\n\n"
        f'Antworte nur mit "OK" wenn erfolgreich.'
    )


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


def _reorder_vision_roadmap(path: Path, ordered_names: list[str]) -> None:
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

    existing: dict[str, str] = {}
    for line in roadmap_text.splitlines():
        m = re.match(r'^(- \[\w+\]\s+)(.+)$', line)
        if m:
            existing[m.group(2).strip().lower()] = line

    seen: set[str] = set()
    reordered: list[str] = []
    for name in ordered_names:
        key = name.lower()
        if key in existing:
            reordered.append(existing[key])
            seen.add(key)
    for key, line in existing.items():
        if key not in seen:
            reordered.append(line)

    text = text[:after_header] + "\n" + "\n".join(reordered) + "\n" + tail
    path.write_text(text, encoding="utf-8")


_NOTION_TO_DEV_STATUS = {
    "idea": "idea",
    "discussed": "discussed",
    "planned": "planned",
    "done": "done",
}


def _reorder_status_roadmap(path: Path, entries: list[dict]) -> None:
    """Reorder STATUS.md Roadmap section by Notion entry order, updating status tags."""
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

    existing: dict[str, tuple[str, str]] = {}
    existing_lines: dict[str, str] = {}
    for line in roadmap_text.splitlines():
        m = re.match(r'^- \[\w+\](\s+)(.+)$', line)
        if m:
            key = m.group(2).strip().lower()
            existing[key] = (m.group(1), m.group(2).strip())
            existing_lines[key] = line

    seen: set[str] = set()
    reordered: list[str] = []
    for entry in entries:
        name = entry.get("name", "").strip()
        key = name.lower()
        if not name or key not in existing:
            continue
        dev_status = _NOTION_TO_DEV_STATUS.get(entry.get("status", "idea"), "idea")
        spacing, name_part = existing[key]
        reordered.append(f"- [{dev_status}]{spacing}{name_part}")
        seen.add(key)

    for key, line in existing_lines.items():
        if key not in seen:
            reordered.append(line)

    text = text[:after_header] + "\n" + "\n".join(reordered) + "\n" + tail
    path.write_text(text, encoding="utf-8")


def sync_feature_order_from_notion(slug: str) -> None:
    """Pull feature order + active item from per-project DB. Update Vision.md + STATUS.md."""
    db_id = load_notion_db_id(slug)
    if not db_id:
        print(f"⚠️  No notion_db_id for {slug} — skipping notion-to-dev", file=sys.stderr)
        return

    prompt = (
        f"Datenbank (data_source_id: {db_id}).\n\n"
        f"Lese alle Einträge, sortiert nach Position (aufsteigend).\n"
        f"Antworte NUR mit einem JSON-Array. Format:\n"
        '[{"name": "...", "status": "idea|discussed|planned|done"}]\n'
        "Falls keine Einträge: []"
    )
    response = run_claude(prompt, automated=True)
    entries = _extract_json_array(response)
    if not entries:
        print(f"notion-to-dev: keine Einträge in {slug} DB.")
        return

    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    auto_active = next((e["name"] for e in entries if e.get("status") != "done"), "")
    _update_status_active(hub_dir / "topics" / slug / "STATUS.md", auto_active, conditional=True)
    _reorder_vision_roadmap(hub_dir / "topics" / slug / "VISION.md",
                            [e["name"] for e in entries])
    _reorder_status_roadmap(hub_dir / "topics" / slug / "STATUS.md", entries)
    print(f"notion-to-dev: {slug} — {len(entries)} Features, aktiv: {active or '(keines)'}")


def sync_reorder_to_notion(slug: str) -> None:
    """Read STATUS.md Roadmap order and update Notion Position for all non-done features."""
    db_id = load_notion_db_id(slug)
    if not db_id:
        print(f"⚠️  No notion_db_id for {slug} — skipping reorder", file=sys.stderr)
        return

    hub_dir = Path(os.environ.get("HUB_DIR", ""))
    status_path = hub_dir / "topics" / slug / "STATUS.md"
    data = parse_status_md(status_path)

    non_done = [(st, name) for st, name in data["items"] if st != "done"]
    if not non_done:
        print(f"reorder: no non-done items for {slug}")
        return

    lines = [f"Datenbank (data_source_id: {db_id}).", ""]
    for i, (_, name) in enumerate(non_done):
        position = (i + 1) * 100
        lines += [
            f'{i + 1}. Suche Eintrag mit Name="{name}".',
            f"   Falls gefunden: Setze Position={position}.",
            "",
        ]
    lines.append('Antworte nur mit "OK" wenn fertig.')
    result = run_claude("\n".join(lines), automated=True)
    print(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync feature to Notion Arbeitsprojekte DB")
    parser.add_argument("--slug")
    parser.add_argument("--feature")
    parser.add_argument("--status", choices=list(_STATUS_MAP))
    parser.add_argument("--spec", default=None)
    parser.add_argument("--plan", default=None)
    parser.add_argument("--all", dest="all_projects", action="store_true",
                        help="Sync all projects from HUB_DIR/topics/*/STATUS.md")
    parser.add_argument(
        "--direction",
        choices=["dev-to-notion", "notion-to-dev", "both"],
        default="dev-to-notion",
    )
    parser.add_argument("--reorder", action="store_true",
                        help="Sync STATUS.md roadmap order → Notion Position")
    args = parser.parse_args()

    if args.reorder:
        if not args.slug:
            parser.error("--reorder requires --slug")
        sync_reorder_to_notion(args.slug)
        return

    if not ARBEIT_DB_ID:
        print("⚠️  ARBEIT_DB_ID not set — skipping Notion sync", file=sys.stderr)
        sys.exit(0)

    direction = args.direction

    if args.all_projects:
        if direction not in ("dev-to-notion", "both"):
            parser.error("--all only supported with direction=dev-to-notion or both")
        hub_dir = Path(os.environ.get("HUB_DIR", ""))
        if not hub_dir or not hub_dir.exists():
            print("⚠️  HUB_DIR not set or not found", file=sys.stderr)
            sys.exit(1)
        for status_path in sorted(hub_dir.glob("topics/*/STATUS.md")):
            data = parse_status_md(status_path)
            if not data["items"] and not data["active"]:
                continue
            print(f"Syncing {data['slug']}...", flush=True)
            prompt = build_bulk_sync_prompt(
                data["slug"], data["items"], data["active"], data["phase"], ARBEIT_DB_ID
            )
            result = run_claude(prompt, automated=True)
            print(result)
        return

    if direction in ("dev-to-notion", "both"):
        if not (args.slug and args.feature and args.status):
            parser.error("dev-to-notion requires --slug/--feature/--status")
        per_project_db_id = load_notion_db_id(args.slug)
        if per_project_db_id:
            prompt = build_per_project_sync_prompt(
                args.slug, args.feature, args.status, args.spec, args.plan, per_project_db_id
            )
        else:
            db_id = ARBEIT_DB_ID
            if not db_id:
                print("⚠️  No notion_db_id and ARBEIT_DB_ID not set — skipping", file=sys.stderr)
                sys.exit(0)
            prompt = build_sync_prompt(args.slug, args.feature, args.status,
                                       args.spec, args.plan, db_id)
        result = run_claude(prompt, automated=True)
        print(result)

    if direction in ("notion-to-dev", "both"):
        sync_feature_order_from_notion(args.slug or "")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Sync Dev Skill feature status to Notion Arbeitsprojekte DB."""
import argparse, os, re, sys
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync feature to Notion Arbeitsprojekte DB")
    parser.add_argument("--slug")
    parser.add_argument("--feature")
    parser.add_argument("--status", choices=list(_STATUS_MAP))
    parser.add_argument("--spec", default=None)
    parser.add_argument("--plan", default=None)
    parser.add_argument("--all", dest="all_projects", action="store_true",
                        help="Sync all projects from HUB_DIR/topics/*/STATUS.md")
    args = parser.parse_args()

    if not ARBEIT_DB_ID:
        print("⚠️  ARBEIT_DB_ID not set — skipping Notion sync", file=sys.stderr)
        sys.exit(0)

    if args.all_projects:
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

    if not (args.slug and args.feature and args.status):
        parser.error("Either --all or all of --slug/--feature/--status required")

    prompt = build_sync_prompt(args.slug, args.feature, args.status,
                               args.spec, args.plan, ARBEIT_DB_ID)
    result = run_claude(prompt, automated=True)
    print(result)


if __name__ == "__main__":
    main()

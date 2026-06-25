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
    extras = ""
    if spec:
        extras += f"\n   - Spec: {spec}"
    if plan:
        extras += f"\n   - Plan: {plan}"
    update_extras = ""
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync feature to Notion Arbeitsprojekte DB")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--status", required=True, choices=list(_STATUS_MAP))
    parser.add_argument("--spec", default=None)
    parser.add_argument("--plan", default=None)
    args = parser.parse_args()

    if not ARBEIT_DB_ID:
        print("⚠️  ARBEIT_DB_ID not set — skipping Notion sync", file=sys.stderr)
        sys.exit(0)

    prompt = build_sync_prompt(args.slug, args.feature, args.status,
                               args.spec, args.plan, ARBEIT_DB_ID)
    result = run_claude(prompt, automated=True)
    print(result)


if __name__ == "__main__":
    main()

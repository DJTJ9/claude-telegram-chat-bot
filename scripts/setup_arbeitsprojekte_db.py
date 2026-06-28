#!/usr/bin/env python3
"""Reset and rebuild the Notion Arbeitsprojekte DB from hub STATUS.md files."""
import os
import subprocess
import sys
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

from core.claude import run_claude  # noqa: E402

ARBEIT_DB_ID = os.environ.get("ARBEIT_DB_ID", "")


def build_setup_prompt(db_id: str) -> str:
    return (
        f"Arbeitsprojekte-Datenbank (data_source_id: {db_id}).\n\n"
        "1. Stelle sicher, dass folgende Properties existieren (erstelle falls fehlend):\n"
        "   - Name (title)\n"
        "   - Typ (select: Projekt, Feature, Idee)\n"
        "   - Phase (select: Idee, Discussed, Planned, Done)\n"
        "   - Status (select: Offen, In Arbeit, Fertig)\n"
        "   - Projekt (select) — Werte sind Slugs wie telegram-bot-army, shopping-navigator\n"
        "   - Notiz (rich_text)\n\n"
        "2. Archiviere alle bestehenden Eintraege in der DB.\n\n"
        "Antworte nur mit 'OK' wenn fertig."
    )


def main() -> None:
    if not ARBEIT_DB_ID:
        print("⚠️  ARBEIT_DB_ID not set — skipping", file=sys.stderr)
        sys.exit(0)

    print("Step 1: Setup properties + archive existing entries...", flush=True)
    prompt = build_setup_prompt(ARBEIT_DB_ID)
    result = run_claude(prompt, automated=True)
    print(result)

    print("Step 2: Repopulate from STATUS.md files...", flush=True)
    notion_sync = str(PROJECT_DIR / "scripts" / "notion_sync.py")
    subprocess.run([sys.executable, notion_sync, "--all"], check=True)


if __name__ == "__main__":
    main()

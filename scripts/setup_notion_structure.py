#!/usr/bin/env python3
"""One-time migration script: creates Notion sub-page structure for Organizer."""
import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from core.claude import run_claude


def _extract_json(response: str) -> str:
    """Extracts the first JSON object from a response that may contain backticks or prose."""
    start = response.find("{")
    end = response.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in response: {response!r}")
    return response[start:end + 1]


SUB_PAGES = [
    ("📅 Tagesplanung", "tagesplanung"),
    ("📆 Wochenplanung", "wochenplanung"),
    ("🗓 Monatsübersicht", "monatsübersicht"),
    ("🗂 Projekte", "projekte"),
    ("🏋 Sport Challenges", "sport-challenges"),
    ("💡 Ideensammlung", "ideensammlung"),
    ("🗃 Archiv", "archiv"),
]

OLD_TAGESORGANIZER_ID = "c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0"
OLD_SPORT_CHALLENGES_ID = "fd7c0b6b-4a77-4a67-88ea-d7d0a093ed42"
OLD_ARCHIV_ID = "abb5abd8-e320-4796-bbf6-941feb9007b9"


def find_organizer_page() -> str:
    prompt = """Suche in Notion nach der Hauptseite mit dem Titel "Organizer" (oder ähnlich: "Tagesorganizer", "Organizer-Hub").
Gib die page_id dieser Seite zurück.
Antworte NUR mit JSON: {"page_id": "<32-stellige-hex-id-ohne-bindestriche>"}"""
    response = run_claude(prompt, automated=True)
    return json.loads(_extract_json(response))["page_id"]


DB_DEFINITIONS = [
    {
        "name": "tasks",
        "sub_page": "tagesplanung",
        "title": "Tasks",
        "properties": (
            '- Name (title)\n'
            '- Status (select: "Not started", "In progress", "Done")\n'
            '- Priorität (select: "Hoch", "Mittel", "Niedrig")\n'
            '- Datum (date)\n'
            '- Bereich (select: "Arbeit", "Privat", "Lernen", "Gesundheit")\n'
            '- Notiz (rich_text)\n'
            '- Zyklus (rich_text)'
        ),
    },
    {
        "name": "projekte",
        "sub_page": "projekte",
        "title": "Projekte",
        "properties": (
            '- Name (title)\n'
            '- Status (select: "Offen", "In Arbeit", "Abgeschlossen")\n'
            '- Priorität (select: "Hoch", "Mittel", "Niedrig")\n'
            '- Notiz (rich_text)'
        ),
    },
    {
        "name": "sport-challenges",
        "sub_page": "sport-challenges",
        "title": "Sport Challenges",
        "properties": (
            '- Name (title)\n'
            '- Kategorie (select)\n'
            '- Status (select: "Not Started", "Done")'
        ),
    },
    {
        "name": "ideensammlung",
        "sub_page": "ideensammlung",
        "title": "Ideensammlung",
        "properties": (
            '- Name (title)\n'
            '- Kategorie (select)\n'
            '- Notiz (rich_text)'
        ),
    },
    {
        "name": "archiv",
        "sub_page": "archiv",
        "title": "Archiv",
        "properties": (
            '- Name (title)\n'
            '- Status (select)\n'
            '- Priorität (select)\n'
            '- Datum (date)\n'
            '- Bereich (select)\n'
            '- Notiz (rich_text)\n'
            '- Archiviert am (date)'
        ),
    },
]


def create_databases(sub_page_ids: dict[str, str]) -> dict[str, str]:
    """Creates DBs on sub-pages. Returns db_name→db_id."""
    result = {}
    for db in DB_DEFINITIONS:
        parent_id = sub_page_ids[db["sub_page"]]
        prompt = (
            f'Erstelle eine neue Datenbank in Notion auf der Seite {parent_id}:\n'
            f'- Titel: "{db["title"]}"\n'
            f'- Properties:\n{db["properties"]}\n\n'
            f'Falls eine Datenbank mit diesem Titel auf dieser Seite bereits existiert, gib deren ID zurück.\n'
            f'Antworte NUR mit JSON: {{"database_id": "<32-stellige-hex-id-ohne-bindestriche>"}}'
        )
        response = run_claude(prompt, automated=True)
        data = json.loads(_extract_json(response))
        result[db["name"]] = data["database_id"]
        print(f"✅ DB '{db['title']}': {data['database_id']}")
    return result


def create_sub_pages(organizer_page_id: str) -> dict[str, str]:
    """Creates 7 sub-pages under organizer_page_id. Returns slug→page_id."""
    result = {}
    for title, slug in SUB_PAGES:
        prompt = f"""Erstelle eine neue Seite in Notion:
- Titel: "{title}"
- Parent-Seite: page_id {organizer_page_id}

Falls eine Seite mit diesem Titel unter diesem Parent bereits existiert, gib deren ID zurück (kein Duplikat erstellen).
Antworte NUR mit JSON: {{"page_id": "<32-stellige-hex-id-ohne-bindestriche>"}}"""
        response = run_claude(prompt, automated=True)
        data = json.loads(_extract_json(response))
        result[slug] = data["page_id"]
        print(f"✅ '{title}': {data['page_id']}")
    return result


def migrate_data(new_db_ids: dict[str, str]) -> None:
    """Migrates data from old DBs to new DBs. 3 migrations: Tasks, Sport, Archiv."""
    migrations = [
        (
            "Tagesorganizer → neue Tasks-DB",
            f"""Migriere alle Einträge von der alten Datenbank (data_source_id: {OLD_TAGESORGANIZER_ID})
in die neue Tasks-Datenbank (data_source_id: {new_db_ids['tasks']}).
Für jeden Eintrag: Erstelle identischen Eintrag mit allen Properties (Name, Status, Priorität, Datum, Bereich, Notiz, Zyklus).
Überspringe Einträge bei denen Name + Datum in der neuen DB bereits existieren.
Antworte mit: "<N> Einträge migriert." """,
        ),
        (
            "Sport Challenges → neue Sport-DB",
            f"""Migriere alle Einträge von der alten Sport-Challenges-Datenbank (data_source_id: {OLD_SPORT_CHALLENGES_ID})
in die neue Sport-Challenges-Datenbank (data_source_id: {new_db_ids['sport-challenges']}).
Für jeden Eintrag: Erstelle identischen Eintrag (Name, Kategorie, Status).
Überspringe Duplikate (Name gleich).
Antworte mit: "<N> Sport Challenges migriert." """,
        ),
        (
            "Archiv → neues Archiv",
            f"""Migriere alle Einträge von der alten Archiv-Datenbank (data_source_id: {OLD_ARCHIV_ID})
in die neue Archiv-Datenbank (data_source_id: {new_db_ids['archiv']}).
Für jeden Eintrag: Erstelle identischen Eintrag (Name, Status, Priorität, Datum, Bereich, Notiz, Archiviert am).
Überspringe Duplikate (Name + Archiviert am gleich).
Antworte mit: "<N> Archiv-Einträge migriert." """,
        ),
    ]
    for label, prompt in migrations:
        result = run_claude(prompt, automated=True)
        print(f"✅ {label}: {result.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup Notion Organizer structure")
    parser.add_argument("--page-id", help="Organizer main page ID (auto-discovered if not set)")
    args = parser.parse_args()

    print("🔍 Schritt 1: Organizer-Seite finden...")
    organizer_id = args.page_id or find_organizer_page()
    print(f"   page_id: {organizer_id}")

    print("\n📁 Schritt 2: Sub-Seiten erstellen...")
    sub_page_ids = create_sub_pages(organizer_id)

    print("\n🗄️ Schritt 3: Datenbanken erstellen...")
    new_db_ids = create_databases(sub_page_ids)

    print("\n📦 Schritt 4: Daten migrieren...")
    migrate_data(new_db_ids)

    print("\n" + "=" * 60)
    print("✅ Fertig. Neue DB-IDs für organizer.py + CLAUDE.md:")
    print("=" * 60)
    for name, db_id in new_db_ids.items():
        print(f"  {name}: {db_id}")


if __name__ == "__main__":
    main()

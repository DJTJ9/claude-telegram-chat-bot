#!/usr/bin/env python3
"""One-time migration script: creates Notion sub-page structure for Organizer."""
import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from core.claude import run_claude

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
    return json.loads(response.strip())["page_id"]


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
        data = json.loads(response.strip())
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
        data = json.loads(response.strip())
        result[slug] = data["page_id"]
        print(f"✅ '{title}': {data['page_id']}")
    return result

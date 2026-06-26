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

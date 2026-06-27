#!/usr/bin/env python3
"""Seeds Notion databases with example data."""
import datetime
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from core.claude import run_claude

TASKS_DB_ID      = "38b4bba29c5581a7bd94cef1b0cc6c58"
SPORT_DB_ID      = "38b4bba29c5581c88f49c67bb85f78c0"
BACKLOG_DB_ID    = "0cb18d17-cf70-413d-b29d-adb4675db614"
LERNTHEMEN_DB_ID = "5a76447f-2b0a-4f6b-81bb-853f39aa04bb"


def seed_tasks(today: str) -> None:
    entries = "\n".join([
        f'- "Sport-Einheit planen" | Priorität: Hoch    | Bereich: Gesundheit | Datum: {today}',
        f'- "E-Mails prüfen"       | Priorität: Mittel  | Bereich: Arbeit     | Datum: {today}',
        f'- "Einkaufsliste machen" | Priorität: Niedrig | Bereich: Privat     | Datum: {today}',
        f'- "Python lernen"        | Priorität: Mittel  | Bereich: Lernen     | Datum: {today}',
        f'- "Tagebuch schreiben"   | Priorität: Niedrig | Bereich: Privat     | Datum: {today}',
    ])
    prompt = (
        f'Erstelle folgende Einträge in der Notion-Datenbank {TASKS_DB_ID} (Tasks DB):\n'
        f'{entries}\n'
        f'Für jeden Eintrag: Status = "Not started".\n'
        f'Überspringe Einträge, bei denen Name + Datum bereits existieren.\n'
        f'Antworte mit: "<N> Tasks erstellt."'
    )
    result = run_claude(prompt, automated=True)
    print(f"✅ Tasks: {result.strip()}")


def seed_sport() -> None:
    entries = "\n".join([
        '- "5km laufen"           | Kategorie: Laufen | Status: Not Started',
        '- "10-Minuten-Lauf"      | Kategorie: Laufen | Status: Not Started',
        '- "20 Liegestütze"       | Kategorie: Kraft  | Status: Not Started',
        '- "Plank 60s"            | Kategorie: Kraft  | Status: Not Started',
        '- "Morgenroutine Dehnen" | Kategorie: Dehnen | Status: Not Started',
        '- "Yoga 15min"           | Kategorie: Dehnen | Status: Not Started',
    ])
    prompt = (
        f'Erstelle folgende Einträge in der Notion-Datenbank {SPORT_DB_ID} (Sport Challenges DB):\n'
        f'{entries}\n'
        f'Überspringe Einträge, bei denen Name bereits existiert.\n'
        f'Antworte mit: "<N> Sport Challenges erstellt."'
    )
    result = run_claude(prompt, automated=True)
    print(f"✅ Sport Challenges: {result.strip()}")


def seed_backlog() -> None:
    entries = "\n".join([
        '- "Notion-Struktur optimieren" | Priorität: Mittel  | Status: Offen',
        '- "Bot-Tests schreiben"        | Priorität: Niedrig | Status: Offen',
        '- "Urlaubsplanung"             | Priorität: Niedrig | Status: Offen',
    ])
    prompt = (
        f'Erstelle folgende Einträge in der Notion-Datenbank {BACKLOG_DB_ID} (Backlog DB):\n'
        f'{entries}\n'
        f'Überspringe Einträge, bei denen Name bereits existiert.\n'
        f'Antworte mit: "<N> Backlog-Einträge erstellt."'
    )
    result = run_claude(prompt, automated=True)
    print(f"✅ Backlog: {result.strip()}")


def seed_lernthemen() -> None:
    entries = "\n".join([
        '- "Python — asyncio verstehen" | Status: Offen',
        '- "Notion API"                 | Status: In Bearbeitung',
    ])
    prompt = (
        f'Erstelle folgende Einträge in der Notion-Datenbank {LERNTHEMEN_DB_ID} (Lernthemen DB):\n'
        f'{entries}\n'
        f'Überspringe Einträge, bei denen Name bereits existiert.\n'
        f'Antworte mit: "<N> Lernthemen erstellt."'
    )
    result = run_claude(prompt, automated=True)
    print(f"✅ Lernthemen: {result.strip()}")


def main() -> None:
    today = datetime.date.today().isoformat()
    print("🌱 Befülle Notion-Datenbanken mit Beispieldaten...")
    seed_tasks(today)
    seed_sport()
    seed_backlog()
    seed_lernthemen()
    print("\n✅ Fertig.")


if __name__ == "__main__":
    main()

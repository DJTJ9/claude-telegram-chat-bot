# Project Knowledge

@/root/projects-hub/topics/telegram-bot-army/DECISIONS.md
@/root/projects-hub/topics/telegram-bot-army/LEARNINGS.md

# Notion Organizer Struktur (seit 2026-06-27)

Sub-Seiten unter Organizer-Hauptseite (`37a4bba29c55807493bdf21e2ef34a9e`):
- 📅 Tagesplanung    — page_id: `38b4bba29c5581ce80c5f28256b38986` — Tasks DB: `38b4bba2-9c55-8177-a404-fcfb97c00b3a`
- 📆 Wochenplanung   — page_id: `38b4bba29c5581c58ebcd27d07cd9f9a` — Tasks gefiltert + Habits DB: `6a4d7e7d-dcde-44e3-b7a0-c46330a6261c`
- 🗓 Monatsübersicht — page_id: `38b4bba29c5581d6a443eca8a9917375` — Tasks gefiltert
- 🗂 Projekte         — Projekte DB: `38b4bba29c5581e8868efe4e2fad255a`
- 🏋 Sport Challenges — Sport DB: `38b4bba29c5581c88f49c67bb85f78c0`
- 💡 Ideensammlung    — Ideensammlung DB: `38b4bba29c55814f836ed9a05d3ec9a5`
- 🗃 Archiv           — Archiv DB: `fd650177-1df5-446c-9fe1-751da5102ce0`

# Notion Datenbanken

## Tasks (Tagesplanung)
- data_source_id: `38b4bba2-9c55-8177-a404-fcfb97c00b3a`
- Properties: Name (title), Status (`Not started`|`In progress`|`Done`), Priorität (select: `Hoch`|`Mittel`|`Niedrig`), Datum (date), Bereich (select: `Arbeit`|`Privat`|`Lernen`|`Gesundheit`), Notiz (rich_text), Zyklus (rich_text)
- Regel: Immer Datum setzen. Priorität Hoch = heute erledigen.

### Termin-Konvention
- Datum mit Uhrzeit (datetime) = Termin → Morgen-View unter "📅 Termine" sortiert nach Zeit
- Datum ohne Uhrzeit / kein Datum = Task → sortiert nach Priorität
- Default-Uhrzeit falls nicht angegeben: `09:00`
- **NocoDB:** `Datum`-Spalte (Typ Date) und `Uhrzeit`-Spalte (Typ Time, Format `HH:MM`) sind getrennte Felder — beide beim Anlegen eines Termins befüllen (`nocodb_direct.create_task(..., uhrzeit=...)`)

### Zyklus-Format (rich_text)
| Wert | Bedeutung |
|------|-----------|
| `täglich` | Jeden Tag |
| `montags` / `dienstags` / … | Jeden Wochentag |
| `wochentags` | Mo–Fr |
| `wochenends` | Sa+So |
| `alle <N> Tage` | z.B. `alle 3 Tage` |
| `1., 15.` | Am 1. und 15. jedes Monats |

Bot-Parsing: LLM interpretiert Freitext, erstellt nächste Instanz. Kein Enum.

## Lernthemen
- data_source_id: `38d4bba2-9c55-810d-8ada-d278460c1579`
- Ort: Ideensammlung-Seite (`38b4bba29c55811ab459c95fd0b6c2ee`)
- Properties: Name (title), Status (`Offen`|`In Bearbeitung`|`Abgeschlossen`)

## Spieleideen
- data_source_id: `ce6783d1-54fe-421f-8d7d-aa8c34880853`
- Properties: Name (title), Typ (select), Genre (multi_select), Plattform (select), Status (select), Beschreibung (rich_text)

## Backlog
- data_source_id: `fad94811-608c-41ba-b728-d1338e21a01d`
- Properties: Name (title), Status (`Offen`|`Erledigt`), Priorität (select), Bereich (select), Notiz (rich_text)

## Task-Archiv
- data_source_id: `fd650177-1df5-446c-9fe1-751da5102ce0`
- Properties: Name (title), Status (kopiert), Priorität (select), Datum (date), Bereich (select), Notiz (rich_text), Archiviert am (date)

## Arbeitsprojekte
- data_source_id: `38b4bba29c5581e8868efe4e2fad255a`
- Properties: Name (title), Typ (select: `Projekt`|`Epic`|`Feature`), Status (select), Priorität (select), Phase (select: `Idee`|`Discussed`|`Planned`|`Done`), Spec (rich_text), Plan (rich_text), Notiz (rich_text), Projekt (select)

## Sport Challenges
- data_source_id: `38b4bba29c5581c88f49c67bb85f78c0`
- Properties: Name (title), Kategorie (select), Status (select: `Not Started` | `Done`)
- Regel: Status-Reset auf "Not Started" manuell in Notion — Bot setzt nur auf "Done"

## Backlog-Flow
- Item direkt abhaken: `backlog_done:{page_id}` Callback → `notion_direct.archive_backlog_item(page_id)` (REST, kein Claude)
- Item einplanen: `BACKLOG_PROMOTE_SYSTEM_PROMPT` → erstellt Task in Tasks-DB, setzt Backlog-Status Erledigt
- Archiv-Loop: `_run_archive_once()` periodisch → archiviert Done-Tasks (Tagesorganizer + Backlog) via LLM

## Morgen/Abend-Workflow
- Morgen: Termine (Datum+Uhrzeit heute) sortiert nach Zeit oben. Tasks (nur Datum oder kein Datum, nicht Done) sortiert nach Priorität darunter. Danach: Sport Challenges (1 zufällige pro Kategorie).
- Abend: Erfolgsliste (Done) + offene Punkte (nicht Done). Frage: offene Tasks auf morgen verschieben?

## Tagesplanung-Seite Linked Views
Auf 📅 Tagesplanung-Sub-Seite 3 Linked-DB-Views:
- Tasks (Filter: Datum = heute, Status ≠ Done)
- Sport Challenges (Filter: Status = Not Started)
- Backlog (Filter: Status = Offen)

Erstellt via `scripts/setup_notion_structure.py → add_linked_views()`.

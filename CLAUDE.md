# Project Knowledge

@/root/projects-hub/topics/telegram-bot-army/DECISIONS.md
@/root/projects-hub/topics/telegram-bot-army/LEARNINGS.md

# Notion Organizer Struktur (seit 2026-06-27)

Sub-Seiten unter Organizer-Hauptseite (`37a4bba29c55807493bdf21e2ef34a9e`):
- 📅 Tagesplanung  — Tasks DB: `38b4bba29c5581a7bd94cef1b0cc6c58`
- 📆 Wochenplanung — (Tasks gefiltert) + Habits DB: `6a4d7e7d-dcde-44e3-b7a0-c46330a6261c`
- 🗓 Monatsübersicht — (Tasks gefiltert)
- 🗂 Projekte — Projekte DB: `38b4bba29c5581e8868efe4e2fad255a`
- 🏋 Sport Challenges — Sport DB: `38b4bba29c5581c88f49c67bb85f78c0`
- 💡 Ideensammlung — Ideensammlung DB: `38b4bba29c55814f836ed9a05d3ec9a5`
- 🗃 Archiv — Archiv DB: `38b4bba29c558102b9aecb790594aff6`

# Notion Datenbanken

## Tasks (Tagesplanung)
- data_source_id: `38b4bba29c5581a7bd94cef1b0cc6c58`
- Properties: Name (title), Status (`Not started`|`In progress`|`Done`), Priorität (select: `Hoch`|`Mittel`|`Niedrig`), Datum (date), Bereich (select: `Arbeit`|`Privat`|`Lernen`|`Gesundheit`), Notiz (rich_text), Zyklus (rich_text)
- Regel: Immer Datum setzen. Priorität Hoch = heute erledigen.

## Lernthemen
- data_source_id: `5a76447f-2b0a-4f6b-81bb-853f39aa04bb`
- Properties: Name (title), Status (`Offen`|`In Bearbeitung`|`Abgeschlossen`), Kategorie (select), Priorität (select), Workspace (rich_text), Notiz (rich_text)

## Spieleideen
- data_source_id: `ce6783d1-54fe-421f-8d7d-aa8c34880853`
- Properties: Name (title), Typ (select), Genre (multi_select), Plattform (select), Status (select), Beschreibung (rich_text)

## Backlog
- data_source_id: `0cb18d17-cf70-413d-b29d-adb4675db614`
- Properties: Name (title), Status (`Offen`|`Erledigt`), Priorität (select), Bereich (select), Notiz (rich_text)

## Task-Archiv
- data_source_id: `38b4bba29c558102b9aecb790594aff6`
- Properties: Name (title), Status (kopiert), Priorität (select), Datum (date), Bereich (select), Notiz (rich_text), Archiviert am (date)

## Arbeitsprojekte
- data_source_id: `032bbb7d-6eb3-43da-a3af-cf0be05f3ece`
- Properties: Name (title), Typ (select: `Projekt`|`Epic`|`Feature`), Status (select), Priorität (select), Phase (select: `Idee`|`Discussed`|`Planned`|`Done`), Spec (rich_text), Plan (rich_text), Notiz (rich_text), Projekt (select)

## Sport Challenges
- data_source_id: `38b4bba29c5581c88f49c67bb85f78c0`
- Properties: Name (title), Kategorie (select), Status (select: `Not Started` | `Done`)
- Regel: Status-Reset auf "Not Started" manuell in Notion — Bot setzt nur auf "Done"

## Morgen/Abend-Workflow
- Morgen: Termine (Datum+Uhrzeit heute) sortiert nach Zeit oben. Tasks (nur Datum oder kein Datum, nicht Done) sortiert nach Priorität darunter. Danach: Sport Challenges (1 zufällige pro Kategorie).
- Abend: Erfolgsliste (Done) + offene Punkte (nicht Done). Frage: offene Tasks auf morgen verschieben?

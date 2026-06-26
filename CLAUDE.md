# Project Knowledge

@/root/projects-hub/topics/telegram-bot-army/DECISIONS.md
@/root/projects-hub/topics/telegram-bot-army/LEARNINGS.md

# Notion Datenbanken

## Tagesorganizer
- data_source_id: `c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0`
- Properties: Name (title), Status (`Not started`|`In progress`|`Done`), Priorität (select: `Hoch`|`Mittel`|`Niedrig`), Datum (date), Bereich (select: `Arbeit`|`Privat`|`Lernen`|`Gesundheit`), Notiz (rich_text)
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
- data_source_id: `abb5abd8-e320-4796-bbf6-941feb9007b9`
- Properties: Name (title), Status (kopiert), Priorität (select), Datum (date), Bereich (select), Notiz (rich_text), Archiviert am (date)

## Arbeitsprojekte
- data_source_id: `032bbb7d-6eb3-43da-a3af-cf0be05f3ece`
- Properties: Name (title), Typ (select: `Projekt`|`Epic`|`Feature`), Status (select), Priorität (select), Phase (select: `Idee`|`Discussed`|`Planned`|`Done`), Spec (rich_text), Plan (rich_text), Notiz (rich_text), Projekt (select)

## Sport Challenges
- data_source_id: `fd7c0b6b4a774a6788ead7d0a093ed42`
- Properties: Name (title), Kategorie (select), Status (select: `Not Started` | `Done`)
- Regel: Status-Reset auf "Not Started" manuell in Notion — Bot setzt nur auf "Done"

## Morgen/Abend-Workflow
- Morgen: Termine (Datum+Uhrzeit heute) sortiert nach Zeit oben. Tasks (nur Datum oder kein Datum, nicht Done) sortiert nach Priorität darunter. Danach: Sport Challenges (1 zufällige pro Kategorie).
- Abend: Erfolgsliste (Done) + offene Punkte (nicht Done). Frage: offene Tasks auf morgen verschieben?

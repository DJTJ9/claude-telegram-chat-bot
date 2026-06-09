# Mission

## Why
Notion als persönliches Hirn für tägliche Planung: Tasks in Notion anlegen und pflegen,
Claude Code liest sie, aktualisiert Status, erweitert den Organizer per Prompt.
Ziel: bis Ende Juni 2026 einen vollständigen Tagesplaner in Notion haben, der sich per
Claude Code steuern lässt — kein manuelles Copy-Paste, keine Tool-Wechsel.

## Success looks like
- Notion-Datenbank als täglicher Organizer strukturiert (Properties: Name, Status, Priorität, Datum, Bereich)
- Claude Code liest offene Tasks des Tages und zeigt Tagesplan
- Claude Code setzt erledigte Tasks auf "Done" per einfachem Prompt
- Neue Tasks per Spracheingabe → Claude Code legt sie in Notion an
- Mindestens ein wiederverwendbarer Workflow-Prompt für den Morgen und einen für den Abend

## Constraints
- Notion Desktop App (v7.19.0)
- Windows 10, PowerShell
- Claude Code CLI mit Notion MCP
- Einfach halten: keine Automation-Tools, keine Webhooks — nur Claude Code + Notion

## Out of scope
- Kalender-Sync (Google Calendar, Outlook)
- Mobile Workflows (nur Desktop)
- Komplexe Datenbankrelationen (vorerst)
- Andere Note-Apps

# LR-0009: CLAUDE.md als persistentes Workflow-Gedächtnis

CLAUDE.md in `~/.claude/CLAUDE.md` (global) wird bei jedem Session-Start automatisch geladen —
data_source_id, Workflow-Vorlagen und Regeln müssen nie wieder erklärt werden.
Direkter Zugriff per ID schlägt `notion_find`-Suche: weniger Tool-Calls, sofort los.

evidence: Tagesorganizer-Block in globaler CLAUDE.md live eingetragen, funktioniert in aktueller Session sichtbar (Kontext-Header zeigt die DB-ID).

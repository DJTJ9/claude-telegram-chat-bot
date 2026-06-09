# LR-0008: Morgen- und Abend-Workflow mit echtem Tagesorganizer

Morgen-Prompt: Filter Status ≠ Done + (Datum = heute OR leer), Sort Priorität asc, Group Bereich.
Abend-Prompt: zwei parallele Queries (Done / nicht Done) → Rückblick + offene Punkte.
Compound-Filter (AND + OR) funktioniert in notion_query_data_source.

evidence: Beide Prompts live gegen Tagesorganizer-DB ausgeführt, Task "Organizer entwickeln" korrekt in Erfolgsliste erschienen.

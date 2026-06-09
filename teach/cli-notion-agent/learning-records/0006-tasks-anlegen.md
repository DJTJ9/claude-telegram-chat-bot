# LR-0006: Neue Notion-Tasks per Claude Code anlegen

`notion_create_data_source_item_from_values` legt neue Einträge mit flachem Key-Value-Objekt an.
Mehrere unabhängige Creates laufen parallel — ein Prompt, N Tasks, keine Wartezeit.
Gibt neue page_id zurück → direkt für Update-Calls nutzbar.

evidence: 4 Tasks in zwei Calls angelegt (1 einzeln, 3 parallel) — alle in Notion Desktop bestätigt.

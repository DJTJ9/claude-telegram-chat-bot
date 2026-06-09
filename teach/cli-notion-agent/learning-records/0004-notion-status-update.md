# LR-0004: Notion-Property per Claude Code schreiben

`notion_update_page_properties` setzt Properties (z.B. Status) via page_id.
Status-Name muss exakt mit Notion-Option übereinstimmen.
page_id kommt aus vorheriger `notion_query_data_source`-Antwort — kein extra Lookup nötig.

evidence: "Learn Notion" Status live von "In progress" auf "Done" gesetzt, in Notion Desktop bestätigt.

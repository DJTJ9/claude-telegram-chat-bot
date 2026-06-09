# LR-0012: Task-Parsing via System-Prompt + Prefix-Routing

Prefix-Routing ("Task:") ist zuverlässiger als KI-Klassifikation — deterministisch, kein Extra-Aufruf.
`--system-prompt` gibt Claude Parsing-Regeln + Output-Format ohne die User-Nachricht zu verändern.
`encoding="utf-8"` in subprocess.run nötig auf Windows — cp1252 bricht bei Unicode-Zeichen (✅, Umlaute).
Datum explizit übergeben (`Heute ist {today}`), da claude -p kalt startet ohne Zeitkontext.

evidence: "Task: Frog für nächsten Tag, Priorität Hoch" und "Task: Python lernen" beide korrekt in Notion angelegt nach UTF-8-Fix.

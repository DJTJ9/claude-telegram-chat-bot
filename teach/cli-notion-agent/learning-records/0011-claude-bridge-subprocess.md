# LR-0011: Claude Code als Subprocess via Telegram-Bridge

`claude --dangerously-skip-permissions -p "prompt"` läuft nicht-interaktiv und gibt Antwort auf stdout.
`cwd=WORK_DIR` sorgt dafür dass CLAUDE.md geladen wird — damit kennt Claude den Tagesorganizer ohne erklären.
`subprocess.run` mit `capture_output=True` liest stdout/stderr als String zurück.
Für Produktion: `--allowedTools mcp__notion__*` statt `--dangerously-skip-permissions`.

evidence: Telegram-Nachricht "Was ist heute das Datum?" → Claude antwortet korrekt in Telegram, Terminal zeigt Prompt + Antwort-Preview.

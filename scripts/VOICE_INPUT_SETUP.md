# Voice Input Setup

## Desktop (Windows)
1. `ffmpeg` installieren, sicherstellen dass es im PATH ist (`ffmpeg -version`).
2. AutoHotkey installieren (https://www.autohotkey.com).
3. `scripts/voice_input_desktop.ahk` per Doppelklick starten (oder in Autostart-Ordner legen).
4. Ctrl+Alt+V = Aufnahme starten/stoppen (Toggle).

## Mobile (Termux)
1. Termux + Termux:API-App installieren (beide aus F-Droid, NICHT Play Store — Play-Store-Version ist veraltet).
2. `pkg install termux-api python` in Termux ausführen.
3. `chmod +x scripts/voice_input_termux.sh`.
4. Termux:Widget-App installieren, Shortcut auf `scripts/voice_input_termux.sh` anlegen
   (Symlink in `~/.shortcuts/` zeigt auf das Script im Repo-Pfad).
5. Antippen = Aufnahme starten/stoppen (Toggle). Nach Stop: Text ist im Clipboard,
   manuell per Long-Press ins Terminal einfügen (kein Auto-Paste ohne Root möglich).

## Beide Plattformen
- `GROQ_API_KEY` muss in `$WORK_DIR/.env` gesetzt sein (bereits vorhanden).
- `pip install -r requirements.txt` stellt sicher, dass das `groq`-SDK verfügbar ist.

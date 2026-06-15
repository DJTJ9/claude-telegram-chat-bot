# vision:end — Session-Save für Vision-Sessions

## Ziel

`vision:` Sessions können explizit beendet werden mit `vision:end` — als Antwort auf Claudes nächste Frage oder als freie Telegram-Nachricht jederzeit. Am Ende wird VISION.md geschrieben, erweitert um `## Letzter Stand` und `## Confidence-Scores`.

## Bugfix: Claude sagt "keine Tools erlaubt"

Claude in `_run_vision` hat `--dangerously-skip-permissions` und nutzt bereits Bash (telegram_ask.py), sagt aber dennoch "ich darf keine Tools verwenden". Ursache: Prompt definiert kein klares End-Signal und keine explizite Bestätigung der Tool-Rechte. Claude bleibt in der Frage-Schleife und verwirft Schreib-Anfragen als "außerhalb der Session".

Fix: Prompt-Ergänzungen (siehe Abschnitt Prompt-Änderungen).

## Komponenten

### 1. Signal-Datei-Mechanismus

**Datei:** `HUB_DIR/.vision_end`

Ermöglicht, dass eine freie Telegram-Nachricht (`vision:end`) eine laufende Claude-Session beeinflusst, ohne IPC oder Prozess-Kill.

Fluss:
1. User sendet `vision:end` (Antwort auf Frage ODER freie Nachricht)
2. Bot schreibt `HUB_DIR/.vision_end`
3. Beim nächsten `telegram_ask.py`-Aufruf: Datei gefunden → `"vision:end"` zurückgeben, Datei löschen
4. Claude empfängt `"vision:end"` → schreibt VISION.md → git commit/push

### 2. bot.py — Neuer Message-Handler

```python
elif text.lower() == "vision:end":
    if _vision_active:
        Path(HUB_DIR, ".vision_end").write_text("end")
        response = "⏹ vision:end Signal gesendet — Claude schreibt VISION.md"
    else:
        response = "Keine Vision-Session aktiv."
```

Platzierung: im `elif`-Kette des Message-Handlers, vor dem allgemeinen `else`.

### 3. telegram_ask.py — Signal-Check

Am Anfang der Hauptlogik, vor dem Senden der Frage:

```python
signal_path = Path(HUB_DIR) / ".vision_end"
if signal_path.exists():
    signal_path.unlink()
    print("vision:end")
    sys.exit(0)
```

`HUB_DIR` muss in `telegram_ask.py` verfügbar sein (aus env oder settings.json lesen — bereits vorhanden wenn bot läuft).

### 4. _run_vision Prompt-Änderungen

Drei Ergänzungen zum bestehenden Prompt:

**Tool-Rechte explizit bestätigen:**
```
"You have full tool access: write files, run Bash commands including git. "
```

**vision:end-Signal:**
```
"If any telegram_ask.py call returns exactly 'vision:end': stop asking questions. "
"Write/update {vision_path} with all discussed content. "
"Then: git -C {HUB_DIR} add -A && git -C {HUB_DIR} commit -m 'vision: update {slug}' && git -C {HUB_DIR} push. "
"Then exit. "
```

**Natürliches End-Signal (bisher undefiniert):**
```
"When you have covered goal, top features, architecture, and open questions: "
"ask 'Soll ich die Vision-Session jetzt abschließen? (ja / vision:end / weiter)'. "
"On 'ja' or 'vision:end': write VISION.md and commit. On 'weiter': continue. "
```

### 5. VISION.md Struktur-Erweiterung

Zwei neue Abschnitte, die Claude bei jedem Session-Ende schreibt/überschreibt:

**`## Letzter Stand`** — Wiederaufnahme-Marker:
```markdown
## Letzter Stand
*YYYY-MM-DD*

Zuletzt besprochen: <Themen der Session>.
Nächste Session: <offene Punkte, priorisiert>.
```

**`## Confidence-Scores`** — Entscheidungs-Bewertung:
```markdown
## Confidence-Scores

| Position | Bestätigungen | Anzweiflungen | Bewertung |
|----------|--------------|---------------|-----------|
| Beispiel-Entscheidung | 3 | 0 | 🟢 hoch |
```

Claude füllt diese Abschnitte basierend auf dem Gesprächsverlauf (wie oft wurde eine Position bestätigt vs. angezweifelt).

## Datenfluss

```
User: "vision:end" (Antwort oder freie Nachricht)
  │
  ├─ Als Antwort auf Frage:
  │    telegram_ask.py empfängt → gibt "vision:end" an Claude zurück
  │
  └─ Als freie Nachricht:
       bot.py Main-Loop → schreibt HUB_DIR/.vision_end
       → nächster telegram_ask.py-Aufruf liest Datei → gibt "vision:end" zurück
  
Claude empfängt "vision:end"
  → schreibt VISION.md (inkl. Letzter Stand + Confidence-Scores)
  → git add -A && commit && push
  → subprocess.run gibt 0 zurück
  → bot sendet "🔭 Vision-Session für X abgeschlossen"
```

## Nicht im Scope

- Mehrere parallele Vision-Sessions (bleibt durch `_vision_active` Flag gesperrt)
- Telegram-Relay für Brainstorming-Sessions von Windows aus (separates Problem: Race condition Pi-Bot vs. telegram_ask.py auf Windows)
- Confidence-Score-Eingabe durch User (Claude schätzt selbst aus Gesprächsverlauf)

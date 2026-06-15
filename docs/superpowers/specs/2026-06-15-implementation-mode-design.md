# Implementation Mode — Design

**Datum:** 2026-06-15  
**Scope:** `on_permission.py`, `CLAUDE.md`, `bot.py`

## Problem

Bei Terminal-Brainstorming-Sessions blockieren Permission-Anfragen die Inline-Implementierung:
- `on_permission.py` schickt nicht-PROJECT_DIR-Edits (z.B. CLAUDE.md) ans Telegram-Relay
- Bash-Commands gehen ebenfalls ans Relay wenn `notifications_enabled: true`
- Nicht alle Anfragen kommen beim Bot an (Timing-Probleme)
- User muss jede Kleinigkeit vom Handy approven obwohl der Plan bereits ausführlich abgesegnet wurde

`_run_plan()` (Bot-triggered) nutzt `--dangerously-skip-permissions` → kein Problem.  
Terminal-Sessions können Permission-Mode nicht nachträglich ändern → nur der Hook kann eingreifen.

## Lösung: `implementation_mode` Flag

### Datenmodell (`settings.json`)

```json
{
  "implementation_mode": false,
  "implementation_mode_until": null
}
```

`implementation_mode_until` = ISO-8601-Timestamp +4h ab Aktivierung. Selbst-ablaufend — kein Cleanup-Loop nötig.

### Hook-Änderung (`on_permission.py`)

Neuer Block direkt nach settings.json laden, VOR `notifications_enabled`-Check:

```python
from datetime import datetime

impl_mode = settings.get("implementation_mode", False)
impl_until = settings.get("implementation_mode_until")

if impl_mode and impl_until:
    try:
        if datetime.now().isoformat() <= impl_until:
            print(json.dumps({"decision": "approve"}))
            sys.exit(0)
    except Exception:
        pass  # malformed timestamp → fall through to normal behavior
```

Wenn Mode aktiv + nicht abgelaufen: sofort approve, kein Telegram, kein Warten.

### Lifecycle (CLAUDE.md-Instruktion)

**Automatisch — VOR Inline-Implementierung** (nach "jetzt"-Antwort im Post-Plan-Scheduling):

Claude nutzt das **Edit-Tool** (nicht Bash) um `settings.json` zu aktualisieren:
- `implementation_mode: true`
- `implementation_mode_until: <jetzt+4h als ISO-String>`

Edit auf PROJECT_DIR-Dateien ist immer auto-approved → kein Henne-Ei-Problem.

**Automatisch — als letzter Schritt der Implementierung** (nach allen Commits und Push):

Claude löscht das Flag via Edit:
- `implementation_mode: false`
- `implementation_mode_until: null`

### Manueller Override (`bot.py`)

Neuer Befehl `impl-mode: an|aus`:
- `impl-mode: an` → setzt Flag + `until` (+4h) → Telegram-Bestätigung
- `impl-mode: aus` → löscht Flag → Telegram-Bestätigung
- `impl-mode:` (kein Arg) → zeigt aktuellen Status + ggf. restliche Zeit

Nützlich wenn Claude abstürzt und Flag stecken bleibt.

## Dateien

| Datei | Änderung |
|---|---|
| `scripts/on_permission.py` | +8 Zeilen am Anfang (nach settings-load) |
| `C:\Users\tjark\.claude\CLAUDE.md` | +4 Zeilen im Post-Plan-Scheduling-Block |
| `bot.py` | neuer `elif`-Block + HILFE_TEXT-Zeile |

## Nicht im Scope

- Änderungen am Telegram-Relay (bleibt wie es ist)
- Änderungen an `_run_plan()` (bot-triggered, nutzt bereits `--dangerously-skip-permissions`)
- Neue Helper-Scripts (alles in bestehenden Dateien)

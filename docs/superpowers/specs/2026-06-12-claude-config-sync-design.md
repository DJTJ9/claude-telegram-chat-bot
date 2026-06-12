# Claude Config Sync — Design Spec

**Date:** 2026-06-12  
**Goal:** `~/.claude` setup (skills, plugins, hooks, CLAUDE.md, memory) identisch auf allen Windows-Geräten — minimaler Aufwand, automatische Synchronisation.

---

## 1. Architektur

`~/.claude` wird privates GitHub Repo. Bestehende SessionStart/Stop-Hooks (`config-pull.sh`, `config-push.sh`) sind bereits verdrahtet — brauchen nur einen konfigurierten Git-Remote.

```
Desktop ~/.claude  ──push──►  GitHub (privat)  ◄──pull──  Laptop ~/.claude
        ▲ auto bei Stop                                    ▲ auto bei Start
```

---

## 2. Repository-Inhalt

### Tracked (in Git)
```
~/.claude/
  CLAUDE.md                   ← globale Instruktionen + Notion-Datenbank-Definitionen
  settings.json               ← Plugins, Hooks, Theme, enabledPlugins
  hooks/                      ← caveman-*.js, config-pull.sh, config-push.sh
  skills/                     ← teach, watch (lokale Skills)
  memory/                     ← project memories (MEMORY.md + alle *.md)
  statusline-command.sh
  setup.ps1                   ← Bootstrap-Script für neues Gerät
```

### Ignoriert (.gitignore)
```
projects/           # session-interne Daten
tasks/
file-history/
shell-snapshots/
security/
plugins/cache/      # auto-geladen von Claude Code
plugins/marketplaces/
*.jsonl             # session logs
```

---

## 3. ECC Plugin — Pfad-Fix

**Problem:** `settings.json` referenziert ECC als lokalen `file`-Pfad (`C:\Temp\ECC-inspect`) — nicht portabel.

**Fix:** Auf `github` Source umstellen (ECC ist öffentliches MIT-Repo):

```json
// vorher
"ecc": {
  "source": { "source": "file", "path": "C:\\Temp\\ECC-inspect\\.claude-plugin\\marketplace.json" }
}

// nachher
"ecc": {
  "source": { "source": "github", "repo": "affaan-m/ECC" }
}
```

Alle anderen Plugins (`caveman`, `superpowers`, `codex`, `skill-creator`, `frontend-design`, `security-guidance`) nutzen bereits `github` oder `file`-Pfade unter `~/.claude` — bleiben unverändert.

---

## 4. Bootstrap — Neues Gerät

Zwei manuelle Befehle, dann `setup.ps1` übernimmt:

```powershell
# Einmalig auf neuem Gerät:
git clone https://github.com/DJTJ9/claude-config $HOME\.claude
& "$HOME\.claude\setup.ps1"
```

### setup.ps1 — Inhalt

```powershell
# Voraussetzungen: git, Node.js, Python installiert

# 1. Node-Deps für Hooks
npm install --prefix $HOME\.claude\hooks

# 2. Projekte klonen
New-Item -ItemType Directory -Force "C:\Projekte"
git clone https://github.com/DJTJ9/telegram-notion-bot "C:\Projekte\telegram-notion-bot"

# 3. Python-Deps für Bot
pip install -r "C:\Projekte\telegram-notion-bot\requirements.txt"

# 4. Secrets — manuell
Write-Host ""
Write-Host "Manuelle Schritte:"
Write-Host "  1. Claude Code installieren + API Key eingeben"
Write-Host "  2. .env Datei anlegen: C:\Projekte\telegram-notion-bot\.env"
Write-Host "     (TELEGRAM_TOKEN, NOTION_API_KEY, etc.)"
Write-Host ""
Write-Host "Fertig. Claude Code starten — Plugins laden automatisch."
```

---

## 5. Ongoing Sync Flow

| Event | Hook | Aktion |
|---|---|---|
| Session Start | `SessionStart` → `config-pull.sh` | `git pull --rebase --autostash` |
| Session Stop | `Stop` → `config-push.sh` | `git add -A && git commit && git push` |

Änderungen während einer Session (neue Plugins, CLAUDE.md-Ergänzungen, neue Memory-Einträge) werden automatisch committed und gepusht. Beim nächsten Start auf einem anderen Gerät sind sie da.

---

## 6. Was NICHT synct (bewusst)

| Was | Warum |
|---|---|
| `.env` / Secrets | Sicherheit — nie in Git |
| Claude Code API Key | Gerätespezifisch, in Claude Code gespeichert |
| Session-Logs, Tasks | Ephemer, kein Mehrwert |
| `plugins/cache/` | Auto-regeneriert |

---

## 7. Implementierungsschritte

1. `.gitignore` in `~/.claude` erstellen
2. `settings.json` — ECC auf `github` Source umstellen
3. `git init` + Remote setzen + initialer Push von `~/.claude`
4. `setup.ps1` erstellen + committen
5. Verify: `config-pull.sh` / `config-push.sh` funktionieren mit Remote

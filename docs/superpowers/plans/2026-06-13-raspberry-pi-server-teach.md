# Teach Plan: Raspberry Pi als Home-Server

## Topic
Raspberry Pi 4 als dauerhafter Server einrichten, um den Telegram-Notion-Bot ohne offenes Terminal auf dem Windows-Rechner zu betreiben.

## Why
Bot soll 24/7 laufen, automatisch starten beim Booten und Neustarts überleben — ohne dass der Windows-PC laufen muss.

## Workspace
C:\Projekte\teach\raspberry-pi-server\

## Learner Profile
- Linux/Server-Anfänger (kaum Terminal-Erfahrung)
- Pi 4 (4GB oder 8GB RAM) vorhanden, noch nicht 24/7 aktiv
- Kein Zeitdruck, gründliches Lernen bevorzugt

## Lesson Sequence
1. raspberry-pi-os-setup — OS mit Raspberry Pi Imager flashen, SSH aktivieren, Pi zum ersten Mal starten
2. ssh-zugang — SSH vom Windows-PC verbinden, SSH-Keys erstellen, Passwort-Login deaktivieren
3. linux-grundlagen — Dateisystem navigieren, apt, Pakete installieren, nano-Editor
4. bot-code-transfer — Git auf Pi installieren, Repo klonen, Code übertragen
5. python-umgebung — venv erstellen, requirements installieren, .env-Datei für API-Tokens/Secrets
6. systemd-service — Service-Datei schreiben, Bot als Service starten, Autostart beim Boot
7. firewall-sicherheit — ufw einrichten, SSH absichern, Grundlagen fail2ban
8. logs-und-wartung — journalctl, Bot-Logs lesen, Updates, Fehlersuche wenn Bot abstürzt

## Implementation Instructions
Invoke the /teach skill with the topic and context above. Workspace already exists at C:\Projekte\teach\raspberry-pi-server\ with MISSION.md, NOTES.md, RESOURCES.md written. Skip clarifying questions — use this plan directly. Create all 8 lessons in batch using the lesson sequence above (slugs as listed). Then commit, push, and send Telegram links.

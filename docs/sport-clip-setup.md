# Sport-Clip-Capture Setup

Pipeline: Web Clipper → Obsidian Vault (`Sport Challenges/`) → LiveSync (CouchDB) →
Server-Spiegel `/root/obsidian-vault/` → `sport_clip_import.py` (Timer, 5 min) → NocoDB Sport Challenges.

## Einmalig (manuell, User)

1. **Cloudflare-DNS:** A-Record `sync` → Server-IP, Proxy an.

## Einmalig pro Gerät (iPad / Android / Windows)

2. **Obsidian LiveSync Plugin** (Community Plugins → "Self-hosted LiveSync"):
   - Remote Database URI: `https://sync.thinkshark.de` — **ohne `/obsidian`-Pfad!**
     Das Plugin hat ein separates Feld "Database name": dort `obsidian` eintragen.
     (URI mit Pfad + Database name führt zu doppeltem Pfad `/obsidian/obsidian/` →
     404/400, Plugin meldet "Could not connect".)
   - Username: `obsidian_sync`, Password: siehe `/root/nocodb-data/.env`
   - Sync-Modus: LiveSync. Bei Cloudflare-Timeouts: Batch size/Batch limit reduzieren.
3. **Obsidian Web Clipper**:
   - iPad: Safari-Extension (App Store), in Safari-Einstellungen aktivieren, Teilen-Menü
   - Android: Firefox + Extension (addons.mozilla.org)
   - Windows: Chrome/Firefox/Edge-Extension
4. **Clipper-Template "Sport Challenge"** (Clipper-Einstellungen → Templates → New):
   - Note location: `Sport Challenges`
   - Note name: `{{date}}-{{title}}`
   - Properties:
     - `title: {{title}}`
     - `kategorie:` — **strikte SingleSelect** in NocoDB. Erlaubte Werte: `Ausdauer`,
       `Kraft`, `Entspannung`, `Flexibility`. Entweder mit genau einer dieser Optionen
       befüllen oder LEER lassen (leer → Row ohne Kategorie). **Ungültige Werte führen
       zu HTTP 400 und die Note wird nicht importiert.** Es gibt keinen Default.
     - `source: {{url}}`
     - `nocodb_id:` (leer lassen! — wird vom Import-Script gesetzt)
   - Note content: `{{selection}}` + Bild-Embed; kurze Videoclips (.mp4) manuell in den
     Vault legen und per `![[clip.mp4]]` embedden

## Server-Komponenten

- CouchDB: `/root/nocodb-data/docker-compose.yml` (Service `couchdb`, 127.0.0.1:5984),
  Config `couchdb-local.ini`, Credentials `/root/nocodb-data/.env`
- Caddy: Block `sync.thinkshark.de` in `/etc/caddy/Caddyfile` (reverse_proxy auf `localhost:5984`)
- Vault-Spiegel: `filesystem-livesync.service` (Repo `/root/filesystem-livesync`)
- Import: `sport-clip-import.timer` + `.service` → `scripts/sport_clip_import.py`
- NocoDB-Felder via `scripts/setup_sport_clip_fields.py`: Medium/Quelle/Notiz
- Media-Enrichment: `yt-dlp` (pip, global) + `ffmpeg` (apt) — Frames pro Übung
  beim Import. yt-dlp bricht bei YouTube-Änderungen gelegentlich → Update mit
  `python3 -m pip install --break-system-packages -U yt-dlp`.

### NocoDB-URL-Konvention

`NOCODB_API_URL` in `$WORK_DIR/.env` MUSS der nackte Host sein:

```
NOCODB_API_URL=https://organizer.thinkshark.de
```

Der frühere Workspace/Base-Dashboard-Präfix (`/w595bo48/...`) funktioniert für KEINE
API — Caddy proxied 1:1 und NocoDB kennt diesen Pfad serverseitig nicht.
`sport_clip_import.py` leitet zusätzlich per `urlsplit` den nackten Host für
`storage/upload` ab; `setup_sport_clip_fields.py` macht dasselbe für die Meta-API.

### filesystem-livesync (as-built)

- Upstream ist **unmaintained** (Nachfolger: livesync-bridge). Läuft trotzdem stabil
  für diesen Use-Case.
- Config liegt **hardcoded** unter `/root/filesystem-livesync/dat/config.json` —
  es gibt kein `--config`-Flag.
- `deleteMetadataOfDeletedFiles` gehört auf **Top-Level** des Config-Eintrags.
- Build: Repo brauchte `git submodule update --init --recursive` **vor** `npm install`.
- Service-ExecStart pinnt die Node-Version über den nvm-Pfad
  (`/root/.nvm/versions/node/v24.16.0/bin/node`). Bei einem nvm-Upgrade, das
  v24.16.0 entfernt, bricht der Service — dann ExecStart auf den neuen Pfad anpassen
  und `systemctl daemon-reload`.
- Bekannte Limitation: lokale Datei-Löschungen kurz nach dem Push propagieren nicht
  zuverlässig zur CouchDB.

### NocoDB-Felder (Sport Challenges)

- `Kategorie`: SingleSelect mit Optionen `Ausdauer`, `Kraft`, `Entspannung`, `Flexibility`
- `Status`: Option heißt exakt `Not Started` (großes S — nicht `Not started`)
- Zusatzfelder via `scripts/setup_sport_clip_fields.py`: `Medium` (Attachment),
  `Quelle` (URL), `Notiz` (LongText)

## Troubleshooting

- Clip fehlt in NocoDB: `journalctl -u sport-clip-import.service -n 20`,
  dann `journalctl -u filesystem-livesync -n 50` (kommt die Note im Spiegel an?)
- HTTP 400 im Import-Log: fast immer ungültiger `kategorie:`-Wert im Frontmatter
  (siehe erlaubte Optionen oben) — Wert korrigieren oder leeren, nächster Timer-Lauf
  importiert neu.
- Note re-importieren: `nocodb_id:`-Zeile im Frontmatter leeren
- Medium leer trotz YouTube-Quelle: `journalctl -u sport-clip-import -n 20` —
  Zeile "Enrichment fehlgeschlagen" nennt den Grund. Häufigster Fix:
  `python3 -m pip install --break-system-packages -U yt-dlp` (YouTube-Änderung).
  Nur Thumbnail statt Frames = Enrichment-Fallback hat gegriffen; Frames kommen
  nach yt-dlp-Update + Re-Import (`nocodb_id:` leeren).
- Frames scheitern aktuell serverseitig: YouTube-Bot-Check blockt die
  Datacenter-IP ("Sign in to confirm you're not a bot") — Thumbnail-Fallback
  ist das erwartete Verhalten, bis Cookies provisioniert sind. Zusätzlich
  braucht yt-dlp 2026.x eine JS-Runtime (node vorhanden: `--js-runtimes node`).
- **Bekannter offener Bug** (Stand 2026-07-04, separates Follow-up):
  `core/nocodb_direct.py:161` — `fetch_sport_challenges()` filtert mit
  `(Status,eq,Not started)`. Falsches Casing (Option heißt `Not Started`), matcht
  daher 0 Rows → der Sport-Random-Pool der Bots ist leer. Das Modul war für dieses
  Feature tabu; Fix erfolgt separat.

## Appendix: Konfigurationsdateien (as-built)

### /etc/systemd/system/sport-clip-import.service

```ini
[Unit]
Description=Sport-Challenge Clips aus Obsidian-Vault nach NocoDB importieren

[Service]
Type=oneshot
WorkingDirectory=/root/projekte/telegram-bot-army
ExecStart=/usr/bin/python3 -u scripts/sport_clip_import.py
```

### /etc/systemd/system/sport-clip-import.timer

```ini
[Unit]
Description=Sport-Clip-Import alle 5 Minuten

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

### /etc/systemd/system/filesystem-livesync.service

```ini
[Unit]
Description=Obsidian filesystem-livesync (CouchDB <-> /root/obsidian-vault)
After=network.target docker.service

[Service]
WorkingDirectory=/root/filesystem-livesync
ExecStart=/root/.nvm/versions/node/v24.16.0/bin/node dist/index.js
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### /root/nocodb-data/docker-compose.yml — Service-Block `couchdb`

```yaml
  couchdb:
    image: couchdb:3
    ports:
      - "127.0.0.1:5984:5984"
    environment:
      - COUCHDB_USER=${COUCHDB_USER}
      - COUCHDB_PASSWORD=${COUCHDB_PASSWORD}
    volumes:
      - couchdb_data:/opt/couchdb/data
      - ./couchdb-local.ini:/opt/couchdb/etc/local.d/livesync.ini
    restart: unless-stopped
```

Credentials (`COUCHDB_USER`, `COUCHDB_PASSWORD`): `/root/nocodb-data/.env`.

### /root/nocodb-data/couchdb-local.ini

Hinweis: CouchDB hasht das Admin-Passwort beim ersten Start selbst — die
`[admins]`-Zeile enthält daher einen generierten pbkdf2-Hash (hier redacted).

```ini
[couchdb]
single_node=true
max_document_size = 50000000
uuid = 35e0f4be4dad9ccf5cf89932197dbfcb

[chttpd]
require_valid_user = true
max_http_request_size = 4294967296
enable_cors = true

[chttpd_auth]
require_valid_user = true

[httpd]
WWW-Authenticate = Basic realm="couchdb"
enable_cors = true

[cors]
origins = app://obsidian.md, capacitor://localhost, http://localhost
credentials = true
headers = accept, authorization, content-type, origin, referer
methods = GET,PUT,POST,HEAD,DELETE
max_age = 3600

[admins]
obsidian_sync = <redacted>
```

### /etc/caddy/Caddyfile — Block `sync.thinkshark.de`

```
sync.thinkshark.de {
    tls /etc/caddy/cf-origin.pem /etc/caddy/cf-origin-key.pem
    reverse_proxy localhost:5984
}
```

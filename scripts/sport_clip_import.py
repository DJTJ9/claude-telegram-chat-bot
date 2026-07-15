#!/usr/bin/env python3
"""Importiert Web-Clipper-Notes aus dem Vault-Ordner 'Sport Challenges/' als Rows
mit Medium-Attachment in die NocoDB Sport Challenges Table.

Idempotenz: Notes mit gesetztem nocodb_id-Frontmatter werden übersprungen;
nach erfolgreichem Import wird die Row-ID ins Frontmatter zurückgeschrieben
(synct via LiveSync auf alle Geräte zurück)."""
import mimetypes
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import requests

try:
    from scripts import youtube_enrich  # Test-Kontext (Repo-Root auf sys.path)
except ImportError:
    import youtube_enrich  # Script-Kontext (scripts/ ist sys.path[0])

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# Records- UND Storage-API laufen beide nur auf dem nackten Host ohne
# Workspace/Base-Pfad-Präfix (live verifiziert: präfixiert 404 "Cannot POST",
# bare 200). Ein evtl. Präfix in NOCODB_API_URL wird deshalb hier abgestreift.
NOCODB_API_URL = os.environ.get("NOCODB_API_URL", "http://localhost:8090")
_parts = urlsplit(NOCODB_API_URL)
NOCODB_HOST_URL = f"{_parts.scheme}://{_parts.netloc}"
NOCODB_API_TOKEN = os.environ.get("NOCODB_API_TOKEN", "")
SPORT_TABLE_ID = os.environ.get("NOCODB_SPORT_TABLE_ID", "")
VAULT_PATH = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "/root/obsidian-vault"))
CLIP_DIR = "Sport Challenges"
TOKEN_ORGANIZER = os.environ.get("TOKEN_ORGANIZER", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm", ".mov"}
_EMBED_RE = re.compile(r"!\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")
_MD_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm = {}
    for line in parts[1].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"')
    return fm, parts[2]


def find_media(body: str, note_path: Path, vault: Path) -> Path | None:
    for name in _EMBED_RE.findall(body) + _MD_IMG_RE.findall(body):
        name = name.strip()
        if name.startswith("http"):
            continue
        if Path(name).suffix.lower() not in MEDIA_EXTS:
            continue
        for cand in (note_path.parent / name, vault / name):
            if cand.exists():
                return cand
        hits = list(vault.rglob(Path(name).name))
        if hits:
            return hits[0]
    return None


def find_pending(vault: Path) -> list[Path]:
    # LiveSync mit Case-insensitive-Handling spiegelt Pfade lowercase auf den
    # Server — Ordnernamen deshalb case-insensitiv matchen
    if not vault.is_dir():
        return []
    clip_dirs = [d for d in vault.iterdir() if d.is_dir() and d.name.lower() == CLIP_DIR.lower()]
    pending = []
    for clip_dir in sorted(clip_dirs):
        for note in sorted(clip_dir.glob("*.md")):
            fm, _ = parse_frontmatter(note.read_text(encoding="utf-8"))
            if not fm.get("nocodb_id"):
                pending.append(note)
    return pending


def upload_attachment(path: Path) -> list[dict]:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with open(path, "rb") as fh:
        r = requests.post(
            f"{NOCODB_HOST_URL}/api/v2/storage/upload",
            headers={"xc-token": NOCODB_API_TOKEN},
            files={"file": (path.name, fh, mime)},
        )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Upload fehlgeschlagen ({path.name}): {r.status_code} {r.text[:200]}")
    return r.json()


def write_back_id(path: Path, row_id: int) -> None:
    text = path.read_text(encoding="utf-8")
    if re.search(r"^nocodb_id:.*$", text, flags=re.MULTILINE):
        text = re.sub(r"^nocodb_id:.*$", f"nocodb_id: {row_id}", text, count=1, flags=re.MULTILINE)
    elif text.startswith("---"):
        text = text.replace("---", f"---\nnocodb_id: {row_id}", 1)
    else:
        text = f"---\nnocodb_id: {row_id}\n---\n{text}"
    path.write_text(text, encoding="utf-8")


def notify_import(title: str, media_count: int) -> None:
    """Produkt-Notification direkt an den Organizer-Chat — bewusst NICHT über
    telegram_notify.py, das die Meldung über active_session routen würde statt
    fest an den Organizer (User-Entscheidung 2026-07-05)."""
    if not TOKEN_ORGANIZER or not CHAT_ID:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN_ORGANIZER}/sendMessage",
            json={"chat_id": int(CHAT_ID),
                  "text": f"🏃 Sport-Challenge importiert: {title} ({media_count} Medien)"},
            timeout=15,
        )
        if r.status_code != 200:
            print(f"Import-Notify HTTP {r.status_code}")
    except Exception as exc:
        print(f"Import-Notify fehlgeschlagen: {exc}")


def enrich_media(source: str) -> tuple[list[dict], list[str]]:
    """Kaskade: Cookies-Frames -> Watch-Page-Kapitel+Thumbnail -> Thumbnail -> nichts.
    Blockiert den Import nie."""
    video_id = youtube_enrich.youtube_video_id(source)
    if not video_id:
        return [], []
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        if youtube_enrich.has_cookies():
            try:
                info = youtube_enrich.probe(source)
                timestamps = youtube_enrich.frame_timestamps(info["duration"], info["chapters"])
                video = youtube_enrich.download_video(source, workdir)
                frames = youtube_enrich.extract_frames(video, timestamps, workdir)
                attachments = []
                for frame in frames:
                    attachments.extend(upload_attachment(frame))
                return attachments, youtube_enrich.chapter_lines(info["chapters"])
            except Exception as exc:
                print(f"Cookies-Frames fehlgeschlagen ({video_id}), Fallback Watch-Page: {exc}")
        else:
            print(f"kein Cookies-File ({youtube_enrich.COOKIES_FILE}) — Frames-Tier übersprungen")
        kapitel: list[str] = []
        try:
            kapitel = youtube_enrich.chapter_lines(
                youtube_enrich.scrape_watch_chapters(video_id))
        except Exception as exc:
            print(f"Watch-Page-Kapitel fehlgeschlagen ({video_id}): {exc}")
        try:
            thumb = youtube_enrich.download_thumbnail(video_id, workdir)
            return upload_attachment(thumb), kapitel
        except Exception as exc:
            print(f"Thumbnail-Fallback fehlgeschlagen ({video_id}): {exc}")
            return [], kapitel


def import_note(path: Path, vault: Path) -> int | None:
    fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    payload = {
        "Title": fm.get("title") or path.stem,
        "Status": "Not Started",
    }
    # Kategorie ist strikte SingleSelect (Ausdauer/Kraft/Entspannung/Flexibility) —
    # ohne Frontmatter-Wert Feld weglassen statt ungültige Default-Option senden (400)
    if fm.get("kategorie"):
        payload["Kategorie"] = fm["kategorie"]
    if fm.get("source"):
        payload["Quelle"] = fm["source"]
    notiz = body.strip()
    media = find_media(body, path, vault)
    if media:
        payload["Medium"] = upload_attachment(media)
    else:
        attachments, kapitel = enrich_media(fm.get("source", ""))
        if attachments:
            payload["Medium"] = attachments
        if kapitel:
            notiz = "\n".join(kapitel) + "\n\n" + notiz
    if notiz:
        payload["Notiz"] = notiz[:2000]
    r = requests.post(
        f"{NOCODB_HOST_URL}/api/v2/tables/{SPORT_TABLE_ID}/records",
        headers={"xc-token": NOCODB_API_TOKEN, "Content-Type": "application/json"},
        json=payload,
    )
    if r.status_code not in (200, 201):
        print(f"FEHLER Row-Create ({path.name}): {r.status_code} {r.text[:200]}")
        return None
    row_id = r.json()["Id"]
    write_back_id(path, row_id)
    notify_import(payload["Title"], len(payload.get("Medium") or []))
    return row_id


def main() -> int:
    pending = find_pending(VAULT_PATH)
    if not pending:
        print("0/0 Notes importiert")
        return 0
    ok = 0
    for note in pending:
        try:
            row_id = import_note(note, VAULT_PATH)
        except Exception as exc:  # einzelne kaputte Note blockiert den Rest nicht
            print(f"FEHLER {note.name}: {exc}")
            continue
        if row_id:
            print(f"importiert: {note.name} -> Row {row_id}")
            ok += 1
    print(f"{ok}/{len(pending)} Notes importiert")
    return 0


if __name__ == "__main__":
    sys.exit(main())

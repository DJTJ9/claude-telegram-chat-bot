#!/usr/bin/env python3
"""YouTube-Zugriff für den Sport-Clip-Import: Video-ID-Parsing,
Frame-Timestamp-Berechnung (Kapitel-Mitte — Übungen werden erst erklärt,
dann ausgeführt), yt-dlp-Probe/-Download, ffmpeg-Frame-Extraktion,
Thumbnail-Fallback. Kein NocoDB-Wissen — reine Medien-Beschaffung."""
import json
import os
import re
import subprocess
from pathlib import Path

import requests

_YT_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^#]*&)?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)

MAX_FRAMES = 10
FALLBACK_FRAMES = 6
DOWNLOAD_TIMEOUT = 180  # Sekunden — hängender Download darf den Timer-Lauf nicht halten

COOKIES_FILE = os.environ.get("YOUTUBE_COOKIES_FILE", "/root/secrets/youtube_cookies.txt")
WATCH_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def has_cookies() -> bool:
    return Path(COOKIES_FILE).is_file()


def _cookie_args() -> list[str]:
    return ["--cookies", COOKIES_FILE] if has_cookies() else []


def youtube_video_id(url: str) -> str | None:
    m = _YT_ID_RE.search(url or "")
    return m.group(1) if m else None


def frame_timestamps(duration: float, chapters: list[dict]) -> list[float]:
    if chapters:
        mids = [(c["start_time"] + c["end_time"]) / 2 for c in chapters]
        if len(mids) > MAX_FRAMES:
            step = len(mids) / MAX_FRAMES
            mids = [mids[int(i * step)] for i in range(MAX_FRAMES)]
        return mids
    if duration <= 0:
        return []
    # 5–95 % der Dauer — Intro/Outro-Ränder meiden
    return [duration * (0.05 + 0.90 * i / (FALLBACK_FRAMES - 1)) for i in range(FALLBACK_FRAMES)]


def chapter_lines(chapters: list[dict]) -> list[str]:
    lines = []
    for c in chapters:
        s = int(c["start_time"])
        lines.append(f"{s // 60:02d}:{s % 60:02d} {c['title']}")
    return lines


def probe(url: str) -> dict:
    r = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", "--no-playlist", *_cookie_args(), url],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(f"yt-dlp probe fehlgeschlagen: {r.stderr[:200]}")
    info = json.loads(r.stdout)
    return {"duration": float(info.get("duration") or 0), "chapters": info.get("chapters") or []}


def download_video(url: str, workdir: Path) -> Path:
    r = subprocess.run(
        ["yt-dlp", "-f", "worst[height>=360]/worst", "--no-playlist", *_cookie_args(),
         "-o", str(workdir / "video.%(ext)s"), url],
        capture_output=True, text=True, timeout=DOWNLOAD_TIMEOUT,
    )
    if r.returncode != 0:
        raise RuntimeError(f"yt-dlp download fehlgeschlagen: {r.stderr[:200]}")
    videos = [p for p in workdir.iterdir() if p.stem == "video"]
    if not videos:
        raise RuntimeError("yt-dlp: kein Video-File nach Download")
    return videos[0]


def extract_frames(video: Path, timestamps: list[float], workdir: Path) -> list[Path]:
    frames = []
    for i, ts in enumerate(timestamps, 1):
        frame = workdir / f"uebung_{i:02d}.jpg"
        r = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", str(video),
             "-frames:v", "1", "-q:v", "3", str(frame)],
            capture_output=True, timeout=60,
        )
        if r.returncode == 0 and frame.exists():
            frames.append(frame)
    if not frames:
        raise RuntimeError("ffmpeg: keine Frames extrahiert")
    return frames


def download_thumbnail(video_id: str, workdir: Path) -> Path:
    for variant in ("maxresdefault", "hqdefault"):
        r = requests.get(f"https://img.youtube.com/vi/{video_id}/{variant}.jpg", timeout=30)
        if r.status_code == 200 and r.content:
            p = workdir / "thumbnail.jpg"
            p.write_bytes(r.content)
            return p
    raise RuntimeError(f"kein Thumbnail für {video_id}")


def _parse_clock(ts: str) -> int:
    seconds = 0
    for part in ts.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds


def _balanced_json(text: str, start: int) -> dict | None:
    """JSON-Objekt ab text[start]=='{' per Klammer-Zählung ausschneiden."""
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def scrape_watch_chapters(video_id: str) -> list[dict]:
    """Kapitel aus der Watch-Page (macroMarkersListItemRenderer). Funktioniert auch
    bei LOGIN_REQUIRED-IP-Block, wo yt-dlp keine Player-Daten bekommt — die
    Storyboard-Spec fehlt dort, die Kapitel-Marker werden aber ausgeliefert
    (live verifiziert 2026-07-05)."""
    r = requests.get(
        f"https://www.youtube.com/watch?v={video_id}",
        headers={"User-Agent": WATCH_UA, "Accept-Language": "de,en;q=0.8"},
        timeout=30,
    )
    if r.status_code != 200:
        return []
    by_start: dict[int, dict] = {}
    for m in re.finditer(r'"macroMarkersListItemRenderer":\{', r.text):
        obj = _balanced_json(r.text, m.end() - 1)
        if not obj:
            continue
        title = (obj.get("title") or {}).get("simpleText")
        ts = (obj.get("timeDescription") or {}).get("simpleText")
        if not title or not ts or not re.fullmatch(r"[\d:]+", ts):
            continue
        start = _parse_clock(ts)
        by_start.setdefault(start, {"title": title, "start_time": start})
    return [by_start[k] for k in sorted(by_start)]

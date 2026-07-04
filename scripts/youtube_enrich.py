#!/usr/bin/env python3
"""YouTube-Zugriff für den Sport-Clip-Import: Video-ID-Parsing,
Frame-Timestamp-Berechnung (Kapitel-Mitte — Übungen werden erst erklärt,
dann ausgeführt), yt-dlp-Probe/-Download, ffmpeg-Frame-Extraktion,
Thumbnail-Fallback. Kein NocoDB-Wissen — reine Medien-Beschaffung."""
import json
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

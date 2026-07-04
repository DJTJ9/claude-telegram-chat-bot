"""Tests für scripts/youtube_enrich.py — URL-Parsing, Timestamp-Berechnung,
Kapitelliste, subprocess-Wrapper. Netzwerk + Subprocesses komplett gemockt."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import youtube_enrich as ye


class TestYoutubeVideoId:
    def test_watch_url(self):
        assert ye.youtube_video_id("https://www.youtube.com/watch?v=nm-fxV-bwWg") == "nm-fxV-bwWg"

    def test_watch_url_with_extra_params(self):
        assert ye.youtube_video_id("https://www.youtube.com/watch?t=10&v=nm-fxV-bwWg") == "nm-fxV-bwWg"

    def test_short_url(self):
        assert ye.youtube_video_id("https://youtu.be/nm-fxV-bwWg") == "nm-fxV-bwWg"

    def test_shorts_url(self):
        assert ye.youtube_video_id("https://www.youtube.com/shorts/nm-fxV-bwWg") == "nm-fxV-bwWg"

    def test_non_youtube_returns_none(self):
        assert ye.youtube_video_id("https://example.com/burpees") is None

    def test_empty_returns_none(self):
        assert ye.youtube_video_id("") is None


def _chap(start, end, title="Übung"):
    return {"start_time": start, "end_time": end, "title": title}


class TestFrameTimestamps:
    def test_chapter_middles(self):
        chapters = [_chap(0, 60), _chap(60, 120), _chap(120, 300)]
        assert ye.frame_timestamps(300, chapters) == [30.0, 90.0, 210.0]

    def test_more_than_ten_chapters_sampled_to_ten(self):
        chapters = [_chap(i * 10, (i + 1) * 10) for i in range(14)]
        ts = ye.frame_timestamps(140, chapters)
        assert len(ts) == 10
        assert ts[0] == 5.0          # Mitte des ersten Kapitels
        assert ts == sorted(ts)      # aufsteigend

    def test_no_chapters_six_equidistant_5_to_95_percent(self):
        ts = ye.frame_timestamps(600, [])
        assert len(ts) == 6
        assert ts[0] == 30.0         # 5 %
        assert ts[-1] == 570.0       # 95 %

    def test_zero_duration_no_chapters_returns_empty(self):
        assert ye.frame_timestamps(0, []) == []


class TestChapterLines:
    def test_formats_mm_ss(self):
        chapters = [_chap(0, 90, "Intro"), _chap(90, 150, "Knee to Chest")]
        assert ye.chapter_lines(chapters) == ["00:00 Intro", "01:30 Knee to Chest"]

    def test_empty_chapters(self):
        assert ye.chapter_lines([]) == []

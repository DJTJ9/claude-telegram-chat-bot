"""Tests für scripts/youtube_enrich.py — URL-Parsing, Timestamp-Berechnung,
Kapitelliste, subprocess-Wrapper. Netzwerk + Subprocesses komplett gemockt."""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import youtube_enrich as ye
from scripts import youtube_enrich


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


class TestProbe:
    @patch.object(ye, "subprocess")
    def test_parses_duration_and_chapters(self, mock_sub):
        mock_sub.run.return_value = MagicMock(
            returncode=0,
            stdout='{"duration": 380.0, "chapters": [{"start_time": 0, "end_time": 90, "title": "Intro"}]}',
        )
        info = ye.probe("https://www.youtube.com/watch?v=nm-fxV-bwWg")
        assert info["duration"] == 380.0
        assert len(info["chapters"]) == 1

    @patch.object(ye, "subprocess")
    def test_missing_chapters_becomes_empty_list(self, mock_sub):
        mock_sub.run.return_value = MagicMock(returncode=0, stdout='{"duration": 55}')
        assert ye.probe("u")["chapters"] == []

    @patch.object(ye, "subprocess")
    def test_nonzero_exit_raises(self, mock_sub):
        mock_sub.run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR: geo blocked")
        try:
            ye.probe("u")
            assert False, "RuntimeError erwartet"
        except RuntimeError as exc:
            assert "geo blocked" in str(exc)


class TestDownloadVideo:
    @patch.object(ye, "subprocess")
    def test_returns_downloaded_file(self, mock_sub, tmp_path):
        def fake_run(cmd, **kw):
            (tmp_path / "video.mp4").write_bytes(b"vid")
            return MagicMock(returncode=0, stderr="")
        mock_sub.run.side_effect = fake_run
        assert ye.download_video("u", tmp_path).name == "video.mp4"

    @patch.object(ye, "subprocess")
    def test_nonzero_exit_raises(self, mock_sub, tmp_path):
        mock_sub.run.return_value = MagicMock(returncode=1, stderr="ERROR: 403")
        try:
            ye.download_video("u", tmp_path)
            assert False, "RuntimeError erwartet"
        except RuntimeError:
            pass


class TestExtractFrames:
    @patch.object(ye, "subprocess")
    def test_one_frame_per_timestamp(self, mock_sub, tmp_path):
        def fake_run(cmd, **kw):
            Path(cmd[-1]).write_bytes(b"\xff\xd8jpg")
            return MagicMock(returncode=0)
        mock_sub.run.side_effect = fake_run
        frames = ye.extract_frames(tmp_path / "v.mp4", [30.0, 90.0], tmp_path)
        assert [f.name for f in frames] == ["uebung_01.jpg", "uebung_02.jpg"]

    @patch.object(ye, "subprocess")
    def test_all_failed_raises(self, mock_sub, tmp_path):
        mock_sub.run.return_value = MagicMock(returncode=1)
        try:
            ye.extract_frames(tmp_path / "v.mp4", [30.0], tmp_path)
            assert False, "RuntimeError erwartet"
        except RuntimeError:
            pass


class TestDownloadThumbnail:
    @patch.object(ye, "requests")
    def test_maxres_first(self, mock_req, tmp_path):
        mock_req.get.return_value = MagicMock(status_code=200, content=b"jpg")
        p = ye.download_thumbnail("nm-fxV-bwWg", tmp_path)
        assert p.read_bytes() == b"jpg"
        assert "maxresdefault" in mock_req.get.call_args_list[0].args[0]

    @patch.object(ye, "requests")
    def test_falls_back_to_hqdefault(self, mock_req, tmp_path):
        mock_req.get.side_effect = [
            MagicMock(status_code=404, content=b""),
            MagicMock(status_code=200, content=b"jpg"),
        ]
        assert ye.download_thumbnail("x", tmp_path).exists()
        assert "hqdefault" in mock_req.get.call_args_list[1].args[0]

    @patch.object(ye, "requests")
    def test_both_fail_raises(self, mock_req, tmp_path):
        mock_req.get.return_value = MagicMock(status_code=404, content=b"")
        try:
            ye.download_thumbnail("x", tmp_path)
            assert False, "RuntimeError erwartet"
        except RuntimeError:
            pass


def test_has_cookies_false_wenn_file_fehlt(monkeypatch, tmp_path):
    monkeypatch.setattr(youtube_enrich, "COOKIES_FILE", str(tmp_path / "nope.txt"))
    assert youtube_enrich.has_cookies() is False


def test_probe_und_download_geben_cookies_flag_weiter(monkeypatch, tmp_path):
    cookies = tmp_path / "youtube_cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setattr(youtube_enrich, "COOKIES_FILE", str(cookies))
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        class R:
            returncode = 0
            stdout = json.dumps({"duration": 60, "chapters": []})
            stderr = ""
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    youtube_enrich.probe("https://www.youtube.com/watch?v=abcdefghijk")
    (tmp_path / "video.mp4").write_bytes(b"x")
    # download_video sucht video.* im workdir — fake_run lädt nichts, Datei liegt schon da
    youtube_enrich.download_video("https://www.youtube.com/watch?v=abcdefghijk", tmp_path)
    for cmd in calls:
        i = cmd.index("--cookies")
        assert cmd[i + 1] == str(cookies)


def test_probe_ohne_cookies_file_kein_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(youtube_enrich, "COOKIES_FILE", str(tmp_path / "nope.txt"))
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        class R:
            returncode = 0
            stdout = json.dumps({"duration": 60, "chapters": []})
            stderr = ""
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    youtube_enrich.probe("https://www.youtube.com/watch?v=abcdefghijk")
    assert "--cookies" not in calls[0]


WATCH_HTML_FIXTURE = (
    'irrelevant{"macroMarkersListItemRenderer":{"title":{"simpleText":"EINLEITUNG"},'
    '"timeDescription":{"accessibility":{"accessibilityData":{"label":"0 Sekunden"}},'
    '"simpleText":"0:00"},"thumbnail":{"thumbnails":[]},"onTap":{}}}mehr'
    '{"macroMarkersListItemRenderer":{"title":{"simpleText":"KNIE ZUR BRUST"},'
    '"timeDescription":{"accessibility":{"accessibilityData":{"label":"73 Sekunden"}},'
    '"simpleText":"1:13"},"thumbnail":{"thumbnails":[]},"onTap":{}}}'
    # Duplikat (Engagement-Panel listet Kapitel doppelt) — muss dedupliziert werden
    '{"macroMarkersListItemRenderer":{"title":{"simpleText":"EINLEITUNG"},'
    '"timeDescription":{"accessibility":{"accessibilityData":{"label":"0 Sekunden"}},'
    '"simpleText":"0:00"},"thumbnail":{"thumbnails":[]},"onTap":{}}}'
    # Marker ohne Titel (z.B. Heatmap) — muss ignoriert werden
    '{"macroMarkersListItemRenderer":{"timeDescription":{"simpleText":"0:30"},"onTap":{}}}'
)


def test_scrape_watch_chapters_parst_dedupliziert_und_sortiert(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        assert "watch?v=abcdefghijk" in url
        class R:
            status_code = 200
            text = WATCH_HTML_FIXTURE
        return R()

    monkeypatch.setattr(youtube_enrich.requests, "get", fake_get)
    chapters = youtube_enrich.scrape_watch_chapters("abcdefghijk")
    assert chapters == [
        {"title": "EINLEITUNG", "start_time": 0},
        {"title": "KNIE ZUR BRUST", "start_time": 73},
    ]
    # kompatibel zu chapter_lines()
    assert youtube_enrich.chapter_lines(chapters) == ["00:00 EINLEITUNG", "01:13 KNIE ZUR BRUST"]


def test_scrape_watch_chapters_leere_liste_bei_http_fehler(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        class R:
            status_code = 429
            text = ""
        return R()

    monkeypatch.setattr(youtube_enrich.requests, "get", fake_get)
    assert youtube_enrich.scrape_watch_chapters("abcdefghijk") == []

"""Tests für scripts/sport_clip_import.py — Parsing, Media-Auflösung, Idempotenz.
Netzwerk komplett gemockt; synthetischer Vault in tmp_path."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import sport_clip_import as sci


NOTE = """---
title: 100 Burpees Challenge
kategorie: Kraft
source: https://example.com/burpees
nocodb_id:
---
Jeden Tag 100 Burpees, 30 Tage lang.

![[burpees.jpg]]
"""


def _make_vault(tmp_path):
    vault = tmp_path / "vault"
    clips = vault / "Sport Challenges"
    clips.mkdir(parents=True)
    (clips / "2026-07-04-burpees.md").write_text(NOTE, encoding="utf-8")
    (vault / "burpees.jpg").write_bytes(b"\xff\xd8fakejpg")
    return vault


class TestParseFrontmatter:
    def test_parses_fields_and_body(self):
        fm, body = sci.parse_frontmatter(NOTE)
        assert fm["title"] == "100 Burpees Challenge"
        assert fm["kategorie"] == "Kraft"
        assert fm["source"] == "https://example.com/burpees"
        assert fm["nocodb_id"] == ""
        assert "100 Burpees" in body

    def test_no_frontmatter_returns_empty(self):
        fm, body = sci.parse_frontmatter("nur text")
        assert fm == {} and body == "nur text"


class TestFindMedia:
    def test_resolves_wikilink_embed_from_vault_root(self, tmp_path):
        vault = _make_vault(tmp_path)
        note = vault / "Sport Challenges" / "2026-07-04-burpees.md"
        _, body = sci.parse_frontmatter(note.read_text(encoding="utf-8"))
        media = sci.find_media(body, note, vault)
        assert media is not None and media.name == "burpees.jpg"

    def test_ignores_remote_and_nonmedia(self, tmp_path):
        vault = _make_vault(tmp_path)
        note = vault / "Sport Challenges" / "2026-07-04-burpees.md"
        body = "![](https://cdn.example.com/x.jpg)\n![[notes.pdf]]"
        assert sci.find_media(body, note, vault) is None

    def test_markdown_style_embed(self, tmp_path):
        vault = _make_vault(tmp_path)
        note = vault / "Sport Challenges" / "2026-07-04-burpees.md"
        assert sci.find_media("![alt](burpees.jpg)", note, vault).name == "burpees.jpg"


class TestFindPending:
    def test_finds_note_without_id(self, tmp_path):
        vault = _make_vault(tmp_path)
        assert len(sci.find_pending(vault)) == 1

    def test_skips_note_with_id(self, tmp_path):
        vault = _make_vault(tmp_path)
        note = vault / "Sport Challenges" / "2026-07-04-burpees.md"
        note.write_text(NOTE.replace("nocodb_id:", "nocodb_id: 42"), encoding="utf-8")
        assert sci.find_pending(vault) == []

    def test_missing_clip_dir_returns_empty(self, tmp_path):
        assert sci.find_pending(tmp_path / "leer") == []

    def test_finds_note_in_lowercase_clip_dir(self, tmp_path):
        # LiveSync (case-insensitive Handling) legt Pfade lowercase im Spiegel ab
        vault = tmp_path / "vault"
        (vault / "sport challenges").mkdir(parents=True)
        (vault / "sport challenges" / "2026-07-04-stretch.md").write_text(
            "---\ntitle: Stretch\nnocodb_id:\n---\nText.\n", encoding="utf-8"
        )
        assert len(sci.find_pending(vault)) == 1

    def test_both_case_variants_scanned(self, tmp_path):
        vault = _make_vault(tmp_path)
        (vault / "sport challenges").mkdir()
        (vault / "sport challenges" / "2026-07-04-stretch.md").write_text(
            "---\ntitle: Stretch\nnocodb_id:\n---\nText.\n", encoding="utf-8"
        )
        assert len(sci.find_pending(vault)) == 2


class TestImportNote:
    @patch.object(sci, "requests")
    def test_creates_row_and_writes_back_id(self, mock_requests, tmp_path):
        vault = _make_vault(tmp_path)
        note = vault / "Sport Challenges" / "2026-07-04-burpees.md"
        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = [{"url": "download/burpees.jpg", "title": "burpees.jpg"}]
        create_resp = MagicMock(status_code=200)
        create_resp.json.return_value = {"Id": 77}
        mock_requests.post.side_effect = [upload_resp, create_resp]

        row_id = sci.import_note(note, vault)

        assert row_id == 77
        row_payload = mock_requests.post.call_args_list[1].kwargs["json"]
        assert row_payload["Title"] == "100 Burpees Challenge"
        assert row_payload["Kategorie"] == "Kraft"
        assert row_payload["Status"] == "Not Started"
        assert row_payload["Quelle"] == "https://example.com/burpees"
        assert "nocodb_id: 77" in note.read_text(encoding="utf-8")

    @patch.object(sci, "requests")
    def test_second_run_is_idempotent(self, mock_requests, tmp_path):
        vault = _make_vault(tmp_path)
        note = vault / "Sport Challenges" / "2026-07-04-burpees.md"
        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = [{"url": "x", "title": "burpees.jpg"}]
        create_resp = MagicMock(status_code=200)
        create_resp.json.return_value = {"Id": 77}
        mock_requests.post.side_effect = [upload_resp, create_resp]
        sci.import_note(note, vault)

        assert sci.find_pending(vault) == []

    @patch.object(sci, "requests")
    def test_note_without_media_still_imported(self, mock_requests, tmp_path):
        vault = _make_vault(tmp_path)
        note = vault / "Sport Challenges" / "no-media.md"
        note.write_text("---\ntitle: Plank Challenge\nnocodb_id:\n---\n5 min Plank.\n", encoding="utf-8")
        create_resp = MagicMock(status_code=200)
        create_resp.json.return_value = {"Id": 78}
        mock_requests.post.side_effect = [create_resp]

        assert sci.import_note(note, vault) == 78
        row_payload = mock_requests.post.call_args_list[0].kwargs["json"]
        assert "Medium" not in row_payload
        # Kategorie ist strikte SingleSelect — ohne Frontmatter-Wert wird das Feld weggelassen
        assert "Kategorie" not in row_payload


YT_NOTE = """---
title: Stretching Routine
kategorie: Flexibility
source: https://www.youtube.com/watch?v=nm-fxV-bwWg
nocodb_id:
---
Follow-along Routine.
"""


def _make_yt_vault(tmp_path):
    vault = tmp_path / "vault"
    clips = vault / "Sport Challenges"
    clips.mkdir(parents=True)
    note = clips / "2026-07-04-stretch.md"
    note.write_text(YT_NOTE, encoding="utf-8")
    return vault, note


class TestEnrichMedia:
    @patch.object(sci, "youtube_enrich")
    @patch.object(sci, "requests")
    def test_frames_uploaded_and_chapters_prefixed(self, mock_requests, mock_ye, tmp_path):
        vault, note = _make_yt_vault(tmp_path)
        mock_ye.youtube_video_id.return_value = "nm-fxV-bwWg"
        mock_ye.probe.return_value = {"duration": 380.0, "chapters": [{"start_time": 90, "end_time": 150, "title": "Knee to Chest"}]}
        mock_ye.frame_timestamps.return_value = [120.0]
        mock_ye.chapter_lines.return_value = ["01:30 Knee to Chest"]

        def fake_download(url, workdir):
            return workdir / "video.mp4"
        def fake_extract(video, timestamps, workdir):
            f = workdir / "uebung_01.jpg"
            f.write_bytes(b"\xff\xd8jpg")
            return [f]
        mock_ye.download_video.side_effect = fake_download
        mock_ye.extract_frames.side_effect = fake_extract

        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = [{"url": "download/uebung_01.jpg", "title": "uebung_01.jpg"}]
        create_resp = MagicMock(status_code=200)
        create_resp.json.return_value = {"Id": 9}
        mock_requests.post.side_effect = [upload_resp, create_resp]

        row_id = sci.import_note(note, vault)

        assert row_id == 9
        payload = mock_requests.post.call_args_list[1].kwargs["json"]
        assert payload["Medium"] == [{"url": "download/uebung_01.jpg", "title": "uebung_01.jpg"}]
        assert payload["Notiz"].startswith("01:30 Knee to Chest")
        assert "Follow-along Routine." in payload["Notiz"]

    @patch.object(sci, "youtube_enrich")
    @patch.object(sci, "requests")
    def test_enrich_failure_falls_back_to_thumbnail(self, mock_requests, mock_ye, tmp_path):
        vault, note = _make_yt_vault(tmp_path)
        mock_ye.youtube_video_id.return_value = "nm-fxV-bwWg"
        mock_ye.probe.side_effect = RuntimeError("geo blocked")

        def fake_thumb(video_id, workdir):
            p = workdir / "thumbnail.jpg"
            p.write_bytes(b"\xff\xd8jpg")
            return p
        mock_ye.download_thumbnail.side_effect = fake_thumb

        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = [{"url": "download/thumbnail.jpg", "title": "thumbnail.jpg"}]
        create_resp = MagicMock(status_code=200)
        create_resp.json.return_value = {"Id": 10}
        mock_requests.post.side_effect = [upload_resp, create_resp]

        assert sci.import_note(note, vault) == 10
        payload = mock_requests.post.call_args_list[1].kwargs["json"]
        assert payload["Medium"][0]["title"] == "thumbnail.jpg"
        assert payload["Notiz"].startswith("Follow-along")  # kein Kapitel-Präfix

    @patch.object(sci, "youtube_enrich")
    @patch.object(sci, "requests")
    def test_all_enrichment_fails_row_without_medium(self, mock_requests, mock_ye, tmp_path):
        vault, note = _make_yt_vault(tmp_path)
        mock_ye.youtube_video_id.return_value = "nm-fxV-bwWg"
        mock_ye.probe.side_effect = RuntimeError("down")
        mock_ye.download_thumbnail.side_effect = RuntimeError("404")

        create_resp = MagicMock(status_code=200)
        create_resp.json.return_value = {"Id": 11}
        mock_requests.post.return_value = create_resp

        assert sci.import_note(note, vault) == 11
        payload = mock_requests.post.call_args_list[0].kwargs["json"]
        assert "Medium" not in payload

    @patch.object(sci, "youtube_enrich")
    @patch.object(sci, "requests")
    def test_non_youtube_source_skips_enrichment(self, mock_requests, mock_ye, tmp_path):
        vault = tmp_path / "vault"
        clips = vault / "Sport Challenges"
        clips.mkdir(parents=True)
        note = clips / "no-yt.md"
        note.write_text("---\ntitle: Plank\nsource: https://example.com/x\nnocodb_id:\n---\nPlank.\n", encoding="utf-8")
        mock_ye.youtube_video_id.return_value = None

        create_resp = MagicMock(status_code=200)
        create_resp.json.return_value = {"Id": 12}
        mock_requests.post.return_value = create_resp

        assert sci.import_note(note, vault) == 12
        mock_ye.probe.assert_not_called()
        mock_ye.download_thumbnail.assert_not_called()

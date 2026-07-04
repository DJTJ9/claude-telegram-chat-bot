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
        assert row_payload["Kategorie"] == "Sport"  # Default

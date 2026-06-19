import os
os.environ.setdefault("GROQ_API_KEY", "test_key")

from unittest.mock import patch, MagicMock
from core.telegram import build_inline_keyboard

def test_abc_options():
    kb = build_inline_keyboard("Welche Option? A) Eins B) Zwei C) Drei")
    labels = [btn["text"] for row in kb for btn in row]
    assert "A" in labels
    assert "B" in labels
    assert "C" in labels
    assert "Freitext" in labels

def test_ja_nein():
    kb = build_inline_keyboard("Ist das richtig? ja oder nein")
    labels = [btn["text"] for row in kb for btn in row]
    assert "Ja" in labels
    assert "Nein" in labels

def test_unknown_question():
    kb = build_inline_keyboard("Was ist dein Name?")
    labels = [btn["text"] for row in kb for btn in row]
    assert "Freitext" in labels
    assert len([l for l in labels if l != "Freitext"]) == 0


def test_normalize_voice_replaces_doppelpunkt():
    from core.telegram import normalize_voice
    assert normalize_voice("status Doppelpunkt ok") == "status: ok"


def test_normalize_voice_replaces_komma():
    from core.telegram import normalize_voice
    assert normalize_voice("eins Komma zwei") == "eins, zwei"


def test_normalize_voice_replaces_punkt():
    from core.telegram import normalize_voice
    assert normalize_voice("Ende Punkt") == "Ende."


def test_normalize_voice_case_insensitive():
    from core.telegram import normalize_voice
    assert normalize_voice("test DOPPELPUNKT wert") == "test: wert"


def test_transcribe_voice_returns_text():
    from core.telegram import transcribe_voice

    get_file_resp = MagicMock()
    get_file_resp.json.return_value = {"result": {"file_path": "voice/file.ogg"}}

    audio_resp = MagicMock()
    audio_resp.content = b"fake_ogg_bytes"

    groq_mock = MagicMock()
    groq_mock.audio.transcriptions.create.return_value.text = "Hallo Welt"

    with patch("core.telegram.requests.get", side_effect=[get_file_resp, audio_resp]):
        with patch("core.telegram._groq_client", return_value=groq_mock):
            result = transcribe_voice("tok", "fileid123")

    assert result == "Hallo Welt"

import os
os.environ.setdefault("GROQ_API_KEY", "test_key")

from unittest.mock import patch, MagicMock


def test_transcribe_audio_returns_stripped_text(tmp_path):
    from scripts.voice_transcribe import transcribe_audio

    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"fake-audio-bytes")
    mock_resp = MagicMock()
    mock_resp.text = "  Hallo Welt  "

    with patch("scripts.voice_transcribe.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_resp
        mock_groq_cls.return_value = mock_client
        result = transcribe_audio(str(audio_file))

    assert result == "Hallo Welt"
    mock_client.audio.transcriptions.create.assert_called_once()


def test_transcribe_audio_uses_whisper_model(tmp_path):
    from scripts.voice_transcribe import transcribe_audio

    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"fake-audio-bytes")
    mock_resp = MagicMock()
    mock_resp.text = "test"

    with patch("scripts.voice_transcribe.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_resp
        mock_groq_cls.return_value = mock_client
        transcribe_audio(str(audio_file))

    call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
    assert call_kwargs["model"] == "whisper-large-v3"

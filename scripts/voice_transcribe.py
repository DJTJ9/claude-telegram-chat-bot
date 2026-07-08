import os
import sys
from pathlib import Path

from groq import Groq

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())


def transcribe_audio(audio_path: str) -> str:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), f.read()),
            model="whisper-large-v3",
        )
    return resp.text.strip()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: voice_transcribe.py <audio_file>", file=sys.stderr)
        sys.exit(1)
    print(transcribe_audio(sys.argv[1]))

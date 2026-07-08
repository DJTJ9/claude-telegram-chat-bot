import os
import sys

from groq import Groq


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

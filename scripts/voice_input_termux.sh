#!/data/data/com.termux/files/usr/bin/bash
set -e
LOCK_FILE="$HOME/.voice_input.lock"
AUDIO_FILE="$HOME/.voice_input.wav"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$LOCK_FILE" ]; then
    termux-microphone-record -q
    rm -f "$LOCK_FILE"
    echo -e "\033[33m● Transkribiere...\033[0m"
    TEXT=$(python3 "$SCRIPT_DIR/voice_transcribe.py" "$AUDIO_FILE")
    termux-clipboard-set "$TEXT"
    termux-toast "Text kopiert: $TEXT"
    echo -e "\033[0m"
else
    echo -e "\033[31m● REC\033[0m"
    termux-microphone-record -f "$AUDIO_FILE"
    touch "$LOCK_FILE"
fi

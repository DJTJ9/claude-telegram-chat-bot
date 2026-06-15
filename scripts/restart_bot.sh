#!/bin/bash
systemctl restart telegram-bot 2>/dev/null && exit 0
pkill -f "python.*bot\.py" 2>/dev/null
sleep 1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." && set -a && source .env && set +a && venv/bin/python bot.py &
echo "Bot restarted (pid=$!)"

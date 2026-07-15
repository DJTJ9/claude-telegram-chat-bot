#!/bin/bash
# Restart all bot-army services
for svc in bot-organizer bot-brain bot-teach; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        systemctl restart "$svc"
        echo "Restarted $svc"
    fi
done

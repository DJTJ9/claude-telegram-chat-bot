# LR-0010: Telegram-Bot mit Long Polling

Telegram Bot API funktioniert via Token + getUpdates-Polling. Chat-ID filtert auf eigene Nachrichten.
`$env:TELEGRAM_TOKEN` muss in derselben PowerShell-Session gesetzt sein wie `python bot.py`.
Webhook vorher löschen wenn aktiv: `deleteWebhook` via Browser-URL.

evidence: Bot empfängt Testnachrichten, antwortet mit "Empfangen: ...", Terminal zeigt Nachrichten live.

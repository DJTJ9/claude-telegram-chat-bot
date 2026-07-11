# Project Knowledge

@/root/projects-hub/topics/telegram-bot-army/DECISIONS.md
@/root/projects-hub/topics/telegram-bot-army/LEARNINGS.md

# Termin-Konvention (NocoDB)

`Datum`-Spalte (Typ Date) und `Uhrzeit`-Spalte (Typ Time, Format `HH:MM`) sind getrennte Felder — beide beim Anlegen eines Termins befüllen: `nocodb_direct.create_task(title, datum, prio, uhrzeit=...)`.


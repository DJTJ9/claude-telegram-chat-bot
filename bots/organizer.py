import os, sys, json, re, uuid, subprocess, threading, time
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from core.telegram import get_updates, send_message, build_inline_keyboard, answer_callback_query, transcribe_voice, normalize_voice, edit_message
from core.settings import load_settings, save_settings
from core.claude import run_claude, run_claude_with_history, run_claude_parse
from core.state import load_reminders, save_reminders, load_plans, save_plans, load_registry

TOKEN = os.environ["TOKEN_ORGANIZER"]
CHAT_ID = int(os.environ.get("CHAT_ID", "8896609541"))
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
HUB_DIR = Path(os.environ.get("HUB_DIR", str(WORK_DIR)))

HABITS_DATA_SOURCE_ID = "6a4d7e7d-dcde-44e3-b7a0-c46330a6261c"
BACKLOG_DATA_SOURCE_ID = "0cb18d17-cf70-413d-b29d-adb4675db614"
ARCHIV_DATA_SOURCE_ID  = "abb5abd8-e320-4796-bbf6-941feb9007b9"
BEREICHE = {"arbeit", "privat", "lernen", "gesundheit"}

REPLY_KEYBOARD = {
    "keyboard": [
        ["moin", "abend"],
        ["task:", "status:"],
        ["woche", "fokus:"],
        ["verschieben:", "hilfe"],
        ["backlog"],
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False,
    "persistent": True,
}

HILFE_TEXT = """📋 Organizer Bot

🌅 Tagesplanung
  moin — Tasks + fällige Habits für heute
  abend — Tagesabschluss
  woche — Wochenrückblick
  fokus: <Bereich> — Arbeit / Privat / Lernen / Gesundheit

✅ Tasks & Habits
  task: — Neuen Task anlegen (interaktiv)
  task: <text> — Neuen Task direkt anlegen
  habit: <text> — Neuen Habit anlegen
  termin: <text> — Termin anlegen
  backlog: <text> — Undatierte Aufgabe speichern
  backlog — Alle offenen Backlog-Tasks anzeigen
  status: <name> <status> — Status ändern
  verschieben: <datum> — Offene Tasks verschieben

📚 Listen
  lern: <thema> — Lernthema speichern
  idee: <text> — Spielidee speichern
  suche: <text> — Alle DBs durchsuchen

⏰ Erinnerungen
  erinnere mich um 14:00 an Zahnarzt
  erinnerung: <text>
  erinnerungen — alle offenen Erinnerungen anzeigen

🤖 Pläne
  /plans — geplante Implementierungen anzeigen
  implement-plan: <slug> um HH:MM
  implement-plan: <slug> jetzt
  abort-plan: <slug>

⚙️ Einstellungen
  impl-mode: an|aus — Implementierungs-Mode"""

TASK_SYSTEM_PROMPT = """Du bist ein Notion-Task-Assistent. Der Nutzer schickt eine Aufgabe als Freitext.
Lege die Aufgabe im Tagesorganizer an (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Leite aus dem Text ab: Name, Datum (ISO 8601, heute falls nicht angegeben), Priorität (Hoch/Mittel/Niedrig, Mittel falls nicht angegeben), Bereich (Arbeit/Privat/Lernen/Gesundheit, Privat falls unklar).
Antworte NUR mit einer Zeile: ✅ Task angelegt: [Name] · [Datum] · [Priorität] · [Bereich]"""

PROJEKT_TASKS_SYSTEM_PROMPT = """Du bist ein Notion-Projektassistent.
Lies den Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Zeige alle Tasks wo Property "Projekt" = dem angegebenen Projektnamen, Status Not started oder In progress.
Sortiere nach Priorität (Hoch zuerst), dann Datum.
Erste Zeile: "📁 [Projektname] – [N] offene Tasks"
Je Task: · [Epic falls gesetzt] [Priorität] [Name] — [Datum]
Kein Markdown."""

PROJEKT_TASK_SYSTEM_PROMPT = """Du bist ein Notion-Task-Assistent.
Lege einen Task im Tagesorganizer an (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Der Projektname wird vorgegeben — setze ihn als Property "Projekt".
Leite aus dem Text ab: Name, Datum (ISO 8601, heute falls nicht angegeben), Priorität (Hoch/Mittel/Niedrig, Mittel falls nicht angegeben), Bereich (Arbeit/Privat/Lernen/Gesundheit, Arbeit falls Projekt gesetzt).
Antworte NUR mit einer Zeile: ✓ Task angelegt: [Name] · [Projekt] · [Priorität] · [Datum]"""

WOCHE_SYSTEM_PROMPT = """Du bist ein Notion-Wochenassistent.
Lies den Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Zeige alle Tasks der letzten 7 Tage (inkl. heute).
Format:
1) Erste Zeile: "📅 Wochenrückblick (DD.MM – DD.MM)"
2) Abschnitt "✅ Erledigt (N):" — Tasks mit Status Done
   je Zeile: · Bereich · Priorität · Name
3) Abschnitt "⏳ Offen (N):" — Tasks Not started / In progress
   je Zeile: · Bereich · Priorität · Name
Sortiere Offen nach Priorität (Hoch zuerst). Kein Markdown."""

FOKUS_SYSTEM_PROMPT = """Du bist ein Notion-Fokusassistent.
Lies den Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Zeige alle Tasks mit dem genannten Bereich, Datum heute,
Status Not started oder In progress. Sortiere nach Priorität (Hoch zuerst).
Format pro Task: · [Priorität] [Name] — [Notiz falls vorhanden]
Erste Zeile: "🎯 Fokus: [Bereich] – [N] Tasks heute"
Falls keine Tasks: "🎯 Fokus: [Bereich] – nichts geplant für heute."
Kein Markdown."""

VERSCHIEBEN_SYSTEM_PROMPT = """Du bist ein Notion-Planungsassistent.
Lies den Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Finde alle Tasks mit Status Not started oder In progress.
Setze ihr Datum-Feld auf das vom Nutzer angegebene Datum.
"morgen" = heute + 1 Tag. Wochentage relativ zu heute berechnen.
Antworte NUR mit: "📆 N Tasks verschoben auf [Datum]."
Falls keine offenen Tasks: "Keine offenen Tasks zum Verschieben."
Kein Markdown."""

ABEND_SYSTEM_PROMPT = """Du bist ein Notion-Abend-Assistent.
Lies den Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Zeige alle Tasks mit Datum = heute.

Format:

Zeile 1: "🌙 Tagesabschluss [DD.MM.YYYY]"
Leerzeile

Abschnitt 1: "✅ Heute erledigt ([N]):"
Je Task: · [→Projekt falls gesetzt] [Name]
Falls keine: · (nichts heute abgehakt)

Leerzeile

Abschnitt 2: "⏳ Noch offen ([N]):"
Je Task: · [Prio-Icon] [→Projekt falls gesetzt] [Name]
Prio-Icons: Hoch=🔴 Mittel=🟡 Niedrig=🟢
Sortiere nach Priorität (Hoch zuerst).
Falls keine: · (alles erledigt — gut gemacht!)

Leerzeile

Abschnitt 3: "📊 Projekt-Bilanz:"
Je Projekt das heute Tasks hat:
· [Name]: [N_done] erledigt / [N_offen] offen
Falls N_done = 0: füge " — kein Fortschritt heute" hinzu.
Falls keine Projekt-Tasks heute: · (keine Projekt-Tasks heute)

Leerzeile
"💡 Offene Tasks verschieben? → verschieben: morgen"
Kein Markdown."""

MOIN_SYSTEM_PROMPT = f"""Du bist ein Notion-Morgen-Assistent.
Lies den Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Finde alle Tasks mit Datum = heute ODER ohne Datum, Status Not started oder In progress.

Trenne in zwei Gruppen:
- Termine: Tasks wo Datum einen Zeitanteil hat (datetime, z.B. 2026-06-15T14:00)
- Tasks: Tasks wo Datum nur ein Datum ist (date-only) oder kein Datum gesetzt ist

Format:
Zeile 1: "🌅 Guten Morgen! [DD.MM.YYYY]"
Zeile 2 (nur wenn Projekt-Tasks vorhanden): "📁 " + je Projekt "[Name] ([N])"-Gruppen mit " · " getrennt (nur Tasks zählen, nicht Termine)
Leerzeile

Falls Termine vorhanden:
  "📅 Termine heute ([N]):"
  Je Termin: "· [HH:MM] · [Name]"
  Sortiert nach Uhrzeit aufsteigend.
  Leerzeile

Falls Tasks vorhanden:
  "📋 Tasks heute ([N]):"
  Je Task: "· [Prio-Icon] [→Projekt falls gesetzt] [Name]"
  Prio-Icons: Hoch=🔴 Mittel=🟡 Niedrig=🟢
  Sortiert nach Priorität (Hoch zuerst), dann alphabetisch.
  Leerzeile

Dann lies die Habits-Datenbank (data_source_id: {HABITS_DATA_SOURCE_ID}).
Zeige alle Habits mit Nächste Fälligkeit ≤ heute UND Status = Aktiv.
Falls solche Habits vorhanden:
  "🔄 Habits heute ([N]):"
  Je Habit: "· [Name] (alle [Intervall] Tage)"
Falls keine fälligen Habits: diese Sektion weglassen.

Kein Markdown. Kein Datum in der Task-Liste."""

LERN_SYSTEM_PROMPT = """Du bist ein Lernthemen-Assistent. Der Nutzer nennt ein Thema, das er lernen möchte.
Lege es in der Lernthemen-Datenbank an (data_source_id: 5a76447f-2b0a-4f6b-81bb-853f39aa04bb).
Leite aus dem Text ab: Name, Kategorie (Programmierung/Sprachen/Mathematik/Design/Sonstiges, Programmierung falls unklar), Priorität (Mittel falls nicht angegeben).
Antworte NUR mit einer Zeile: 📚 Lernthema gespeichert: [Name] · [Kategorie] · [Priorität]"""

IDEE_SYSTEM_PROMPT = """Du bist ein Spieleideen-Assistent. Der Nutzer beschreibt eine Spielidee.
Lege sie in der Spieleideen-Datenbank an (data_source_id: ce6783d1-54fe-421f-8d7d-aa8c34880853).
Leite aus dem Text ab:
- Name: kurzer prägnanter Titel
- Typ: Neues Spiel / Game Mechanic / Erweiterung / Mod (Neues Spiel falls unklar)
- Genre: ein oder mehrere aus: Strategy, RPG, Puzzle, Action, Simulation, Idle, Horror, Platformer
- Plattform: PC falls nicht genannt
- Status: immer "Idee"
- Beschreibung: die vollständige Idee des Nutzers unverändert übernehmen
Antworte NUR mit einer Zeile: 🎮 Spielidee gespeichert: [Name] · [Typ] · [Genre]"""

HABIT_SYSTEM_PROMPT = """Du bist ein Habit-Assistent. Der Nutzer beschreibt einen wiederkehrenden Habit.
Lege ihn in der Habits-Datenbank an (data_source_id: 6a4d7e7d-dcde-44e3-b7a0-c46330a6261c).
Leite aus dem Text ab:
- Name: kurzer Titel des Habits
- Intervall: Anzahl Tage als Zahl (täglich=1, wöchentlich=7, alle N Tage=N)
- Bereich: Arbeit/Privat/Lernen/Gesundheit (leer lassen falls nicht angegeben)
- Nächste Fälligkeit: das heutige Datum (aus dem Nutzer-Prompt)
- Status: Aktiv
Antworte NUR mit einer Zeile: 🔄 Habit angelegt: [Name] · alle [Intervall] Tage · ab heute"""

STATUS_SYSTEM_PROMPT = f"""Du bist ein Notion-Status-Assistent.

Schritt 1 — Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0):
Finde den Task per fuzzy-Suche (Name muss nicht exakt übereinstimmen).
Mappe den Status:
  erledigt / fertig / done → Done
  in arbeit / läuft / gestartet / in progress → In progress
  offen / zurück / nicht gestartet → Not started
Setze den Status. Merke ob ein Task gefunden wurde.

Schritt 2 — Habits-DB (data_source_id: {HABITS_DATA_SOURCE_ID}):
Nur ausführen falls "erledigt", "fertig" oder "done" im Text.
Finde den Habit per fuzzy-Suche.
Falls gefunden:
  - Berechne Nächste Fälligkeit = heutiges Datum + Intervall (Tage, aus Property "Intervall")
  - Setze Nächste Fälligkeit auf dieses Datum und lasse Status = Aktiv
Merke ob ein Habit gefunden wurde.

Antworte:
- Nur Task gefunden: "✅ [Task Name] → [Status]"
- Nur Habit gefunden: "🔄 Habit '[Name]' erledigt — nächste Fälligkeit: [Datum DD.MM.YYYY]"
- Beides gefunden: beide Zeilen
- Nichts gefunden: "❌ Kein passender Task/Habit gefunden: \\"[Eingabe]\\""
Kein Markdown."""

TERMIN_SYSTEM_PROMPT = """Du bist ein Notion-Termin-Assistent.
Lege den Termin im Tagesorganizer an (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Leite aus dem Text ab:
- Name: Bezeichnung des Termins
- Datum: ISO 8601 datetime YYYY-MM-DDTHH:MM:SS
  Falls kein Datum: heute. Falls keine Uhrzeit: 09:00.
  "morgen" = heute + 1 Tag, Wochentage relativ zu heute.
  "um 14" oder "14 Uhr" → 14:00:00, "halb drei" → 14:30:00
Antworte NUR mit einer Zeile: 📅 Termin angelegt: [Name] · [DD.MM.YYYY um HH:MM]"""

BACKLOG_SYSTEM_PROMPT = f"""Du bist ein Notion-Backlog-Assistent. Der Nutzer nennt eine Aufgabe ohne festen Termin.
Lege sie im Backlog an (data_source_id: {BACKLOG_DATA_SOURCE_ID}).
Leite ab: Name, Priorität (Hoch/Mittel/Niedrig, Mittel falls nicht angegeben), Bereich (Arbeit/Privat/Lernen/Gesundheit, Privat falls unklar).
Status immer: Offen.
Antworte NUR mit einer Zeile: 📌 Backlog-Task angelegt: [Name] · [Priorität] · [Bereich]"""

BACKLOG_LIST_SYSTEM_PROMPT = f"""Du bist ein Notion-Backlog-Assistent.
Lies den Backlog (data_source_id: {BACKLOG_DATA_SOURCE_ID}).
Zeige alle Tasks mit Status = Offen, sortiert nach Priorität (Hoch zuerst).
Format:
Zeile 1: "📌 Backlog ([N] offen):"
Je Task: "[N]. [Prio-Icon] [Name] — [Bereich]"
Prio-Icons: Hoch=🔴 Mittel=🟡 Niedrig=🟢
Falls keine offenen Tasks: "📌 Backlog leer."
Kein Markdown."""

BACKLOG_PROMOTE_SYSTEM_PROMPT = f"""Du bist ein Notion-Backlog-Assistent.
Schritt 1: Finde den Task mit der genannten Nummer aus der Backlog-Liste (fuzzy-Suche auf den Namen).
Schritt 2: Lege neuen Task im Tagesorganizer an (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
  Übernehme: Name, Priorität, Bereich, Notiz.
  Setze Datum = angegebenes Zieldatum (ISO 8601). "morgen" = heute + 1 Tag.
  Status = Not started.
Schritt 3: Setze den Backlog-Task auf Status = Erledigt (data_source_id: {BACKLOG_DATA_SOURCE_ID}).
Antworte NUR mit: "✅ [Name] → Tagesorganizer für [DD.MM.YYYY]"
Kein Markdown."""

ARCHIVE_LOOP_SYSTEM_PROMPT = f"""Du bist ein Notion-Archiv-Assistent.
Archiviere alle erledigten Tasks aus dem Tagesorganizer und dem Backlog ins Task-Archiv.

Schritt 1 — Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0):
Finde alle Tasks mit Status = Done.
Für jeden: Lege Eintrag im Task-Archiv an (data_source_id: {ARCHIV_DATA_SOURCE_ID}).
Kopiere: Name, Status, Priorität, Datum, Bereich, Notiz. Setze "Archiviert am" = heutiges Datum (ISO 8601).
Archiviere dann den Original-Task (archived: true).

Schritt 2 — Backlog (data_source_id: {BACKLOG_DATA_SOURCE_ID}):
Finde alle Tasks mit Status = Erledigt.
Für jeden: Lege Eintrag im Task-Archiv an. Datum = leer. "Archiviert am" = heutiges Datum.
Archiviere dann den Original-Backlog-Task.

Antworte NUR mit: "✅ Archiviert: N Tasks" oder "Nichts zu archivieren."
Kein Markdown."""

SUCHE_SYSTEM_PROMPT = """Du bist ein Notion-Suchassistent.
Der Nutzer gibt einen Suchbegriff. Suche in allen 5 Datenbanken:

1. Tagesorganizer  (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0) — Felder: Name, Notiz
2. Backlog         (data_source_id: 0cb18d17-cf70-413d-b29d-adb4675db614) — Felder: Name, Notiz
3. Task-Archiv     (data_source_id: abb5abd8-e320-4796-bbf6-941feb9007b9) — Felder: Name, Notiz
4. Lernthemen      (data_source_id: 5a76447f-2b0a-4f6b-81bb-853f39aa04bb) — Felder: Name, Notiz
5. Spieleideen     (data_source_id: ce6783d1-54fe-421f-8d7d-aa8c34880853) — Felder: Name, Beschreibung

Für jede DB: nutze contains-Filter auf Name ODER das Textfeld (OR-Verknüpfung).
Zeige nur DBs mit Treffern. Sortiere Treffer pro DB nach Priorität falls vorhanden.

Format:
Zeile 1: "🔍 Suche: \\"[Begriff]\\""
Leerzeile
Je DB mit Treffern:
  "[Icon] [DB-Name] ([N])"
  Je Treffer: "  · [Status-Icon] [Name][— Datum falls gesetzt]"
  Leerzeile
Letzte Zeile: "🔍 [Gesamt] Treffer in [M] Datenbank(en)."
Falls keine Treffer: "🔍 Keine Ergebnisse für \\"[Begriff]\\"."

Status-Icons: Not started/Offen=⬜ In progress/In Bearbeitung=🔄 Done/Erledigt/Abgeschlossen=✅
DB-Icons: 📋 Tagesorganizer, 📦 Backlog, 🗂 Archiv, 📚 Lernthemen, 🎮 Spieleideen
Kein Markdown."""

REMINDER_PARSE_SYSTEM_PROMPT = """Du bist ein Erinnerungs-Parser. Deine einzige Aufgabe: Text analysieren und JSON zurückgeben.

WICHTIG: Führe KEINE Aktionen aus. Nutze KEINE Tools. Sende KEINE Nachrichten. Schreibe KEINEN Code.

Extrahiere aus dem Nutzer-Text:
- text: Was soll erinnert werden
- due: Fälligkeitszeitpunkt als ISO 8601 (YYYY-MM-DDTHH:MM:SS)

Regeln:
- "morgen" = heute + 1 Tag, "übermorgen" = heute + 2 Tage
- Falls kein Datum: heute
- Falls keine Uhrzeit: 09:00
- "um 14" oder "14 Uhr" → 14:00:00
- "halb drei" → 14:30:00, "Viertel nach acht" → 08:15:00

Antworte AUSSCHLIESSLICH mit diesem JSON (kein Markdown, keine Erklärung, nichts anderes):
{"text": "<was erinnert werden soll>", "due": "<YYYY-MM-DDTHH:MM:SS>"}"""

CHAT_SYSTEM_PROMPT = """Du bist ein hilfreicher persönlicher Assistent-Bot. Antworte kurz und direkt auf Fragen und Konversation.
Führe KEINE Aktionen aus. Nutze KEINE Tools. Erstelle KEINE Schedules oder Routines. Antworte NUR mit Text."""

MOIN_JSON_SYSTEM_PROMPT = f"""Du bist ein Notion-Morgen-Assistent.
Lies den Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Finde alle Tasks mit Datum = heute ODER ohne Datum, Status Not started oder In progress.

Gruppen:
- appointments: Tasks mit Datum als datetime (z.B. 2026-06-22T14:00) — sortiert nach Uhrzeit
- tasks: Tasks mit nur Datum (date-only) oder ohne Datum — sortiert nach Prio (Hoch zuerst)

Lies dann Habits-Datenbank (data_source_id: {HABITS_DATA_SOURCE_ID}).
- habits: Habits mit Nächste Fälligkeit <= heute UND Status = Aktiv — sortiert alphabetisch

Antworte AUSSCHLIESSLICH mit diesem JSON (kein Markdown, keine Erklärung):
{{
  "date": "YYYY-MM-DD",
  "appointments": [{{"name": "...", "time": "HH:MM", "id": "<page_id_ohne_bindestriche_32_zeichen>"}}],
  "tasks": [{{"name": "...", "prio": "Hoch|Mittel|Niedrig", "projekt": "...|null", "id": "<page_id_ohne_bindestriche_32_zeichen>"}}],
  "habits": [{{"name": "...", "interval": <int_tage>, "id": "<page_id_ohne_bindestriche_32_zeichen>"}}]
}}
page_id: Notion page ID als Hex-String ohne Bindestriche, exakt 32 Zeichen."""

ABEND_JSON_SYSTEM_PROMPT = f"""Du bist ein Notion-Abend-Assistent.
Lies den Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Finde alle Tasks mit Datum = heute.

Lies dann Habits-Datenbank (data_source_id: {HABITS_DATA_SOURCE_ID}).
missed_habits: Habits mit Nächste Fälligkeit <= heute UND Status = Aktiv.

Antworte AUSSCHLIESSLICH mit diesem JSON (kein Markdown, keine Erklärung):
{{
  "date": "YYYY-MM-DD",
  "done": [{{"name": "...", "projekt": "...|null"}}],
  "open": [{{"name": "...", "prio": "Hoch|Mittel|Niedrig", "projekt": "...|null", "id": "<page_id_ohne_bindestriche_32_zeichen>"}}],
  "missed_habits": [{{"name": "...", "id": "<page_id_ohne_bindestriche_32_zeichen>"}}],
  "projekt_bilanz": [{{"name": "...", "done": <int>, "open": <int>}}]
}}
Sortiere open nach prio (Hoch zuerst). projekt_bilanz nur für Projekte mit Tasks heute."""

TASK_UPDATE_SYSTEM_PROMPT = """Du bist ein Notion-Update-Assistent.
Du erhältst eine Notion page_id und ein zu aktualisierendes Feld mit dem neuen Wert.
Aktualisiere direkt diese Page (kein Suchen nötig).
Felder:
  prio/priorität → Property "Priorität" (select: Hoch/Mittel/Niedrig)
  datum → Property "Datum" (date: ISO 8601 YYYY-MM-DD)
  bereich → Property "Bereich" (select: Arbeit/Privat/Lernen/Gesundheit)
  notiz → Property "Notiz" (rich_text)
  status → Property "Status" (status: Done/In progress/Not started)
Antworte NUR mit einer Zeile: ✏️ <Feld> → <Wert>
Falls Page nicht gefunden: ❌ Page nicht gefunden: <page_id>"""

HABIT_DONE_SYSTEM_PROMPT = f"""Du bist ein Habit-Assistent.
Du erhältst eine Notion page_id aus der Habits-Datenbank (data_source_id: {HABITS_DATA_SOURCE_ID}).
1. Lese den Habit — Properties "Name" und "Intervall" (Anzahl Tage als Zahl)
2. Berechne Nächste Fälligkeit = heutiges Datum + Intervall Tage (ISO 8601)
3. Setze Property "Nächste Fälligkeit" auf dieses Datum. Status bleibt "Aktiv".
Antworte NUR mit: ✅ <Name> — nächste Fälligkeit: DD.MM.YYYY
Falls nicht gefunden: ❌ Habit nicht gefunden: <page_id>"""

EDIT_SYSTEM_PROMPT = """Du bist ein Notion-Edit-Assistent.
Nutzer-Eingabe: "<taskname> <feld> <wert>"
1. Suche Task im Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0) per fuzzy-Suche
2. Erkenne Feld: prio/priorität → Priorität | datum → Datum | bereich → Bereich | notiz → Notiz
3. Mappe Wert:
   Prio: hoch→Hoch, mittel→Mittel, niedrig→Niedrig
   Bereich: arbeit→Arbeit, privat→Privat, lernen→Lernen, gesundheit→Gesundheit
   Datum: morgen=heute+1, übermorgen=heute+2, ISO-Datum direkt, Wochentag relativ berechnen
4. Aktualisiere die Property
Antworte NUR mit: ✏️ <Task-Name> · <Feld> → <Wert>
Falls nicht gefunden: ❌ Task nicht gefunden: "<Eingabe>" """

PRIO_ICONS = {"Hoch": "🔴", "Mittel": "🟡", "Niedrig": "🟢"}

callback_state: dict = {}   # {chat_id: {action, page_id, task_name, field?, msg_id?}}
vs_state: dict = {}         # {chat_id: {pending, selected, tasks}}


def _extract_name_from_message(text: str) -> str:
    first_line = text.split("\n")[0].strip()
    for icon in ("🔴 ", "🟡 ", "🟢 ", "⏳ ", "⚠️ ", "🔄 "):
        if first_line.startswith(icon):
            first_line = first_line[len(icon):]
            break
    if "  →" in first_line:
        first_line = first_line[:first_line.index("  →")]
    return first_line.strip()


def _resolve_date_key(key: str, today: str) -> str:
    d = date.fromisoformat(today)
    offsets = {"heute": 0, "morgen": 1, "uebermorgen": 2, "naechste_woche": 7}
    return (d + timedelta(days=offsets.get(key, 0))).isoformat()


def _resolve_value(field: str, value_key: str, today: str) -> str:
    if field == "prio":
        return {"hoch": "Hoch", "mittel": "Mittel", "niedrig": "Niedrig"}.get(value_key, value_key)
    if field == "bereich":
        return {"arbeit": "Arbeit", "privat": "Privat",
                "lernen": "Lernen", "gesundheit": "Gesundheit"}.get(value_key, value_key)
    if field == "datum":
        return _resolve_date_key(value_key, today)
    return value_key


def _task_buttons(page_id: str) -> list:
    return [[
        {"text": "✅ Erledigt",    "callback_data": f"done:{page_id}"},
        {"text": "📅 Verschieben", "callback_data": f"reschedule:{page_id}"},
        {"text": "✏️ Bearbeiten",  "callback_data": f"edit:{page_id}"},
    ]]


conversation_history: dict = {}
pending_task_input: dict = {}


def _apply_task_update(page_id: str, field: str, value: str, today: str = None) -> str:
    today = today or date.today().isoformat()
    prompt = f"Heute ist {today}. page_id: {page_id}. Feld: {field}. Wert: {value}."
    return run_claude(prompt, system_prompt=TASK_UPDATE_SYSTEM_PROMPT, automated=True)


def _send_task_message(task: dict) -> None:
    pid = task["id"].replace("-", "")
    prio_icon = PRIO_ICONS.get(task.get("prio", ""), "")
    text = f"{prio_icon} {task['name']}" if prio_icon else task["name"]
    if task.get("projekt"):
        text += f"  →{task['projekt']}"
    send_message(TOKEN, CHAT_ID, text, reply_markup={"inline_keyboard": _task_buttons(pid)})


def _send_habit_message(habit: dict) -> None:
    pid = habit["id"].replace("-", "")
    freq = "täglich" if habit.get("interval", 1) == 1 else f"alle {habit['interval']} Tage"
    text = f"🔄 {habit['name']} ({freq})"
    buttons = [[{"text": "✅ Erledigt", "callback_data": f"habit_done:{pid}"}]]
    send_message(TOKEN, CHAT_ID, text, reply_markup={"inline_keyboard": buttons})


def _send_moin_messages(data: dict) -> None:
    try:
        d = date.fromisoformat(data.get("date", date.today().isoformat()))
        today_str = d.strftime("%d.%m.%Y")
    except ValueError:
        today_str = data.get("date", "")

    tasks = data.get("tasks", [])
    projects: dict = {}
    for t in tasks:
        if t.get("projekt"):
            projects[t["projekt"]] = projects.get(t["projekt"], 0) + 1

    header = f"🌅 Guten Morgen! {today_str}"
    if projects:
        proj_str = " · ".join(f"{p} ({n})" for p, n in sorted(projects.items()))
        header += f"\n📁 {proj_str}"
    send_message(TOKEN, CHAT_ID, header, reply_markup=REPLY_KEYBOARD)

    appts = data.get("appointments", [])
    if appts:
        lines = [f"📅 Termine heute ({len(appts)}):"]
        for a in appts:
            lines.append(f"· {a['time']} · {a['name']}")
        send_message(TOKEN, CHAT_ID, "\n".join(lines))

    for task in tasks:
        _send_task_message(task)

    for habit in data.get("habits", []):
        _send_habit_message(habit)

    if not tasks and not data.get("habits"):
        send_message(TOKEN, CHAT_ID, "Nichts zu tun heute 🎉")


def _send_abend_messages(data: dict) -> None:
    try:
        d = date.fromisoformat(data.get("date", date.today().isoformat()))
        today_str = d.strftime("%d.%m.%Y")
    except ValueError:
        today_str = data.get("date", "")

    done = data.get("done", [])
    open_tasks = data.get("open", [])
    bilanz = data.get("projekt_bilanz", [])

    lines = [f"🌙 Tagesabschluss {today_str}", ""]
    lines.append(f"✅ Heute erledigt ({len(done)}):")
    if done:
        for t in done:
            prefix = f"→{t['projekt']} " if t.get("projekt") else ""
            lines.append(f"· {prefix}{t['name']}")
    else:
        lines.append("· (nichts heute abgehakt)")

    if bilanz:
        lines.append("")
        lines.append("📊 Projekt-Bilanz:")
        for p in bilanz:
            lines.append(f"· {p['name']}: {p['done']} erledigt / {p['open']} offen")

    send_message(TOKEN, CHAT_ID, "\n".join(lines), reply_markup=REPLY_KEYBOARD)

    for task in open_tasks:
        pid = task["id"].replace("-", "")
        prio_icon = PRIO_ICONS.get(task.get("prio", ""), "")
        text = f"⏳ {task['name']}"
        if task.get("projekt"):
            text += f"  →{task['projekt']}"
        if prio_icon:
            text += f"\n{prio_icon} ({task.get('prio', '')})"
        send_message(TOKEN, CHAT_ID, text, reply_markup={"inline_keyboard": _task_buttons(pid)})

    for habit in data.get("missed_habits", []):
        pid = habit["id"].replace("-", "")
        buttons = [[{"text": "✅ Nachträglich erledigen", "callback_data": f"habit_done:{pid}"}]]
        send_message(TOKEN, CHAT_ID,
                     f"⚠️ {habit['name']} — heute fällig, nicht erledigt",
                     reply_markup={"inline_keyboard": buttons})


def _check_vs_done(chat_id: int, today: str) -> None:
    state = vs_state.get(chat_id)
    if not state or state.get("pending"):
        return
    if not state.get("selected"):
        send_message(TOKEN, chat_id, "Keine Tasks ausgewählt.")
        vs_state.pop(chat_id, None)
        return
    n = len(state["selected"])
    buttons = [[
        {"text": "Morgen",        "callback_data": "vs_confirm:morgen"},
        {"text": "Übermorgen",     "callback_data": "vs_confirm:uebermorgen"},
    ], [
        {"text": "Nächste Woche",  "callback_data": "vs_confirm:naechste_woche"},
        {"text": "Datum eingeben", "callback_data": "vs_confirm:freitext"},
    ]]
    send_message(TOKEN, chat_id,
                 f"{n} Task(s) ausgewählt. Auf welches Datum verschieben?",
                 reply_markup={"inline_keyboard": buttons})


def _run_vs_bulk(chat_id: int, target_date: str, today: str) -> None:
    state = vs_state.pop(chat_id, {})
    selected = state.get("selected", [])
    if not selected:
        send_message(TOKEN, chat_id, "Keine Tasks ausgewählt.", reply_markup=REPLY_KEYBOARD)
        return
    for pid in selected:
        run_claude(
            f"Heute ist {today}. page_id: {pid}. Feld: datum. Wert: {target_date}.",
            system_prompt=TASK_UPDATE_SYSTEM_PROMPT, automated=True,
        )
    d = date.fromisoformat(target_date)
    send_message(TOKEN, chat_id,
                 f"📆 {len(selected)} Task(s) verschoben auf {d.strftime('%d.%m.%Y')}.",
                 reply_markup=REPLY_KEYBOARD)


def _handle_callback(cq: dict) -> None:
    chat_id: int = cq["from"]["id"]
    data: str = cq.get("data", "")
    msg_id: int = cq["message"]["message_id"]
    msg_text: str = cq["message"].get("text", "")
    today: str = date.today().isoformat()

    if data.startswith("done:"):
        pid = data[5:]
        run_claude(
            f"Heute ist {today}. page_id: {pid}. Feld: status. Wert: Done.",
            system_prompt=TASK_UPDATE_SYSTEM_PROMPT, automated=True,
        )
        edit_message(TOKEN, chat_id, msg_id, f"✅ {_extract_name_from_message(msg_text)} — erledigt!")
        threading.Thread(target=_run_archive_once, daemon=True).start()

    elif data.startswith("habit_done:"):
        pid = data[11:]
        result = run_claude(
            f"Heute ist {today}. page_id: {pid}.",
            system_prompt=HABIT_DONE_SYSTEM_PROMPT, automated=True,
        )
        edit_message(TOKEN, chat_id, msg_id, result)

    elif data.startswith("reschedule:") and data.count(":") == 1:
        pid = data[11:]
        buttons = [[
            {"text": "Morgen",        "callback_data": f"reschedule_d:{pid}:morgen"},
            {"text": "Übermorgen",     "callback_data": f"reschedule_d:{pid}:uebermorgen"},
        ], [
            {"text": "Nächste Woche",  "callback_data": f"reschedule_d:{pid}:naechste_woche"},
            {"text": "Datum eingeben", "callback_data": f"reschedule_d:{pid}:freitext"},
        ]]
        edit_message(TOKEN, chat_id, msg_id, msg_text, {"inline_keyboard": buttons})

    elif data.startswith("reschedule_d:"):
        parts = data.split(":", 2)
        pid, date_key = parts[1], parts[2]
        if date_key == "freitext":
            callback_state[chat_id] = {
                "action": "reschedule_text", "page_id": pid,
                "task_name": _extract_name_from_message(msg_text), "msg_id": msg_id,
            }
            send_message(TOKEN, chat_id, "Welches Datum? (z.B. 2026-06-25)")
        else:
            target = _resolve_date_key(date_key, today)
            _apply_task_update(pid, "datum", target, today)
            d = date.fromisoformat(target)
            edit_message(TOKEN, chat_id, msg_id,
                         f"📅 {_extract_name_from_message(msg_text)} → {d.strftime('%d.%m.')}")

    elif data.startswith("edit:") and data.count(":") == 1:
        pid = data[5:]
        buttons = [[
            {"text": "Priorität", "callback_data": f"edit_f:{pid}:prio"},
            {"text": "Datum",     "callback_data": f"edit_f:{pid}:datum"},
        ], [
            {"text": "Bereich",   "callback_data": f"edit_f:{pid}:bereich"},
            {"text": "Notiz",     "callback_data": f"edit_f:{pid}:notiz"},
        ]]
        edit_message(TOKEN, chat_id, msg_id, msg_text, {"inline_keyboard": buttons})

    elif data.startswith("edit_f:"):
        parts = data.split(":", 2)
        pid, field = parts[1], parts[2]
        if field == "prio":
            buttons = [[
                {"text": "Hoch",    "callback_data": f"edit_v:{pid}:prio:hoch"},
                {"text": "Mittel",  "callback_data": f"edit_v:{pid}:prio:mittel"},
                {"text": "Niedrig", "callback_data": f"edit_v:{pid}:prio:niedrig"},
            ]]
        elif field == "datum":
            buttons = [[
                {"text": "Heute",      "callback_data": f"edit_v:{pid}:datum:heute"},
                {"text": "Morgen",     "callback_data": f"edit_v:{pid}:datum:morgen"},
            ], [
                {"text": "Übermorgen", "callback_data": f"edit_v:{pid}:datum:uebermorgen"},
                {"text": "Eingeben",   "callback_data": f"edit_v:{pid}:datum:freitext"},
            ]]
        elif field == "bereich":
            buttons = [[
                {"text": "Arbeit",      "callback_data": f"edit_v:{pid}:bereich:arbeit"},
                {"text": "Privat",      "callback_data": f"edit_v:{pid}:bereich:privat"},
            ], [
                {"text": "Lernen",      "callback_data": f"edit_v:{pid}:bereich:lernen"},
                {"text": "Gesundheit",  "callback_data": f"edit_v:{pid}:bereich:gesundheit"},
            ]]
        elif field == "notiz":
            task_name = _extract_name_from_message(msg_text)
            callback_state[chat_id] = {
                "action": "edit_text", "page_id": pid, "field": "notiz",
                "task_name": task_name, "msg_id": msg_id,
            }
            send_message(TOKEN, chat_id, f"Neue Notiz für '{task_name}':")
            return
        else:
            return
        edit_message(TOKEN, chat_id, msg_id, msg_text, {"inline_keyboard": buttons})

    elif data.startswith("edit_v:"):
        parts = data.split(":", 3)
        pid, field, value_key = parts[1], parts[2], parts[3]
        if value_key == "freitext":
            callback_state[chat_id] = {
                "action": "edit_text" if field != "datum" else "reschedule_text",
                "page_id": pid, "field": field,
                "task_name": _extract_name_from_message(msg_text), "msg_id": msg_id,
            }
            send_message(TOKEN, chat_id,
                         "Neue Notiz eingeben:" if field == "notiz" else "Neues Datum? (z.B. 2026-06-25)")
            return
        value = _resolve_value(field, value_key, today)
        _apply_task_update(pid, field, value, today)
        edit_message(TOKEN, chat_id, msg_id,
                     f"✏️ {_extract_name_from_message(msg_text)} · {field.capitalize()} → {value}")

    elif data.startswith("vs_select:"):
        pid = data[10:]
        state = vs_state.get(chat_id)
        if not state:
            return
        if pid in state["selected"]:
            state["selected"].remove(pid)
            icon = "☐"
        else:
            state["selected"].append(pid)
            if pid in state.get("pending", []):
                state["pending"].remove(pid)
            icon = "☑"
        buttons = [[
            {"text": f"{icon} Auswählen", "callback_data": f"vs_select:{pid}"},
            {"text": "Überspringen",       "callback_data": f"vs_skip:{pid}"},
        ]]
        edit_message(TOKEN, chat_id, msg_id, msg_text, {"inline_keyboard": buttons})
        _check_vs_done(chat_id, today)

    elif data.startswith("vs_skip:"):
        pid = data[8:]
        state = vs_state.get(chat_id)
        if state and pid in state.get("pending", []):
            state["pending"].remove(pid)
        edit_message(TOKEN, chat_id, msg_id, msg_text)
        _check_vs_done(chat_id, today)

    elif data.startswith("vs_confirm:"):
        date_key = data[11:]
        if date_key == "freitext":
            callback_state[chat_id] = {"action": "vs_date", "msg_id": msg_id}
            send_message(TOKEN, chat_id, "Welches Datum? (z.B. 2026-06-25)")
        else:
            _run_vs_bulk(chat_id, _resolve_date_key(date_key, today), today)


def _add_reminder(text, due_iso):
    reminders = load_reminders()
    reminders.append({
        "id": str(uuid.uuid4())[:8],
        "text": text,
        "due": due_iso,
        "status": "pending",
        "chat_id": CHAT_ID,
        "created": datetime.now().isoformat(timespec="seconds"),
    })
    save_reminders(reminders)
    subprocess.run(["git", "-C", str(WORK_DIR), "add", "reminders.json"], capture_output=True)
    subprocess.run(["git", "-C", str(WORK_DIR), "commit", "-m", f"chore: add reminder '{text[:40]}'"], capture_output=True)


def _check_and_send_reminders():
    try:
        reminders = load_reminders()
        now = datetime.now()
        changed = False
        for r in reminders:
            if r["status"] == "pending" and datetime.fromisoformat(r["due"]) <= now:
                send_message(TOKEN, CHAT_ID, f"⏰ Erinnerung: {r['text']}")
                r["status"] = "sent"
                changed = True
        if changed:
            save_reminders(reminders)
            subprocess.run(["git", "-C", str(WORK_DIR), "add", "reminders.json"], capture_output=True)
            subprocess.run(["git", "-C", str(WORK_DIR), "commit", "-m", "chore: mark reminders sent"], capture_output=True)
    except Exception as e:
        print(f"reminder check error: {e}")


def _run_archive_once():
    try:
        run_claude(f"Heute ist {date.today().isoformat()}.", system_prompt=ARCHIVE_LOOP_SYSTEM_PROMPT, automated=True)
    except Exception as e:
        print(f"archive error: {e}")


def _run_plan(plan_path, slug=None):
    if plan_path.startswith("topics/"):
        base_dir = str(HUB_DIR)
        resolved = (HUB_DIR / plan_path).resolve()
        allowed = (HUB_DIR / "topics").resolve()
    else:
        base_dir = str(WORK_DIR)
        resolved = (WORK_DIR / plan_path).resolve()
        allowed = (WORK_DIR / "docs" / "superpowers" / "plans").resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError:
        send_message(TOKEN, CHAT_ID, f"❌ Ungültiger Plan-Pfad: {plan_path}")
        return
    prompt = (
        "Follow the implementation plan exactly. "
        f"Plan file: {plan_path}\n"
        "Read the plan file and implement every task step by step. Commit all changes when done."
    )
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=3600, cwd=base_dir)
    if result.returncode != 0:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=3600, cwd=base_dir)
    success = result.returncode == 0
    if slug:
        plans = load_plans()
        for p in plans:
            if p["slug"] == slug:
                p["status"] = "done" if success else "failed"
                break
        save_plans(plans)
        subprocess.run(["git", "-C", str(HUB_DIR), "add", "scheduled_plans.json"], capture_output=True)
        subprocess.run(["git", "-C", str(HUB_DIR), "commit", "-m", f"chore: plan {slug} -> {'done' if success else 'failed'}"], capture_output=True)
    label = slug or plan_path
    if success:
        send_message(TOKEN, CHAT_ID, f"✅ Implementierung abgeschlossen: {label}")
    else:
        send_message(TOKEN, CHAT_ID, f"❌ Implementierung fehlgeschlagen: {label}\n{(result.stderr or '')[-500:]}")


def _schedule_plan(slug, scheduled_time):
    plans = load_plans()
    for plan in plans:
        if plan["slug"] == slug:
            plan["scheduled_time"] = scheduled_time
            save_plans(plans)
            subprocess.run(["git", "-C", str(HUB_DIR), "add", "scheduled_plans.json"], capture_output=True)
            subprocess.run(["git", "-C", str(HUB_DIR), "commit", "-m", f"chore: schedule plan {slug} at {scheduled_time}"], capture_output=True)
            return f"⏰ {slug} geplant für {scheduled_time}"
    return f"❌ Kein Plan mit slug '{slug}' gefunden"


def _abort_plan(slug):
    plans = load_plans()
    for plan in plans:
        if plan["slug"] == slug:
            if plan["status"] == "running":
                return "⚠️ Plan läuft gerade — abbrechen nicht möglich"
            new_plans = [p for p in plans if p["slug"] != slug]
            save_plans(new_plans)
            subprocess.run(["git", "-C", str(HUB_DIR), "add", "scheduled_plans.json"], capture_output=True)
            subprocess.run(["git", "-C", str(HUB_DIR), "commit", "-m", f"chore: remove plan {slug}"], capture_output=True)
            return f"🗑 {slug} entfernt"
    return f"❌ Kein Plan mit slug '{slug}' gefunden"


def _format_plans():
    plans = [p for p in load_plans() if p["status"] in ("pending", "running")]
    if not plans:
        return "Keine ausstehenden Pläne."
    scheduled = [p for p in plans if p.get("scheduled_time")]
    waiting   = [p for p in plans if not p.get("scheduled_time")]
    lines = ["📋 Geplante Implementierungen"]
    if scheduled:
        lines.append("\n⏰ Geplant:")
        for p in scheduled:
            lines.append(f"• {p['slug']} — {p['scheduled_time']}")
    if waiting:
        lines.append("\n📌 Wartend (kein Termin):")
        for p in waiting:
            lines.append(f"• {p['slug']}")
    return "\n".join(lines)


def _plan_loop():
    while True:
        time.sleep(60)
        try:
            now = datetime.now().strftime("%H:%M")
            plans = load_plans()
            for plan in plans:
                if plan["status"] == "pending" and plan.get("scheduled_time") == now:
                    plan["status"] = "running"
                    save_plans(plans)
                    subprocess.run(["git", "-C", str(HUB_DIR), "add", "scheduled_plans.json"], capture_output=True)
                    subprocess.run(["git", "-C", str(HUB_DIR), "commit", "-m", f"chore: plan {plan['slug']} -> running"], capture_output=True)
                    send_message(TOKEN, CHAT_ID, f"🚀 Starte Implementierung: {plan['slug']}")
                    threading.Thread(target=_run_plan, args=(plan["plan_path"], plan["slug"]), daemon=True).start()
        except Exception as e:
            print(f"plan loop error: {e}")


def _get_projects():
    return {p["slug"]: {"path": p.get("path", ""), "notion_name": p.get("name", p["slug"])} for p in load_registry()}


def main():
    global conversation_history

    plans = load_plans()
    for p in plans:
        if p["status"] == "running":
            p["status"] = "pending"
    save_plans(plans)

    threading.Thread(target=_plan_loop, daemon=True).start()

    def _reminder_loop():
        while True:
            _check_and_send_reminders()
            time.sleep(60)

    def _archive_loop():
        while True:
            time.sleep(1800)
            _run_archive_once()

    threading.Thread(target=_reminder_loop, daemon=True).start()
    threading.Thread(target=_archive_loop, daemon=True).start()

    offset = None
    print(f"Organizer Bot gestartet (chat_id={CHAT_ID})")

    while True:
        try:
            updates = get_updates(TOKEN, offset=offset)
            for upd in updates:
                offset = upd["update_id"] + 1

                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    if cq["from"]["id"] != CHAT_ID:
                        continue
                    answer_callback_query(TOKEN, cq["id"])
                    if cq.get("data") == "__freitext__":
                        send_message(TOKEN, CHAT_ID, "Bitte Antwort eintippen:")
                    continue

                msg = upd.get("message", {})
                if not msg:
                    continue
                chat_id = msg.get("chat", {}).get("id")
                if chat_id != CHAT_ID:
                    continue

                if "voice" in msg:
                    try:
                        raw = transcribe_voice(TOKEN, msg["voice"]["file_id"])
                        text = normalize_voice(raw)
                    except Exception as e:
                        send_message(TOKEN, CHAT_ID, f"❌ Spracheingabe fehlgeschlagen: {e}")
                        continue
                else:
                    text = msg.get("text", "").strip()
                if not text:
                    continue

                today = date.today().isoformat()

                if chat_id in pending_task_input:
                    state = pending_task_input[chat_id]
                    _is_cmd = (
                        text.lower() in ("moin", "abend", "woche", "hilfe", "erinnerungen", "/plans", "backlog")
                        or any(text.lower().startswith(p) for p in (
                            "task:", "status:", "fokus:", "verschieben:", "lern:", "idee:",
                            "habit:", "termin:", "erinnere", "erinnerung:",
                            "implement-plan:", "abort-plan:", "backlog:", "suche:", "impl-mode:"))
                    )
                    if _is_cmd:
                        del pending_task_input[chat_id]
                    elif state == "task_menu":
                        del pending_task_input[chat_id]
                        choice = text.strip().upper()
                        if choice in ("A", "1"):
                            pending_task_input[chat_id] = "task_input"
                            send_message(TOKEN, CHAT_ID,
                                "Schreib mir: Name, Priorität (Hoch/Mittel/Niedrig), Bereich (Arbeit/Privat/Lernen/Gesundheit)\nz.B.: Arzttermin, Hoch, Gesundheit",
                                reply_markup=REPLY_KEYBOARD)
                        elif choice in ("B", "2"):
                            send_message(TOKEN, CHAT_ID, "⏳ Lade Backlog...")
                            bl = run_claude(f"Heute ist {today}.", system_prompt=BACKLOG_LIST_SYSTEM_PROMPT)
                            if "leer" in bl.lower():
                                send_message(TOKEN, CHAT_ID, f"{bl}\n\nKeine Backlog-Tasks verfügbar.", reply_markup=REPLY_KEYBOARD)
                            else:
                                pending_task_input[chat_id] = {"state": "backlog_select", "list": bl}
                                send_message(TOKEN, CHAT_ID, f"{bl}\n\nWelchen Task? (Nummer eingeben)", reply_markup=REPLY_KEYBOARD)
                        else:
                            send_message(TOKEN, CHAT_ID, "Bitte A oder B eingeben.", reply_markup=REPLY_KEYBOARD)
                        continue
                    elif isinstance(state, dict) and state.get("state") == "backlog_select":
                        del pending_task_input[chat_id]
                        try:
                            num = int(text.strip())
                            pending_task_input[chat_id] = {"state": "backlog_date", "num": num, "list": state["list"]}
                            send_message(TOKEN, CHAT_ID, f"Ausgewählt: #{num}\nWelches Datum? (z.B. heute, morgen, 2026-06-15)", reply_markup=REPLY_KEYBOARD)
                        except ValueError:
                            send_message(TOKEN, CHAT_ID, "Bitte eine Nummer eingeben.", reply_markup=REPLY_KEYBOARD)
                        continue
                    elif isinstance(state, dict) and state.get("state") == "backlog_date":
                        del pending_task_input[chat_id]
                        send_message(TOKEN, CHAT_ID, "⏳ Übertrage in Tagesorganizer...")
                        prompt = f"Heute ist {today}. Zieldatum: {text}.\nBacklog-Liste:\n{state['list']}\nNummer: {state['num']}"
                        response = run_claude(prompt, system_prompt=BACKLOG_PROMOTE_SYSTEM_PROMPT)
                        send_message(TOKEN, CHAT_ID, response, reply_markup=REPLY_KEYBOARD)
                        continue
                    elif state == "backlog_input":
                        del pending_task_input[chat_id]
                        send_message(TOKEN, CHAT_ID, "⏳ Denke nach...")
                        response = run_claude(f"Heute ist {today}. Backlog-Aufgabe: {text}", system_prompt=BACKLOG_SYSTEM_PROMPT)
                        send_message(TOKEN, CHAT_ID, response, reply_markup=REPLY_KEYBOARD)
                        continue
                    else:
                        del pending_task_input[chat_id]
                        send_message(TOKEN, CHAT_ID, "⏳ Denke nach...")
                        response = run_claude(f"Heute ist {today}. Aufgabe: {text}", system_prompt=TASK_SYSTEM_PROMPT)
                        send_message(TOKEN, CHAT_ID, response, reply_markup=REPLY_KEYBOARD)
                        continue

                send_message(TOKEN, CHAT_ID, "⏳ Denke nach...")

                project_cwd = None
                project_notion_name = None
                for slug, info in _get_projects().items():
                    if text.lower().startswith(f"{slug}:"):
                        project_cwd = info["path"] or None
                        project_notion_name = info["notion_name"]
                        text = text[len(slug) + 1:].strip()
                        break

                t = text.lower()
                response = None

                if project_notion_name and t == "tasks":
                    response = run_claude(f"Heute ist {today}. Projektname: {project_notion_name}", system_prompt=PROJEKT_TASKS_SYSTEM_PROMPT)
                elif project_notion_name and t.startswith("task:"):
                    task_text = text[5:].strip()
                    response = run_claude(f"Heute ist {today}. Projektname: {project_notion_name}. Aufgabe: {task_text}", system_prompt=PROJEKT_TASK_SYSTEM_PROMPT)
                elif t in ("moin", "morgen", "guten morgen"):
                    response = run_claude(f"Heute ist {today}.", system_prompt=MOIN_SYSTEM_PROMPT)
                elif t in ("abend", "feierabend", "guten abend"):
                    response = run_claude(f"Heute ist {today}.", system_prompt=ABEND_SYSTEM_PROMPT)
                elif t.startswith("task:"):
                    task_text = text[5:].strip()
                    if not task_text:
                        pending_task_input[chat_id] = "task_menu"
                        response = "Neuer Task oder aus Backlog?\nA) Neuer Task\nB) Aus Backlog auswählen"
                    else:
                        response = run_claude(f"Heute ist {today}. Aufgabe: {task_text}", system_prompt=TASK_SYSTEM_PROMPT, cwd=project_cwd)
                elif t == "woche":
                    response = run_claude(f"Heute ist {today}.", system_prompt=WOCHE_SYSTEM_PROMPT)
                elif t.startswith("fokus:"):
                    bereich = text[6:].strip().capitalize()
                    if bereich.lower() not in BEREICHE:
                        response = f"Unbekannter Bereich: {bereich}\nGültig: Arbeit, Privat, Lernen, Gesundheit"
                    else:
                        response = run_claude(f"Heute ist {today}. Bereich: {bereich}", system_prompt=FOKUS_SYSTEM_PROMPT)
                elif t.startswith("verschieben:"):
                    ziel = text[12:].strip()
                    response = (run_claude(f"Heute ist {today}. Zieldatum: {ziel}", system_prompt=VERSCHIEBEN_SYSTEM_PROMPT)
                                if ziel else "Nutzung: verschieben: morgen  oder  verschieben: 2026-06-15")
                elif t.startswith("lern:"):
                    response = run_claude(text[5:].strip(), system_prompt=LERN_SYSTEM_PROMPT)
                elif t.startswith("idee:"):
                    response = run_claude(text[5:].strip(), system_prompt=IDEE_SYSTEM_PROMPT)
                elif t.startswith("habit:"):
                    habit_text = text[6:].strip()
                    response = (run_claude(f"Heute ist {today}. Habit: {habit_text}", system_prompt=HABIT_SYSTEM_PROMPT)
                                if habit_text else "Nutzung: habit: <Habit>  z.B. habit: Sport täglich")
                elif t.startswith("termin:"):
                    termin_text = text[7:].strip()
                    response = (run_claude(f"Heute ist {today}. Termin: {termin_text}", system_prompt=TERMIN_SYSTEM_PROMPT)
                                if termin_text else "Nutzung: termin: <text>  z.B. termin: Arzttermin morgen um 14:00")
                elif t == "backlog":
                    response = run_claude(f"Heute ist {today}.", system_prompt=BACKLOG_LIST_SYSTEM_PROMPT)
                elif t.startswith("backlog:"):
                    backlog_text = text[8:].strip()
                    if not backlog_text:
                        pending_task_input[chat_id] = "backlog_input"
                        response = "Schreib mir: Name, Priorität (Hoch/Mittel/Niedrig), Bereich (Arbeit/Privat/Lernen/Gesundheit)\nz.B.: Stromtarif wechseln, Mittel, Privat"
                    else:
                        response = run_claude(f"Heute ist {today}. Backlog-Aufgabe: {backlog_text}", system_prompt=BACKLOG_SYSTEM_PROMPT)
                elif t.startswith("status:"):
                    status_text = text[7:].strip()
                    if not status_text:
                        response = "Nutzung: status: <Taskname> <Status>  z.B. status: Sport erledigt"
                    else:
                        response = run_claude(f"Heute ist {today}. Anfrage: {status_text}", system_prompt=STATUS_SYSTEM_PROMPT)
                        if any(w in status_text.lower() for w in ("erledigt", "fertig", "done")):
                            threading.Thread(target=_run_archive_once, daemon=True).start()
                elif t.startswith("erinnere") or t.startswith("erinnerung:"):
                    now_time = datetime.now().strftime("%H:%M")
                    raw = run_claude_parse(f"Heute ist {today}, aktuelle Uhrzeit: {now_time}. Nutzer schreibt: {text}", system_prompt=REMINDER_PARSE_SYSTEM_PROMPT)
                    try:
                        parsed = json.loads(raw)
                        _add_reminder(parsed["text"], parsed["due"])
                        due_dt = datetime.fromisoformat(parsed["due"])
                        response = f"⏰ Erinnerung gesetzt: {parsed['text']} — {due_dt.strftime('%d.%m.%Y um %H:%M')}"
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        print(f"[reminder parse error] raw={repr(raw)} exc={e}")
                        response = "❌ Konnte Erinnerung nicht parsen. Versuche: erinnere mich um 14:00 an Zahnarzt"
                elif t == "erinnerungen":
                    reminders = load_reminders()
                    pending = [r for r in reminders if r["status"] == "pending"]
                    if not pending:
                        response = "⏰ Keine offenen Erinnerungen."
                    else:
                        lines = [f"⏰ Offene Erinnerungen ({len(pending)}):"]
                        for r in sorted(pending, key=lambda x: x["due"]):
                            due_dt = datetime.fromisoformat(r["due"])
                            lines.append(f"· {due_dt.strftime('%d.%m. %H:%M')} — {r['text']}")
                        response = "\n".join(lines)
                elif t.startswith("suche:"):
                    query = text[6:].strip()
                    response = (run_claude(query, system_prompt=SUCHE_SYSTEM_PROMPT)
                                if query else "❓ Suchbegriff fehlt. z.B.: suche: Python")
                elif t.startswith("implement-plan:"):
                    body = text[15:].strip()
                    if not body:
                        response = "Nutzung: implement-plan: <slug> um HH:MM  oder  implement-plan: <slug> jetzt"
                    else:
                        slug_part, _, rest = body.partition(" ")
                        rest = rest.strip()
                        if rest.lower() == "jetzt":
                            plan_entry = next((p for p in load_plans() if p["slug"] == slug_part), None)
                            if not plan_entry:
                                response = f"❌ Kein Plan mit slug '{slug_part}' gefunden"
                            else:
                                send_message(TOKEN, CHAT_ID, f"🚀 Implementierung gestartet: {slug_part}", reply_markup=REPLY_KEYBOARD)
                                threading.Thread(target=_run_plan, args=(plan_entry["plan_path"], slug_part), daemon=True).start()
                                continue
                        elif rest.lower().startswith("um "):
                            scheduled_time = rest[3:].strip()
                            response = (_schedule_plan(slug_part, scheduled_time)
                                        if re.fullmatch(r"\d{2}:\d{2}", scheduled_time)
                                        else "❌ Ungültige Uhrzeit — bitte HH:MM angeben (z.B. 02:00)")
                        else:
                            response = "Nutzung: implement-plan: <slug> um HH:MM  oder  implement-plan: <slug> jetzt"
                elif t.startswith("abort-plan:"):
                    slug_part = text[11:].strip()
                    response = (_abort_plan(slug_part) if slug_part else "Nutzung: abort-plan: <slug>")
                elif t.startswith("impl-mode:"):
                    arg = text[10:].strip().lower()
                    s = load_settings()
                    if arg == "an":
                        until = (datetime.now() + timedelta(hours=4)).isoformat(timespec="seconds")
                        s["implementation_mode"] = True
                        s["implementation_mode_until"] = until
                        save_settings(s)
                        response = f"⚙️ Implementation Mode aktiv bis {until[11:16]}"
                    elif arg == "aus":
                        s["implementation_mode"] = False
                        s["implementation_mode_until"] = None
                        save_settings(s)
                        response = "⚙️ Implementation Mode deaktiviert"
                    else:
                        active = s.get("implementation_mode", False)
                        until = s.get("implementation_mode_until")
                        response = (f"⚙️ Implementation Mode: aktiv bis {until[11:16]}"
                                    if active and until else
                                    "⚙️ Implementation Mode: inaktiv\nNutzung: impl-mode: an  oder  impl-mode: aus")
                elif t == "/plans":
                    response = _format_plans()
                elif t == "hilfe":
                    response = HILFE_TEXT
                else:
                    resp, conversation_history = run_claude_with_history(
                        chat_id, text, conversation_history,
                        system_prompt=CHAT_SYSTEM_PROMPT,
                        cwd=project_cwd,
                    )
                    response = resp

                if response:
                    send_message(TOKEN, CHAT_ID, response, reply_markup=REPLY_KEYBOARD)

            time.sleep(0.3)
        except Exception as e:
            print(f"organizer bot error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()

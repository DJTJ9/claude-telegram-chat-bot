import os, re, subprocess, requests, tempfile, sys, json, uuid, threading, time
from datetime import date, datetime
from pathlib import Path
from groq import Groq

TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
MY_CHAT_ID = 8896609541
HABITS_DATA_SOURCE_ID = "6a4d7e7d-dcde-44e3-b7a0-c46330a6261c"
BACKLOG_DATA_SOURCE_ID = "0cb18d17-cf70-413d-b29d-adb4675db614"
ARCHIV_DATA_SOURCE_ID  = "abb5abd8-e320-4796-bbf6-941feb9007b9"
BASE = f"https://api.telegram.org/bot{TOKEN}"
WORK_DIR = os.environ.get("WORK_DIR", r"C:\Projekte\telegram-notion-bot")
HUB_DIR = os.environ.get("HUB_DIR", WORK_DIR)
REMINDERS_PATH = Path(WORK_DIR) / "reminders.json"
PLANS_PATH = Path(HUB_DIR) / "scheduled_plans.json"
TEACH_DIR = os.environ.get("TEACH_DIR", r"C:\Projekte\teach")
PAGES_BASE = "https://djtj9.github.io/teach-lessons"
COURSE_NAMES = {
    "cli-notion-agent":   "Kurs: CLI Notion Agent",
    "projekt-planung":    "Kurs: Projekt-Planung",
    "python-grundlagen":  "Kurs: Python Grundlagen",
}

PROJECTS = {
    "notion": {"path": WORK_DIR, "notion_name": "Notion-Bot"},
    "dart":   {"path": os.environ.get("DART_PROJECT_DIR", r"C:\Unity\Aktuelle Projekte\DartTrainingsApp"), "notion_name": "Dart-App"},
}

groq_client = Groq(api_key=GROQ_API_KEY)

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

HILFE_TEXT = """📋 Befehle:

🌅 Tagesplanung
  moin — Tasks + fällige Habits für heute
  abend — Tagesabschluss
  woche — Wochenrückblick
  fokus: <Bereich> — Arbeit / Privat / Lernen / Gesundheit

✅ Tasks & Habits
  task: — Neuen Task anlegen (interaktiv)
  task: <text> — Neuen Task direkt anlegen
  habit: <text> — Neuen Habit anlegen
    z.B. habit: Sport täglich  oder  habit: Laufen alle 2 Tage
  termin: <text> — Termin anlegen
    z.B. termin: Arzttermin morgen um 14:00
  backlog: <text> — Undatierte Aufgabe in Backlog speichern
  backlog — Alle offenen Backlog-Tasks anzeigen
  status: <name> <status> — Status ändern
    erledigt / in arbeit / offen
  verschieben: <datum> — Offene Tasks verschieben
    z.B. verschieben: morgen  oder  verschieben: 2026-06-15

📁 Projekte
  projekte — Alle Projekte anzeigen
  <name>: <frage> — Im Projektkontext fragen
  <name>: tasks — Projekt-Tasks anzeigen
  <name>: task: <text> — Projekt-Task anlegen

📚 Listen
  lern: <thema> — Lernthema speichern
  idee: <text> — Spielidee speichern
  suche: <text> — Alle DBs durchsuchen (Tasks, Backlog, Archiv, Lernthemen, Ideen)

⏰ Erinnerungen
  erinnere mich um 14:00 an Zahnarzt — Erinnerung setzen
  erinnere mich morgen um 9 an Meeting — mit Datum
  erinnerung: <text> — alternative Syntax
  erinnerungen — alle offenen Erinnerungen anzeigen

🛠 Sonstiges
  teach: <thema + warum> — Lernkurs erstellen oder planen
    z.B. teach: Python Grundlagen, weil ich Skripte automatisieren will
  restart — Bot neu starten

🧠 Brainstorming
  brainstorming: <idee> — Feature-Idee brainstormen (Spec → Plan → Scheduling)
  brainstorming: <idee>, basis: <slug> — Mit vorheriger Spec als Kontext
  /specs — Alle vorhandenen Specs anzeigen

🤖 Pläne
  /plans — geplante Implementierungen anzeigen
  implement-plan: <slug> um HH:MM — Implementierung planen
  implement-plan: <slug> jetzt — sofort implementieren
  abort-plan: <slug> — Implementierung entfernen

⚙️ Einstellungen
  /bot-notify an — Benachrichtigungen aktivieren
  /bot-notify aus — Benachrichtigungen deaktivieren"""

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

CHAT_SYSTEM_PROMPT = """Du bist ein hilfreicher persönlicher Assistent-Bot. Antworte kurz und direkt auf Fragen und Konversation.
Führe KEINE Aktionen aus. Nutze KEINE Tools. Erstelle KEINE Schedules oder Routines. Antworte NUR mit Text."""

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

ARCHIVE_TASK_SYSTEM_PROMPT = f"""Du bist ein Notion-Archiv-Assistent.
Archiviere den genannten Task sofort.
Suche im Tagesorganizer (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0) UND im Backlog (data_source_id: {BACKLOG_DATA_SOURCE_ID}) per fuzzy-Suche.
Falls gefunden und Status = Done oder Erledigt:
  Lege Eintrag im Task-Archiv an (data_source_id: {ARCHIV_DATA_SOURCE_ID}).
  Kopiere alle Properties. Setze "Archiviert am" = heutiges Datum.
  Archiviere Original (archived: true).
Antworte NUR: "✅ Archiviert: [Name]" oder "Übersprungen: [Name] (nicht Done)"
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
Zeile 1: "🔍 Suche: \"[Begriff]\""
Leerzeile
Je DB mit Treffern:
  "[Icon] [DB-Name] ([N])"
  Je Treffer: "  · [Status-Icon] [Name][— Datum falls gesetzt]"
  Leerzeile
Letzte Zeile: "🔍 [Gesamt] Treffer in [M] Datenbank(en)."
Falls keine Treffer: "🔍 Keine Ergebnisse für \"[Begriff]\"."

Status-Icons: Not started/Offen=⬜ In progress/In Bearbeitung=🔄 Done/Erledigt/Abgeschlossen=✅
DB-Icons: 📋 Tagesorganizer, 📦 Backlog, 🗂 Archiv, 📚 Lernthemen, 🎮 Spieleideen
Kein Markdown."""

def _update_index_html(lesson_path):
    parts = lesson_path.replace("\\", "/").split("/")
    if len(parts) < 3:
        return
    course_slug, filename = parts[0], parts[-1]
    m = re.match(r"lektion-(\d+)-", filename)
    if not m:
        return
    num = m.group(1)

    title = filename.replace(".html", "").replace("-", " ").title()
    html_file = os.path.join(TEACH_DIR, os.sep.join(lesson_path.replace("/", os.sep).split(os.sep)))
    try:
        with open(html_file, encoding="utf-8") as f:
            for line in f:
                tm = re.search(r"<title>(.*?)</title>", line)
                if tm:
                    title = re.sub(r"^Lektion \d+\s*[–\-]\s*", "", tm.group(1))
                    break
    except Exception:
        pass

    title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    href = lesson_path.replace("\\", "/")
    new_li = f'  <li><span class="num">{num}</span><a href="{href}">{title}</a></li>\n'

    section_header = COURSE_NAMES.get(course_slug)
    if not section_header:
        return

    index_path = os.path.join(TEACH_DIR, "index.html")
    with open(index_path, encoding="utf-8") as f:
        content = f.read()

    if href in content:
        return

    h2_tag = f"<h2>{section_header}</h2>"
    h2_pos = content.find(h2_tag)
    if h2_pos == -1:
        new_section = f'\n<h2>{section_header}</h2>\n<ul>\n{new_li}</ul>\n'
        content = content.replace("</body>", new_section + "</body>")
    else:
        ul_close = content.find("</ul>", h2_pos)
        if ul_close == -1:
            return
        content = content[:ul_close] + new_li + content[ul_close:]

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)


def publish_new_lessons(chat_id):
    try:
        result = subprocess.run(
            ["git", "-C", TEACH_DIR, "status", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8"
        )
        new_lessons = [
            line[3:].strip()
            for line in result.stdout.strip().splitlines()
            if len(line) > 3 and "/lessons/" in line and line[3:].strip().endswith(".html")
        ]
        if not new_lessons:
            return
        for p in new_lessons:
            _update_index_html(p)
        subprocess.run(["git", "-C", TEACH_DIR, "add", "."], capture_output=True)
        names = ", ".join(os.path.basename(p) for p in new_lessons)
        subprocess.run(
            ["git", "-C", TEACH_DIR, "commit", "-m", f"Add lesson: {names}"],
            capture_output=True, text=True, encoding="utf-8"
        )
        subprocess.run(["git", "-C", TEACH_DIR, "push"], capture_output=True)
        urls = "\n".join(f"{PAGES_BASE}/{p}" for p in new_lessons)
        send_message(chat_id, f"📚 Neue Lektion verfügbar:\n{urls}")
    except Exception as e:
        print(f"publish_new_lessons error: {e}")

def get_updates(offset=None, timeout=30):
    params = {"timeout": timeout, "offset": offset}
    r = requests.get(f"{BASE}/getUpdates", params=params, timeout=timeout + 5)
    return r.json().get("result", [])

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{BASE}/sendMessage", json=payload)

def run_claude(prompt, system_prompt=None, cwd=None, automated=False):
    cmd = ["claude", "--dangerously-skip-permissions"]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    cmd += ["-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"} if automated else None
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=1200, cwd=cwd or WORK_DIR, env=env)
        return (result.stdout or "").strip() or (result.stderr or "").strip() or "(keine Antwort)"
    except subprocess.TimeoutExpired:
        return "⏱ Timeout — Aufgabe hat länger als 20 Minuten gedauert. Bitte vereinfachen oder aufteilen."

def transcribe_voice(file_id):
    r = requests.get(f"{BASE}/getFile", params={"file_id": file_id})
    file_path = r.json()["result"]["file_path"]
    audio_data = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{file_path}").content
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_data)
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                prompt="task: erledigt: status: fokus: lern: idee: habit: verschieben: erinnere mich um:",
            )
        return transcription.text
    finally:
        os.unlink(tmp_path)

def normalize_voice(text: str) -> str:
    text = re.sub(r' Doppelpunkt\b', ':', text, flags=re.IGNORECASE)
    text = re.sub(r' Komma\b', ',', text, flags=re.IGNORECASE)
    text = re.sub(r' Punkt\b', '.', text, flags=re.IGNORECASE)
    return text

conversation_history = {}
pending_task_input = {}
_pending_new_project = {}
_active_permission_id = None
_active_question_id = None

def load_settings(_dir=WORK_DIR):
    p = Path(_dir) / "settings.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {"notifications_enabled": True}

def save_settings(s, _dir=WORK_DIR):
    (Path(_dir) / "settings.json").write_text(json.dumps(s, indent=2))

def run_claude_with_history(chat_id, text, system_prompt=None, cwd=None):
    history = conversation_history.get(chat_id, [])
    if history and not system_prompt:
        context = "\n".join(
            f"[{'USER' if m['role'] == 'user' else 'ASSISTANT'}]: {m['content']}"
            for m in history
        )
        prompt = f"Vorheriger Gesprächsverlauf:\n{context}\n\n[USER]: {text}"
    else:
        prompt = text
    response = run_claude(prompt, system_prompt=system_prompt, cwd=cwd)
    if not system_prompt:
        history = history + [
            {"role": "user", "content": text},
            {"role": "assistant", "content": response},
        ]
        conversation_history[chat_id] = history[-6:]
    return response

def run_claude_parse(prompt, system_prompt):
    """Parse-only Claude call: no MCP servers, returns raw text."""
    cfg = Path(WORK_DIR) / ".parse_mcp_empty.json"
    cfg.write_text('{"mcpServers": {}}', encoding="utf-8")
    try:
        cmd = ["claude", "--permission-mode", "plan",
               "--strict-mcp-config", "--mcp-config", str(cfg),
               "--system-prompt", system_prompt, "-p", prompt]
        env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=30, cwd=WORK_DIR, env=env)
        return (result.stdout or "").strip() or "{}"
    except subprocess.TimeoutExpired:
        return "{}"
    finally:
        cfg.unlink(missing_ok=True)

def load_reminders():
    if REMINDERS_PATH.exists():
        try:
            return json.loads(REMINDERS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []

def save_reminders(reminders):
    REMINDERS_PATH.write_text(json.dumps(reminders, indent=2, ensure_ascii=False), encoding="utf-8")

def _load_plans():
    if PLANS_PATH.exists():
        try:
            return json.loads(PLANS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []

def _save_plans(plans):
    PLANS_PATH.write_text(json.dumps(plans, indent=2, ensure_ascii=False), encoding="utf-8")

def _load_registry():
    p = Path(HUB_DIR) / "projects-registry.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []

def _save_registry(registry):
    p = Path(HUB_DIR) / "projects-registry.json"
    p.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")

def _create_project_entry(slug, name, path, chat_id):
    global _vision_active
    registry = _load_registry()
    if not any(p["slug"] == slug for p in registry):
        registry.append({"slug": slug, "name": name, "path": path or "", "repo": "", "description": ""})
        _save_registry(registry)
        subprocess.run(["git", "-C", HUB_DIR, "add", "projects-registry.json"], capture_output=True)
        subprocess.run(["git", "-C", HUB_DIR, "commit", "-m", f"chore: add project {slug}"], capture_output=True)
    topic_dir = Path(HUB_DIR) / "topics" / slug
    (topic_dir / "specs").mkdir(parents=True, exist_ok=True)
    (topic_dir / "plans").mkdir(parents=True, exist_ok=True)
    send_message(chat_id, f"✅ Projekt {name} angelegt. Starte Vision-Session...")
    _vision_active = True
    threading.Thread(target=_run_vision, args=(slug,), daemon=True).start()

def _parse_vision_features(slug):
    vision_path = Path(HUB_DIR) / "topics" / slug / "VISION.md"
    if not vision_path.exists():
        return []
    features = []
    for line in vision_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \[ \] (.+)$", line.strip())
        if m:
            features.append(m.group(1).strip())
    return features

def _set_plan_status(slug, status):
    plans = _load_plans()
    for p in plans:
        if p["slug"] == slug:
            p["status"] = status
            break
    _save_plans(plans)
    subprocess.run(["git", "-C", HUB_DIR, "add", "scheduled_plans.json"], capture_output=True)
    subprocess.run(["git", "-C", HUB_DIR, "commit", "-m", f"chore: plan {slug} -> {status}"], capture_output=True)

def _run_plan(plan_path, slug=None):
    if plan_path.startswith("topics/"):
        base_dir = HUB_DIR
        resolved = (Path(HUB_DIR) / plan_path).resolve()
        allowed = (Path(HUB_DIR) / "topics").resolve()
    else:
        base_dir = WORK_DIR
        resolved = (Path(WORK_DIR) / plan_path).resolve()
        allowed = (Path(WORK_DIR) / "docs" / "superpowers" / "plans").resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError:
        send_message(MY_CHAT_ID, f"❌ Ungültiger Plan-Pfad: {plan_path}")
        return
    prompt = (
        f"Follow the implementation plan exactly. "
        f"Plan file: {plan_path}\n"
        f"Read the plan file and implement every task step by step. Commit all changes when done."
    )
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            timeout=3600, cwd=base_dir)
    if result.returncode != 0:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                timeout=3600, cwd=base_dir)
    success = result.returncode == 0
    if slug:
        _set_plan_status(slug, "done" if success else "failed")
    label = slug or plan_path
    if success:
        send_message(MY_CHAT_ID, f"✅ Implementierung abgeschlossen: {label}")
    else:
        stderr_snippet = (result.stderr or "")[-500:]
        send_message(MY_CHAT_ID, f"❌ Implementierung fehlgeschlagen: {label}\n{stderr_snippet}")

_brainstorming_active = False
_vision_active = False

def _run_vision(slug):
    global _vision_active
    registry = _load_registry()
    proj = next((p for p in registry if p["slug"] == slug),
                {"slug": slug, "name": slug, "path": "", "repo": ""})
    hub_path = Path(HUB_DIR) / "topics" / slug
    hub_path.mkdir(parents=True, exist_ok=True)
    vision_path = hub_path / "VISION.md"
    telegram_ask_path = Path(WORK_DIR) / "scripts" / "telegram_ask.py"
    vision_note = (
        f"Read {vision_path} first — it exists. Append/refine sections, do NOT overwrite entirely."
        if vision_path.exists() else
        f"Create {vision_path} with this structure:\n"
        f"# {proj['name']} — Vision\n\n## Ziel\n\n"
        f"## Features (Backlog — priorisiert)\n- [ ] ...\n\n"
        f"## Architektur\n\n## Offene Fragen\n\n## Entscheidungen\n"
    )
    code_note = (
        f"Project code is at {proj['path']} — read its structure for architecture context."
        if proj.get("path") and Path(proj["path"]).exists() else ""
    )
    registry_json = json.dumps(registry, ensure_ascii=False)
    prompt = (
        f"You are running a project vision session for: {proj['name']} (slug: {slug}). "
        f"Project registry (all known projects for cross-reference): {registry_json}. "
        f"{code_note} "
        f"{vision_note} "
        f"Through dialogue, explore: project goal, required features (ordered by dependency), "
        f"architecture decisions, open questions. Ask one question at a time via: "
        f'python "{telegram_ask_path}" "your question here". '
        f"After session, write/update {vision_path}. "
        f"Then: git -C {HUB_DIR} add -A && "
        f"git -C {HUB_DIR} commit -m \"vision: update {slug}\" && "
        f"git -C {HUB_DIR} push"
    )
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                timeout=3600, cwd=str(hub_path), env=env)
        if result.returncode == 0:
            send_message(MY_CHAT_ID, f"🔭 Vision-Session für {proj['name']} abgeschlossen")
        else:
            send_message(MY_CHAT_ID, f"❌ Vision-Session fehlgeschlagen\n{(result.stderr or '')[-300:]}")
    except subprocess.TimeoutExpired:
        send_message(MY_CHAT_ID, "❌ Vision-Timeout (1h überschritten)")
    finally:
        _vision_active = False

def _run_teach(topic):
    safe_topic = topic[:500]
    prompt = (
        f"Invoke the /teach skill. "
        f"Topic and context from user: {safe_topic}. "
        f"Use telegram relay for questions if notifications_enabled."
    )
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        timeout=3600, cwd=str(Path(TEACH_DIR).parent), env=env
    )
    if result.returncode != 0:
        send_message(MY_CHAT_ID, f"❌ Teach-Session fehlgeschlagen\n{(result.stderr or '')[-300:]}")

def _run_brainstorming(topic, basis_slug=None, project_slug=None):
    global _brainstorming_active
    safe_topic = topic[:500]
    telegram_ask_path = Path(WORK_DIR) / "scripts" / "telegram_ask.py"
    restart_script = Path(WORK_DIR) / "scripts" / "restart_bot.sh"

    if project_slug:
        registry = _load_registry()
        proj = next((p for p in registry if p["slug"] == project_slug),
                    {"slug": project_slug, "name": project_slug, "path": "", "repo": ""})
        hub_path = Path(HUB_DIR) / "topics" / project_slug
        hub_path.mkdir(parents=True, exist_ok=True)
        vision_path = hub_path / "VISION.md"
        prior_specs = sorted((hub_path / "specs").glob("*.md")) if (hub_path / "specs").exists() else []
        registry_json = json.dumps(registry, ensure_ascii=False)
        proj_path = proj.get("path", "")
        vision_note = (f"Read {vision_path} for project context, architecture, and feature backlog."
                       if vision_path.exists() else "")
        specs_note = (f"Prior specs for cross-session context: {', '.join(str(s) for s in prior_specs[-3:])}"
                      if prior_specs else "")
        push_proj = (
            f"git -C {proj_path!r} add -A && "
            f"git -C {proj_path!r} commit -m \"feat: {safe_topic[:40]}\" && "
            f"git -C {proj_path!r} push"
            if proj_path else ""
        )
        post_impl = (
            f"After successful implementation:\n"
            f"1. In {vision_path}, change '- [ ] {safe_topic}' to "
            f"'- [x] {safe_topic} (implementiert {date.today().isoformat()})'.\n"
            f"2. git -C {HUB_DIR} add -A && git -C {HUB_DIR} commit -m "
            f"\"chore: {project_slug} after {safe_topic[:30]}\" && git -C {HUB_DIR} push\n"
            f"3. {push_proj}\n"
            f"4. If bot.py or scripts/ in {WORK_DIR} were modified: "
            f"send a Telegram message that the bot is restarting, "
            f"then run: bash {restart_script}"
        )
        prompt = (
            f"Invoke the superpowers:brainstorming skill. "
            f"Project: {proj['name']} (slug: {project_slug}). "
            f"Feature to brainstorm: {safe_topic}. "
            f"Project registry: {registry_json}. "
            f"{vision_note} {specs_note} "
            f"Save spec to {hub_path}/specs/YYYY-MM-DD-<topic>-design.md. "
            f"Save plan to {hub_path}/plans/YYYY-MM-DD-<topic>.md. "
            f'Use python "{telegram_ask_path}" for ALL questions and gate decisions. '
            f"{post_impl}"
        )
        exec_cwd = str(hub_path)
    else:
        vision_path = Path(WORK_DIR) / "VISION.md"
        vision_note = (
            f"Read {vision_path} first for existing project context and backlog."
            if vision_path.exists() else ""
        )
        basis_note = (
            f"Also read the spec file in docs/superpowers/specs/ whose name contains '{basis_slug}' "
            f"as prior session context before starting brainstorming."
            if basis_slug else ""
        )
        prompt = (
            f"Invoke the superpowers:brainstorming skill. "
            f"Feature idea from user: {safe_topic}. "
            f"{vision_note} {basis_note}"
            f'Use python "{telegram_ask_path}" for ALL questions and gate decisions '
            f"(notifications_enabled is true — do not output anything to terminal). "
            f"After the spec and plan are written and committed, update VISION.md in {WORK_DIR}: "
            f"add the new feature under Implementiert, move any collected-but-not-chosen ideas to Backlog, "
            f"record key decisions under Entscheidungen."
        )
        exec_cwd = WORK_DIR

    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            timeout=7200, cwd=exec_cwd, env=env
        )
        if result.returncode == 0:
            send_message(MY_CHAT_ID, "✅ Brainstorming abgeschlossen")
        else:
            send_message(MY_CHAT_ID, f"❌ Brainstorming fehlgeschlagen\n{(result.stderr or '')[-300:]}")
    except subprocess.TimeoutExpired:
        send_message(MY_CHAT_ID, "❌ Brainstorming-Timeout (2h überschritten)")
    finally:
        _brainstorming_active = False

def _plan_loop():
    while True:
        time.sleep(60)
        try:
            now = datetime.now().strftime("%H:%M")
            plans = _load_plans()
            for plan in plans:
                if plan["status"] == "pending" and plan.get("scheduled_time") == now:
                    _set_plan_status(plan["slug"], "running")
                    send_message(MY_CHAT_ID, f"🚀 Starte Implementierung: {plan['slug']}")
                    threading.Thread(
                        target=_run_plan,
                        args=(plan["plan_path"], plan["slug"]),
                        daemon=True
                    ).start()
        except Exception as e:
            print(f"plan loop error: {e}")

def _run_archive_once():
    try:
        run_claude(f"Heute ist {date.today().isoformat()}.", system_prompt=ARCHIVE_LOOP_SYSTEM_PROMPT, automated=True)
    except Exception as e:
        print(f"archive error: {e}")

def _archive_loop():
    while True:
        time.sleep(1800)
        _run_archive_once()

def _run_migration(_dir=WORK_DIR):
    s = load_settings(_dir)
    if s.get("archive_migration_done"):
        return
    _run_archive_once()
    s["archive_migration_done"] = True
    save_settings(s, _dir)

def _format_plans():
    plans = [plan for plan in _load_plans() if plan["status"] in ("pending", "running")]
    if not plans:
        return "Keine ausstehenden Pläne."
    scheduled = [plan for plan in plans if plan.get("scheduled_time")]
    waiting   = [plan for plan in plans if not plan.get("scheduled_time")]
    lines = ["📋 Geplante Implementierungen"]
    if scheduled:
        lines.append("\n⏰ Geplant:")
        for plan in scheduled:
            lines.append(f"• {plan['slug']} — {plan['scheduled_time']}")
    if waiting:
        lines.append("\n📌 Wartend (kein Termin):")
        for plan in waiting:
            lines.append(f"• {plan['slug']}")
    return "\n".join(lines)

def _schedule_plan(slug, scheduled_time):
    plans = _load_plans()
    for plan in plans:
        if plan["slug"] == slug:
            plan["scheduled_time"] = scheduled_time
            _save_plans(plans)
            subprocess.run(["git", "-C", HUB_DIR, "add", "scheduled_plans.json"], capture_output=True)
            subprocess.run(["git", "-C", HUB_DIR, "commit", "-m", f"chore: schedule plan {slug} at {scheduled_time}"], capture_output=True)
            return f"⏰ {slug} geplant für {scheduled_time}"
    return f"❌ Kein Plan mit slug '{slug}' gefunden"

def _abort_plan(slug):
    plans = _load_plans()
    for plan in plans:
        if plan["slug"] == slug:
            if plan["status"] == "running":
                return f"⚠️ Plan läuft gerade — abbrechen nicht möglich"
            plans = [p for p in plans if p["slug"] != slug]
            _save_plans(plans)
            subprocess.run(["git", "-C", HUB_DIR, "add", "scheduled_plans.json"], capture_output=True)
            subprocess.run(["git", "-C", HUB_DIR, "commit", "-m", f"chore: remove plan {slug}"], capture_output=True)
            return f"🗑 {slug} entfernt"
    return f"❌ Kein Plan mit slug '{slug}' gefunden"

def add_reminder(chat_id, text, due_iso):
    reminders = load_reminders()
    reminders.append({
        "id": str(uuid.uuid4())[:8],
        "text": text,
        "due": due_iso,
        "status": "pending",
        "chat_id": chat_id,
        "created": datetime.now().isoformat(timespec="seconds"),
    })
    save_reminders(reminders)
    subprocess.run(["git", "-C", WORK_DIR, "add", "reminders.json"], capture_output=True)
    subprocess.run(["git", "-C", WORK_DIR, "commit", "-m", f"chore: add reminder '{text[:40]}'"], capture_output=True)
    subprocess.run(["git", "-C", WORK_DIR, "push"], capture_output=True)

def check_and_send_reminders():
    try:
        subprocess.run(["git", "-C", WORK_DIR, "pull", "--rebase"], capture_output=True)
        reminders = load_reminders()
        now = datetime.now()
        changed = False
        for r in reminders:
            if r["status"] == "pending" and datetime.fromisoformat(r["due"]) <= now:
                send_message(r["chat_id"], f"⏰ Erinnerung: {r['text']}")
                r["status"] = "sent"
                changed = True
        if changed:
            save_reminders(reminders)
            subprocess.run(["git", "-C", WORK_DIR, "add", "reminders.json"], capture_output=True)
            subprocess.run(["git", "-C", WORK_DIR, "commit", "-m", "chore: mark reminders sent"], capture_output=True)
            subprocess.run(["git", "-C", WORK_DIR, "push"], capture_output=True)
    except Exception as e:
        print(f"reminder check error: {e}")

def _reminder_loop():
    while True:
        time.sleep(60)
        check_and_send_reminders()

if __name__ == "__main__":
    threading.Thread(target=_reminder_loop, daemon=True).start()
    threading.Thread(target=_plan_loop, daemon=True).start()
    threading.Thread(target=_archive_loop, daemon=True).start()
    threading.Thread(target=_run_migration, daemon=True).start()
    _stale = _load_plans()
    for _p in _stale:
        if _p["status"] == "running":
            _p["status"] = "pending"
    _save_plans(_stale)
    offset = int(os.environ.pop('BOT_START_OFFSET', '0')) or None
    today = date.today().isoformat()
    print(f"Bridge läuft ({today}). Strg+C zum Beenden.")

    while True:
        # Check for pending permission request from Claude Code hook
        pending_path = Path(WORK_DIR) / "pending_permission.json"
        if pending_path.exists():
            try:
                req = json.loads(pending_path.read_text())
                tool_input = req.get("input", {})
                tool_name = req.get("tool", "Unknown")
                if tool_name in ("Edit", "Write"):
                    file_path = tool_input.get("file_path", str(tool_input))[:300]
                    msg_text = f"✏️ Datei-Edit:\n{file_path}"
                else:
                    cmd = str(tool_input.get("command", tool_input))[:200]
                    msg_text = f"🔐 Permission needed:\nTool: {tool_name}\n$ {cmd}"
                inline_kb = {"inline_keyboard": [[
                    {"text": "Ja ✅", "callback_data": f"approve_{req['request_id']}"},
                    {"text": "Nein ❌", "callback_data": f"deny_{req['request_id']}"},
                ]]}
                send_message(MY_CHAT_ID, msg_text, reply_markup=inline_kb)
                _active_permission_id = req["request_id"]
                pending_path.unlink()
            except Exception as e:
                print(f"permission check error: {e}")

        pending_question_path = Path(WORK_DIR) / "pending_question.json"
        if pending_question_path.exists():
            try:
                req = json.loads(pending_question_path.read_text())
                question_text = req.get("question", "")
                send_message(MY_CHAT_ID, f"❓ Brainstorming-Frage:\n\n{question_text}")
                _active_question_id = req["request_id"]
                pending_question_path.unlink()
            except Exception as e:
                print(f"question check error: {e}")

        poll_timeout = 5 if (_active_permission_id or _active_question_id) else 10
        try:
            updates = get_updates(offset, timeout=poll_timeout)
        except requests.exceptions.ReadTimeout:
            continue
        except Exception as e:
            print(f"Polling-Fehler: {e}")
            continue
        for update in updates:
            offset = update["update_id"] + 1

            # Handle inline keyboard callbacks (permission approve/deny)
            cb = update.get("callback_query")
            if cb:
                if cb.get("from", {}).get("id") != MY_CHAT_ID:
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"], "text": "unauthorized"})
                    continue
                cb_data = cb.get("data", "")
                if cb_data.startswith("approve_") or cb_data.startswith("deny_"):
                    request_id = cb_data.split("_", 1)[1]
                    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id):
                        continue
                    resp_path = (Path(WORK_DIR) / f"permission_response_{request_id}.json").resolve()
                    if Path(WORK_DIR).resolve() not in resp_path.parents:
                        continue
                    approved = cb_data.startswith("approve_")
                    resp_path.write_text(json.dumps({"approved": approved, "request_id": request_id}))
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    action = "genehmigt ✅" if approved else "abgelehnt ❌"
                    send_message(MY_CHAT_ID, f"Permission {action}")
                    if _active_permission_id == request_id:
                        _active_permission_id = None
                elif cb_data == "new_proj":
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    _pending_new_project[MY_CHAT_ID] = {"state": "await_name"}
                    send_message(MY_CHAT_ID, "Name des neuen Projekts?")
                elif cb_data.startswith("proj_sel:"):
                    slug = cb_data[9:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    registry = _load_registry()
                    proj = next((p for p in registry if p["slug"] == slug), {"name": slug})
                    buttons = [[
                        {"text": "🔭 Vision", "callback_data": f"proj_vis:{slug}"},
                        {"text": "🧠 Brainstorming", "callback_data": f"proj_bs:{slug}"},
                        {"text": "📋 Pläne", "callback_data": f"proj_plans:{slug}"},
                    ]]
                    send_message(MY_CHAT_ID, f"{proj['name']} — was möchtest du tun?",
                                 reply_markup={"inline_keyboard": buttons})
                elif cb_data.startswith("proj_vis:"):
                    slug = cb_data[9:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    if _vision_active:
                        send_message(MY_CHAT_ID, "⚠️ Vision-Session läuft bereits.")
                    else:
                        registry = _load_registry()
                        proj = next((p for p in registry if p["slug"] == slug), {"name": slug})
                        _vision_active = True
                        send_message(MY_CHAT_ID,
                                     f"🔭 Vision-Session für {proj['name']} gestartet — Fragen kommen gleich")
                        threading.Thread(target=_run_vision, args=(slug,), daemon=True).start()
                elif cb_data.startswith("proj_bs:"):
                    slug = cb_data[8:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    features = _parse_vision_features(slug)
                    if not features:
                        buttons = [[{"text": "🔭 Vision starten", "callback_data": f"proj_vis:{slug}"}]]
                        send_message(MY_CHAT_ID, "Keine offenen Features. Starte zuerst eine Vision-Session.",
                                     reply_markup={"inline_keyboard": buttons})
                    else:
                        buttons = []
                        for i, feat in enumerate(features[:9]):
                            buttons.append([{"text": f"🎯 {feat[:38]}", "callback_data": f"feat_sel:{slug}:{i}"}])
                        buttons.append([{"text": "✏️ Neues Feature → erst Vision",
                                         "callback_data": f"proj_vis:{slug}"}])
                        registry = _load_registry()
                        proj = next((p for p in registry if p["slug"] == slug), {"name": slug})
                        send_message(MY_CHAT_ID, f"{proj['name']} — welches Feature brainstormen?",
                                     reply_markup={"inline_keyboard": buttons})
                elif cb_data.startswith("feat_sel:"):
                    parts = cb_data.split(":", 2)
                    if len(parts) == 3:
                        slug, idx_str = parts[1], parts[2]
                        requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                        try:
                            idx = int(idx_str)
                            features = _parse_vision_features(slug)
                            if 0 <= idx < len(features):
                                feature = features[idx]
                                if _brainstorming_active:
                                    send_message(MY_CHAT_ID, "⚠️ Brainstorming-Session läuft bereits.")
                                else:
                                    _brainstorming_active = True
                                    send_message(MY_CHAT_ID,
                                                 f"🧠 Brainstorming: {feature[:60]} — Fragen kommen gleich")
                                    threading.Thread(
                                        target=_run_brainstorming,
                                        args=(feature, None, slug),
                                        daemon=True
                                    ).start()
                            else:
                                send_message(MY_CHAT_ID, "❌ Feature nicht mehr verfügbar — projekte neu laden.")
                        except (ValueError, IndexError):
                            send_message(MY_CHAT_ID, "❌ Ungültige Feature-Auswahl.")
                elif cb_data.startswith("proj_plans:"):
                    slug = cb_data[11:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    plans_dir = Path(HUB_DIR) / "topics" / slug / "plans"
                    if not plans_dir.exists() or not list(plans_dir.glob("*.md")):
                        send_message(MY_CHAT_ID, f"Keine Pläne für {slug}.")
                    else:
                        files = sorted(plans_dir.glob("*.md"), reverse=True)
                        registry = _load_registry()
                        proj = next((p for p in registry if p["slug"] == slug), {"name": slug})
                        lines = [f"📋 Pläne für {proj['name']}:\n"]
                        for f in files[:10]:
                            stem = f.stem
                            parts = stem.split("-", 3)
                            if len(parts) == 4:
                                lines.append(f"• {parts[0]}-{parts[1]}-{parts[2]} · {parts[3]}")
                            else:
                                lines.append(f"• {stem}")
                        send_message(MY_CHAT_ID, "\n".join(lines))
                elif cb_data.startswith("npth_a:"):
                    proj_slug = cb_data[7:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    state = _pending_new_project.pop(MY_CHAT_ID, {})
                    proj_name = state.get("name", proj_slug)
                    _create_project_entry(proj_slug, proj_name, path=f"C:\\Projekte\\{proj_name}", chat_id=MY_CHAT_ID)
                elif cb_data.startswith("npth_b:"):
                    proj_slug = cb_data[7:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    state = _pending_new_project.get(MY_CHAT_ID, {})
                    _pending_new_project[MY_CHAT_ID] = {**state, "state": "await_custom_path", "slug": proj_slug}
                    send_message(MY_CHAT_ID, "Pfad eingeben (z.B. C:\\Projekte\\MeineApp):")
                elif cb_data.startswith("npth_c:"):
                    proj_slug = cb_data[7:]
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    state = _pending_new_project.pop(MY_CHAT_ID, {})
                    proj_name = state.get("name", proj_slug)
                    _create_project_entry(proj_slug, proj_name, path=None, chat_id=MY_CHAT_ID)
                continue  # Don't process callback_query as a message

            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")

            if chat_id != MY_CHAT_ID:
                continue

            voice = msg.get("voice")
            text = msg.get("text", "").strip()

            if voice:
                send_message(chat_id, "🎤 Transkribiere...")
                try:
                    text = normalize_voice(transcribe_voice(voice["file_id"])).strip()
                    if re.match(r'^\d{1,2}[.:]\d{2}\s*(uhr\s+)?an\s+', text, re.IGNORECASE):
                        text = f"erinnere mich um {text}"
                    send_message(chat_id, f"🎤 Erkannt: {text}")
                except Exception as e:
                    send_message(chat_id, f"❌ Transkription fehlgeschlagen: {e}")
                    continue
            elif not text:
                continue

            if _active_question_id:
                resp_path = (Path(WORK_DIR) / f"question_response_{_active_question_id}.json").resolve()
                if Path(WORK_DIR).resolve() not in resp_path.parents:
                    continue
                resp_path.write_text(json.dumps({"answer": text}))
                _active_question_id = None
                send_message(chat_id, f"💬 Antwort gesendet: {text}")
                continue

            if text.lower() == "/plans":
                send_message(chat_id, _format_plans(), reply_markup=REPLY_KEYBOARD)
                continue

            if text.lower() == "/specs":
                lines = ["📋 Specs:\n"]
                hub_topics = Path(HUB_DIR) / "topics"
                if hub_topics.exists():
                    for slug_dir in sorted(hub_topics.iterdir()):
                        if not slug_dir.is_dir():
                            continue
                        specs_subdir = slug_dir / "specs"
                        if not specs_subdir.exists():
                            continue
                        for f in sorted(specs_subdir.glob("*.md")):
                            stem = f.stem
                            parts = stem.split("-", 3)
                            if len(parts) == 4:
                                date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
                                slug_label = parts[3].removesuffix("-design")
                                lines.append(f"{date_str} · [{slug_dir.name}] {slug_label}")
                            else:
                                lines.append(f"[{slug_dir.name}] {stem}")
                local_specs = Path(WORK_DIR) / "docs" / "superpowers" / "specs"
                if local_specs.exists():
                    for f in sorted(local_specs.glob("*.md")):
                        stem = f.stem
                        parts = stem.split("-", 3)
                        if len(parts) == 4:
                            date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
                            slug_label = parts[3].removesuffix("-design")
                            lines.append(f"{date_str} · [bot] {slug_label}")
                        else:
                            lines.append(f"[bot] {stem}")
                if len(lines) == 1:
                    response = "Keine Specs vorhanden."
                else:
                    lines.append("\nNutzung: brainstorming: <idee>, basis: <slug>")
                    response = "\n".join(lines)
                send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                continue

            if text.lower().startswith("/bot-notify"):
                arg = text[11:].strip().lower()
                s = load_settings()
                if arg == "an":
                    s["notifications_enabled"] = True
                    save_settings(s)
                    response = "🔔 Benachrichtigungen aktiviert"
                elif arg == "aus":
                    s["notifications_enabled"] = False
                    save_settings(s)
                    response = "🔕 Benachrichtigungen deaktiviert"
                else:
                    state = "aktiviert 🔔" if s.get("notifications_enabled", True) else "deaktiviert 🔕"
                    response = f"Benachrichtigungen: {state}\nNutzung: /bot-notify an  oder  /bot-notify aus"
                send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                continue

            if text.lower() == "restart":
                send_message(chat_id, "🔄 Bot wird neu gestartet...")
                os.environ['BOT_START_OFFSET'] = str(offset)
                os.execv(sys.executable, [sys.executable] + sys.argv[:1])
                continue

            if text.lower() in ("projekte", "/projekte"):
                registry = _load_registry()
                buttons = [[{"text": "➕ Neues Projekt", "callback_data": "new_proj"}]]
                for proj in registry:
                    buttons.append([{"text": f"🎯 {proj['name']}", "callback_data": f"proj_sel:{proj['slug']}"}])
                send_message(chat_id, "Deine Projekte:", reply_markup={"inline_keyboard": buttons})
                continue

            if chat_id in _pending_new_project:
                state_data = _pending_new_project[chat_id]
                state = state_data["state"]
                _is_nav = text.lower() in ("projekte", "hilfe", "moin", "abend", "/plans", "/specs")
                if _is_nav:
                    del _pending_new_project[chat_id]
                elif state == "await_name":
                    proj_name = text.strip()[:40]
                    proj_slug = re.sub(r"[^a-z0-9]+", "-", proj_name.lower()).strip("-")[:30]
                    if not proj_slug:
                        send_message(chat_id, "❌ Ungültiger Name. Nochmal versuchen.")
                    else:
                        default_path = f"C:\\Projekte\\{proj_name}"
                        _pending_new_project[chat_id] = {"state": "await_path", "slug": proj_slug, "name": proj_name}
                        buttons = [
                            [{"text": f"A) {default_path}", "callback_data": f"npth_a:{proj_slug}"}],
                            [{"text": "B) Anderen Pfad eingeben", "callback_data": f"npth_b:{proj_slug}"}],
                            [{"text": "C) Noch kein Pfad (nur Planung)", "callback_data": f"npth_c:{proj_slug}"}],
                        ]
                        send_message(chat_id, f"Wo soll {proj_name} angelegt werden?",
                                     reply_markup={"inline_keyboard": buttons})
                elif state == "await_custom_path":
                    custom_path = text.strip()
                    proj_slug = state_data["slug"]
                    proj_name = state_data["name"]
                    del _pending_new_project[chat_id]
                    _create_project_entry(proj_slug, proj_name, path=custom_path, chat_id=chat_id)
                continue

            if chat_id in pending_task_input:
                state = pending_task_input[chat_id]
                _is_command = (text.lower() in ("restart", "projekte", "moin", "abend", "woche", "hilfe", "erinnerungen", "/plans", "backlog", "/specs")
                               or any(text.lower().startswith(p) for p in
                                      ("task:", "status:", "fokus:", "verschieben:", "lern:",
                                       "idee:", "habit:", "termin:", "projekt:", "teach:", "erinnere", "erinnerung:",
                                       "implement-plan:", "abort-plan:", "backlog:", "suche:", "brainstorming:")))
                if _is_command:
                    del pending_task_input[chat_id]
                elif state == "task_menu":
                    del pending_task_input[chat_id]
                    choice = text.strip().upper()
                    if choice in ("A", "1"):
                        pending_task_input[chat_id] = "task_input"
                        send_message(chat_id, "Schreib mir: Name, Priorität (Hoch/Mittel/Niedrig), Bereich (Arbeit/Privat/Lernen/Gesundheit)\nz.B.: Arzttermin, Hoch, Gesundheit")
                    elif choice in ("B", "2"):
                        send_message(chat_id, "⏳ Lade Backlog...")
                        backlog_response = run_claude(f"Heute ist {today}.", system_prompt=BACKLOG_LIST_SYSTEM_PROMPT)
                        if "leer" in backlog_response.lower():
                            send_message(chat_id, f"{backlog_response}\n\nKeine Backlog-Tasks verfügbar.")
                        else:
                            pending_task_input[chat_id] = {"state": "backlog_select", "list": backlog_response}
                            send_message(chat_id, f"{backlog_response}\n\nWelchen Task? (Nummer eingeben)")
                    else:
                        send_message(chat_id, "Bitte A oder B eingeben.")
                    continue
                elif isinstance(state, dict) and state.get("state") == "backlog_select":
                    del pending_task_input[chat_id]
                    try:
                        num = int(text.strip())
                        pending_task_input[chat_id] = {"state": "backlog_date", "num": num, "list": state["list"]}
                        send_message(chat_id, f"Ausgewählt: #{num}\nWelches Datum? (z.B. heute, morgen, 2026-06-15)")
                    except ValueError:
                        send_message(chat_id, "Bitte eine Nummer eingeben.")
                    continue
                elif isinstance(state, dict) and state.get("state") == "backlog_date":
                    del pending_task_input[chat_id]
                    send_message(chat_id, "⏳ Übertrage in Tagesorganizer...")
                    prompt = f"Heute ist {today}. Zieldatum: {text}.\nBacklog-Liste:\n{state['list']}\nNummer: {state['num']}"
                    response = run_claude(prompt, system_prompt=BACKLOG_PROMOTE_SYSTEM_PROMPT)
                    send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                    continue
                elif state == "backlog_input":
                    del pending_task_input[chat_id]
                    send_message(chat_id, "⏳ Denke nach...")
                    prompt = f"Heute ist {today}. Backlog-Aufgabe: {text}"
                    response = run_claude(prompt, system_prompt=BACKLOG_SYSTEM_PROMPT)
                    send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                    continue
                else:
                    del pending_task_input[chat_id]
                    send_message(chat_id, "⏳ Denke nach...")
                    prompt = f"Heute ist {today}. Aufgabe: {text}"
                    response = run_claude(prompt, system_prompt=TASK_SYSTEM_PROMPT)
                    send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                    publish_new_lessons(chat_id)
                    print(f"[task-dialog] → {response[:60]}")
                    continue

            send_message(chat_id, "⏳ Denke nach...")

            project_cwd = None
            project_notion_name = None
            for name, info in PROJECTS.items():
                prefix = f"{name}:"
                if text.lower().startswith(prefix):
                    project_cwd = info["path"]
                    project_notion_name = info["notion_name"]
                    text = text[len(prefix):].strip()
                    break

            if project_notion_name and text.lower() == "tasks":
                prompt = f"Heute ist {today}. Projektname: {project_notion_name}"
                response = run_claude(prompt, system_prompt=PROJEKT_TASKS_SYSTEM_PROMPT)
            elif text.lower() in ("moin", "morgen", "guten morgen"):
                response = run_claude(f"Heute ist {today}.", system_prompt=MOIN_SYSTEM_PROMPT)
            elif text.lower() in ("abend", "feierabend", "guten abend"):
                response = run_claude(f"Heute ist {today}.", system_prompt=ABEND_SYSTEM_PROMPT)
            elif project_notion_name and text.lower().startswith("task:"):
                task_text = text[5:].strip()
                prompt = f"Heute ist {today}. Projektname: {project_notion_name}. Aufgabe: {task_text}"
                response = run_claude(prompt, system_prompt=PROJEKT_TASK_SYSTEM_PROMPT)
            elif text.lower().startswith("task:"):
                task_text = text[5:].strip()
                if not task_text:
                    pending_task_input[chat_id] = "task_menu"
                    response = "Neuer Task oder aus Backlog?\nA) Neuer Task\nB) Aus Backlog auswählen"
                else:
                    prompt = f"Heute ist {today}. Aufgabe: {task_text}"
                    response = run_claude(prompt, system_prompt=TASK_SYSTEM_PROMPT, cwd=project_cwd)
            elif text.lower() == "woche":
                response = run_claude(f"Heute ist {today}.", system_prompt=WOCHE_SYSTEM_PROMPT)
            elif text.lower().startswith("fokus:"):
                bereich_raw = text[6:].strip()
                bereich = bereich_raw.capitalize()
                if bereich.lower() not in BEREICHE:
                    response = f"Unbekannter Bereich: {bereich_raw}\nGültig: Arbeit, Privat, Lernen, Gesundheit"
                else:
                    response = run_claude(f"Heute ist {today}. Bereich: {bereich}", system_prompt=FOKUS_SYSTEM_PROMPT)
            elif text.lower().startswith("verschieben:"):
                ziel_datum = text[12:].strip()
                if not ziel_datum:
                    response = "Nutzung: verschieben: morgen  oder  verschieben: 2026-06-15"
                else:
                    response = run_claude(f"Heute ist {today}. Zieldatum: {ziel_datum}", system_prompt=VERSCHIEBEN_SYSTEM_PROMPT)
            elif text.lower().startswith("projekt:"):
                projektname = text[8:].strip()
                if not projektname:
                    response = "Nutzung: projekt: <Projektname>  z.B. projekt: Dart-App"
                else:
                    prompt = f"Heute ist {today}. Projektname: {projektname}"
                    response = run_claude(prompt, system_prompt=PROJEKT_TASKS_SYSTEM_PROMPT)
            elif text.lower().startswith("lern:"):
                lern_text = text[5:].strip()
                response = run_claude(lern_text, system_prompt=LERN_SYSTEM_PROMPT)
            elif text.lower().startswith("idee:"):
                idee_text = text[5:].strip()
                response = run_claude(idee_text, system_prompt=IDEE_SYSTEM_PROMPT)
            elif text.lower().startswith("habit:"):
                habit_text = text[6:].strip()
                if not habit_text:
                    response = "Nutzung: habit: <Habit>  z.B. habit: Sport täglich  oder  habit: Laufen alle 2 Tage"
                else:
                    prompt = f"Heute ist {today}. Habit: {habit_text}"
                    response = run_claude(prompt, system_prompt=HABIT_SYSTEM_PROMPT)
            elif text.lower().startswith("termin:"):
                termin_text = text[7:].strip()
                if not termin_text:
                    response = "Nutzung: termin: <text>  z.B. termin: Arzttermin morgen um 14:00"
                else:
                    prompt = f"Heute ist {today}. Termin: {termin_text}"
                    response = run_claude(prompt, system_prompt=TERMIN_SYSTEM_PROMPT)
            elif text.lower().startswith("implement-plan:"):
                body = text[15:].strip()
                if not body:
                    response = "Nutzung: implement-plan: <slug> um HH:MM  oder  implement-plan: <slug> jetzt"
                else:
                    slug_part, _, rest = body.partition(" ")
                    rest = rest.strip()
                    if rest.lower() == "jetzt":
                        plan_entry = next((p for p in _load_plans() if p["slug"] == slug_part), None)
                        if not plan_entry:
                            response = f"❌ Kein Plan mit slug '{slug_part}' gefunden"
                            send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                        else:
                            send_message(chat_id, f"🚀 Implementierung gestartet: {slug_part}")
                            threading.Thread(
                                target=_run_plan,
                                args=(plan_entry["plan_path"], slug_part),
                                daemon=True
                            ).start()
                        continue
                    elif rest.lower().startswith("um "):
                        scheduled_time = rest[3:].strip()
                        if not re.fullmatch(r"\d{2}:\d{2}", scheduled_time):
                            response = "❌ Ungültige Uhrzeit — bitte HH:MM angeben (z.B. 02:00)"
                        else:
                            response = _schedule_plan(slug_part, scheduled_time)
                    else:
                        response = "Nutzung: implement-plan: <slug> um HH:MM  oder  implement-plan: <slug> jetzt"
                send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                continue
            elif text.lower().startswith("abort-plan:"):
                slug_part = text[11:].strip()
                if not slug_part:
                    response = "Nutzung: abort-plan: <slug>"
                else:
                    response = _abort_plan(slug_part)
                send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
                continue
            elif text.lower() == "hilfe":
                response = HILFE_TEXT
            elif text.lower() == "backlog":
                response = run_claude(f"Heute ist {today}.", system_prompt=BACKLOG_LIST_SYSTEM_PROMPT)
            elif text.lower().startswith("backlog:"):
                backlog_text = text[8:].strip()
                if not backlog_text:
                    pending_task_input[chat_id] = "backlog_input"
                    response = "Schreib mir: Name, Priorität (Hoch/Mittel/Niedrig), Bereich (Arbeit/Privat/Lernen/Gesundheit)\nz.B.: Stromtarif wechseln, Mittel, Privat"
                else:
                    prompt = f"Heute ist {today}. Backlog-Aufgabe: {backlog_text}"
                    response = run_claude(prompt, system_prompt=BACKLOG_SYSTEM_PROMPT)
            elif text.lower().startswith("status:"):
                status_text = text[7:].strip()
                if not status_text:
                    response = "Nutzung: status: <Taskname> <Status>  z.B. status: Sport erledigt"
                else:
                    prompt = f"Heute ist {today}. Anfrage: {status_text}"
                    response = run_claude(prompt, system_prompt=STATUS_SYSTEM_PROMPT)
                    if any(w in status_text.lower() for w in ("erledigt", "fertig", "done")):
                        threading.Thread(target=_run_archive_once, daemon=True).start()
            elif text.lower().startswith("erinnere") or text.lower().startswith("erinnerung:"):
                now_time = datetime.now().strftime("%H:%M")
                parse_prompt = f"Heute ist {today}, aktuelle Uhrzeit: {now_time}. Nutzer schreibt: {text}"
                raw = run_claude_parse(parse_prompt, system_prompt=REMINDER_PARSE_SYSTEM_PROMPT)
                try:
                    parsed = json.loads(raw)
                    add_reminder(chat_id, parsed["text"], parsed["due"])
                    due_dt = datetime.fromisoformat(parsed["due"])
                    response = f"⏰ Erinnerung gesetzt: {parsed['text']} — {due_dt.strftime('%d.%m.%Y um %H:%M')}"
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    print(f"[reminder parse error] raw={repr(raw)} exc={e}")
                    response = f"❌ Konnte Erinnerung nicht parsen. Versuche: erinnere mich um 14:00 an Zahnarzt"
            elif text.lower() == "erinnerungen":
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
            elif text.lower().startswith("suche:"):
                query = text[6:].strip()
                if not query:
                    response = "❓ Suchbegriff fehlt. z.B.: suche: Python"
                else:
                    response = run_claude(query, system_prompt=SUCHE_SYSTEM_PROMPT)
            elif text.lower().startswith("vision:"):
                slug = text[7:].strip()
                if not slug:
                    response = "Nutzung: vision: <slug>  z.B. vision: dart-app\nProjekte anzeigen: projekte"
                elif _vision_active:
                    response = "⚠️ Vision-Session läuft bereits. Warten bis abgeschlossen."
                else:
                    registry = _load_registry()
                    proj = next(
                        (p for p in registry
                         if p["slug"] == slug or p["name"].lower() == slug.lower()),
                        None
                    )
                    if not proj:
                        response = (f"❌ Projekt '{slug}' nicht gefunden. "
                                    f"Erst anlegen: projekte → ➕ Neues Projekt")
                    else:
                        _vision_active = True
                        send_message(chat_id,
                                     f"🔭 Vision-Session für {proj['name']} gestartet — Fragen kommen gleich")
                        threading.Thread(target=_run_vision, args=(proj["slug"],), daemon=True).start()
                        continue
            elif text.lower().startswith("brainstorming:"):
                topic = text[14:].strip()
                if not topic:
                    response = (
                        "Nutzung: brainstorming: <idee>\n"
                        "oder:    brainstorming: <idee>, basis: <slug>\n"
                        "Specs anzeigen: /specs"
                    )
                elif _brainstorming_active:
                    response = "⚠️ Brainstorming-Session läuft bereits. Bitte warten bis sie abgeschlossen ist."
                else:
                    basis_slug = None
                    lower_topic = topic.lower()
                    if ", basis:" in lower_topic:
                        idx = lower_topic.index(", basis:")
                        basis_slug = topic[idx + 8:].strip()
                        topic = topic[:idx].strip()
                    _brainstorming_active = True
                    send_message(chat_id, "🧠 Brainstorming gestartet — Fragen kommen gleich über den Chat")
                    threading.Thread(
                        target=_run_brainstorming, args=(topic, basis_slug), daemon=True
                    ).start()
                    continue
            elif text.lower().startswith("/teach") or text.lower().startswith("teach:"):
                topic = text.split(":", 1)[1].strip() if ":" in text else text[6:].strip()
                if not topic:
                    send_message(chat_id, "Nutzung: teach: <thema + warum>\nz.B. teach: Python Grundlagen, weil ich Skripte automatisieren will", reply_markup=REPLY_KEYBOARD)
                    continue
                send_message(chat_id, "📚 Teach-Session gestartet — Fragen kommen gleich über den Chat")
                threading.Thread(target=_run_teach, args=(topic,), daemon=True).start()
                continue
            else:
                response = run_claude_with_history(chat_id, text, system_prompt=CHAT_SYSTEM_PROMPT, cwd=project_cwd)

            send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
            publish_new_lessons(chat_id)
            print(f"[{text[:40]}] → {response[:60]}")

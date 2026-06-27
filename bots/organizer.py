import os, sys, json, re, uuid, subprocess, threading, time
import random
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
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

from core.telegram import get_updates, send_message, build_inline_keyboard, answer_callback_query, transcribe_voice, normalize_voice, edit_message, set_my_commands
from core.settings import load_settings, save_settings
from core.claude import run_claude, run_claude_parse
from core.state import load_reminders, save_reminders, load_plans, save_plans, load_registry
from core import notion_direct

TOKEN = os.environ["TOKEN_ORGANIZER"]
CHAT_ID = int(os.environ.get("CHAT_ID", "8896609541"))
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
HUB_DIR = Path(os.environ.get("HUB_DIR", str(WORK_DIR)))
PORT = int(os.environ.get("PORT", "8002"))

TAGESORGANIZER_ID      = "38b4bba29c5581a7bd94cef1b0cc6c58"
HABITS_DATA_SOURCE_ID  = "6a4d7e7d-dcde-44e3-b7a0-c46330a6261c"
BACKLOG_DATA_SOURCE_ID = "0cb18d17-cf70-413d-b29d-adb4675db614"
ARCHIV_DATA_SOURCE_ID  = "38b4bba29c558102b9aecb790594aff6"
SPORT_CHALLENGES_DB_ID = "38b4bba29c5581c88f49c67bb85f78c0"
IDEENSAMMLUNG_DB_ID    = "38b4bba29c55814f836ed9a05d3ec9a5"
PROJEKTE_DB_ID         = "38b4bba29c5581e8868efe4e2fad255a"
ARBEIT_DB_ID = ""  # Fill in after creating Arbeitsprojekte DB in Notion
BEREICHE = {"arbeit", "privat", "lernen", "gesundheit"}

REPLY_KEYBOARD = {
    "keyboard": [
        ["📋 Task", "📅 Termin", "💡 Ideen"],
        ["📚 Lern", "🌅 Morgen", "🌙 Abend"],
        ["📆 Woche", "📥 Backlog", "🗂️ Projekte"],
        ["🔋 Energie", "🔄 Zyklen"],
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False,
    "persistent": True,
}



WOCHENSICHT_SYSTEM_PROMPT = """Du bist ein Notion-Wochenvorschau-Assistent.
Lies den Tagesorganizer (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
Finde alle Tasks mit Datum >= heute UND Datum <= heute+7, Status != Done.
Gruppiere nach Datum, sortiere Tage chronologisch.
Format:
Zeile 1: "━━ Woche DD.MM – DD.MM ━━"
Leerzeile
Pro Tag (Mo bis So):
  "Wochentag DD.MM"
  Je Task: "  • [Name]  [Prio-Icon]"
  Falls kein Task: "  —  frei"
  Leerzeile
Prio-Icons: Hoch=🔴 Mittel=🟡 Niedrig=🟢
Kein Markdown."""


ZYKLEN_INSTANZ_SYSTEM_PROMPT = """Du bist ein Zyklen-Assistent.
Lies den Tagesorganizer (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
Schritt 1: Finde alle Eintraege mit Zyklus-Property != null/leer. Das sind Vorlagen.
Schritt 2: Fuer jede Vorlage: existiert heute ({today}) schon eine Instanz?
  (Eintrag gleicher Name, Datum = {today}, Status != Done, ohne Zyklus-Property)
Schritt 3: Falls keine Instanz: erstelle neuen Eintrag mit Name = Vorlage-Name,
  Datum = {today}, Status = Not started, Prioritaet = Vorlage-Prioritaet.
  Zyklus-Property NICHT auf neuen Eintrag setzen.
Antworte NUR mit: "{n} Zyklen instanziiert: Name1, Name2" oder "Keine faelligen Zyklen." """

ZYKLEN_LIST_SYSTEM_PROMPT = """Du bist ein Zyklen-Assistent.
Lies den Tagesorganizer (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
Finde alle Eintraege mit Zyklus-Property != null/leer.
Antworte NUR mit JSON:
{"zyklen": [{"id": "<page_id_32_zeichen>", "name": "<Name>", "zyklus": "<Zyklus-Wert>"}]}
Falls keine: {"zyklen": []}"""

ZYKLEN_NEU_SYSTEM_PROMPT = """Du bist ein Zyklen-Assistent.
Lege neuen Eintrag im Tagesorganizer an (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
Name: {name}. Zyklus: {zyklus}. Kein Datum, Status: Not started.
Antworte NUR mit: Zyklischer Task angelegt: {name} ({zyklus})"""

ZYKLEN_DELETE_SYSTEM_PROMPT = """Du bist ein Zyklen-Assistent.
Archiviere den Notion-Eintrag mit page_id {page_id} aus dem Tagesorganizer
(data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
Antworte NUR mit: Zyklischer Task geloescht."""

ABEND_SYSTEM_PROMPT = """Du bist ein Notion-Abend-Assistent.
Lies den Tagesorganizer (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
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
Lies den Tagesorganizer (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
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


TERMIN_SYSTEM_PROMPT = """Du bist ein Notion-Termin-Assistent.
Lege den Termin im Tagesorganizer an (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
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

BACKLOG_JSON_SYSTEM_PROMPT = f"""Du bist ein Notion-Backlog-Assistent.
Lies den Backlog (data_source_id: {BACKLOG_DATA_SOURCE_ID}).
Zeige alle Tasks mit Status = Offen, sortiert nach Priorität (Hoch zuerst).
Antworte AUSSCHLIESSLICH mit diesem JSON (kein Markdown, keine Erklärung):
{{"items": [{{"name": "...", "prio": "Hoch|Mittel|Niedrig", "id": "<page_id_32_zeichen_hex>"}}]}}
Falls keine offenen Tasks: {{"items": []}}"""

BACKLOG_PROMOTE_SYSTEM_PROMPT = f"""Du bist ein Notion-Backlog-Assistent.
Schritt 1: Finde den Task mit der genannten Nummer aus der Backlog-Liste (fuzzy-Suche auf den Namen).
Schritt 2: Lege neuen Task im Tagesorganizer an (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
  Übernehme: Name, Priorität, Bereich, Notiz.
  Setze Datum = angegebenes Zieldatum (ISO 8601). "morgen" = heute + 1 Tag.
  Status = Not started.
Schritt 3: Setze den Backlog-Task auf Status = Erledigt (data_source_id: {BACKLOG_DATA_SOURCE_ID}).
Antworte NUR mit: "✅ [Name] → Tagesorganizer für [DD.MM.YYYY]"
Kein Markdown."""

ARCHIVE_LOOP_SYSTEM_PROMPT = f"""Du bist ein Notion-Archiv-Assistent.
Archiviere alle erledigten Tasks aus dem Tagesorganizer und dem Backlog ins Task-Archiv.

Schritt 1 — Tagesorganizer (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58):
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


MOIN_JSON_SYSTEM_PROMPT = f"""Du bist ein Notion-Morgen-Assistent.
Lies den Tagesorganizer (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
Finde alle Tasks mit Datum = heute ODER ohne Datum, Status Not started oder In progress.

Gruppen:
- appointments: Tasks mit Datum als datetime (z.B. 2026-06-22T14:00) — sortiert nach Uhrzeit
- tasks: Tasks mit nur Datum (date-only) oder ohne Datum — sortiert nach Prio (Hoch zuerst)

Lies dann Habits-Datenbank (data_source_id: {HABITS_DATA_SOURCE_ID}).
- habits: Habits mit Nächste Fälligkeit <= heute UND Status = Aktiv — sortiert alphabetisch

Lies dann Arbeitsprojekte-Datenbank (data_source_id: {ARBEIT_DB_ID}).
- proj_tasks: Features mit Typ = Feature, Datum = heute, Status = Offen oder In Arbeit

Antworte AUSSCHLIESSLICH mit diesem JSON (kein Markdown, keine Erklärung):
{{
  "date": "YYYY-MM-DD",
  "appointments": [{{"name": "...", "time": "HH:MM", "id": "<page_id_32_zeichen>"}}],
  "tasks": [{{"name": "...", "prio": "Hoch|Mittel|Niedrig", "projekt": "...|null", "id": "<page_id_32_zeichen>"}}],
  "habits": [{{"name": "...", "interval": <int_tage>, "id": "<page_id_32_zeichen>"}}],
  "proj_tasks": [{{"name": "...", "projekt": "...", "status": "Offen|In Arbeit", "id": "<page_id_32_zeichen>"}}]
}}
page_id: Notion page ID als Hex-String ohne Bindestriche, exakt 32 Zeichen.
Falls ARBEIT_DB_ID leer: proj_tasks = []"""

ABEND_JSON_SYSTEM_PROMPT = f"""Du bist ein Notion-Abend-Assistent.
Lies den Tagesorganizer (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58).
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

SPORT_CHALLENGES_SYSTEM_PROMPT = f"""Du bist ein Sport-Assistent.
Lies die Notion-Datenbank (data_source_id: {SPORT_CHALLENGES_DB_ID}).
Filtere: Status = "Not Started".
Gruppiere die Ergebnisse nach der "Kategorie"-Property.
Gib NUR dieses JSON zurück (kein Kommentar, kein Markdown):
{{"kategorien": {{"<Kategoriename>": [{{"id": "<page_id>", "name": "<Name>"}}], ...}}}}
Wenn keine offenen Challenges: {{"kategorien": {{}}}}"""

SPORT_DONE_SYSTEM_PROMPT = f"""Du bist ein Sport-Assistent.
Du erhältst eine Notion page_id aus der Sport-Challenges-Datenbank (data_source_id: {SPORT_CHALLENGES_DB_ID}).
Setze die Property "Status" auf "Done".
Antworte NUR mit: ✅ <Name> — erledigt!
Falls nicht gefunden: ❌ Challenge nicht gefunden: <page_id>"""

EDIT_SYSTEM_PROMPT = """Du bist ein Notion-Edit-Assistent.
Nutzer-Eingabe: "<taskname> <feld> <wert>"
1. Suche Task im Tagesorganizer (data_source_id: 38b4bba29c5581a7bd94cef1b0cc6c58) per fuzzy-Suche
2. Erkenne Feld: prio/priorität → Priorität | datum → Datum | bereich → Bereich | notiz → Notiz
3. Mappe Wert:
   Prio: hoch→Hoch, mittel→Mittel, niedrig→Niedrig
   Bereich: arbeit→Arbeit, privat→Privat, lernen→Lernen, gesundheit→Gesundheit
   Datum: morgen=heute+1, übermorgen=heute+2, ISO-Datum direkt, Wochentag relativ berechnen
4. Aktualisiere die Property
Antworte NUR mit: ✏️ <Task-Name> · <Feld> → <Wert>
Falls nicht gefunden: ❌ Task nicht gefunden: "<Eingabe>" """

ARBEIT_PROJEKTE_JSON_SYSTEM_PROMPT = f"""Du bist ein Notion-Projektassistent.
Lies die Arbeitsprojekte-Datenbank (data_source_id: {ARBEIT_DB_ID}).
Filtere: Typ = Projekt, Status = In Arbeit.
Antworte AUSSCHLIESSLICH mit JSON (kein Markdown, keine Erklärung):
{{"projekte": [{{"name": "...", "id": "<page_id_32_zeichen_kein_bindestrich>"}}]}}
Falls keine aktiven Projekte: {{"projekte": []}}"""

ARBEIT_PROJEKT_CREATE_SYSTEM_PROMPT = f"""Du bist ein Notion-Projektassistent.
Lege einen neuen Eintrag in der Arbeitsprojekte-Datenbank an (data_source_id: {ARBEIT_DB_ID}).
Typ = Projekt, Status = In Arbeit. Name = der angegebene Projektname.
Antworte NUR mit: ✅ Projekt angelegt: [Name]"""

ARBEIT_EPIC_CREATE_SYSTEM_PROMPT = f"""Du bist ein Notion-Projektassistent.
Lege einen neuen Eintrag in der Arbeitsprojekte-Datenbank an (data_source_id: {ARBEIT_DB_ID}).
Typ = Epic. Suche das Projekt mit dem angegebenen Namen, setze Elterneintrag auf dessen page_id.
Status = In Arbeit. Name = der angegebene Epic-Name.
Antworte NUR mit: ✅ Epic angelegt: [Epic-Name] in [Projekt-Name]"""

ARBEIT_FEATURE_CREATE_SYSTEM_PROMPT = f"""Du bist ein Notion-Projektassistent.
Lege einen neuen Eintrag in der Arbeitsprojekte-Datenbank an (data_source_id: {ARBEIT_DB_ID}).
Typ = Feature. Suche das Epic mit dem angegebenen Namen, setze Elterneintrag auf dessen page_id.
Status = Offen. Name = der angegebene Feature-Name.
Antworte NUR mit: ✅ Feature angelegt: [Feature-Name] in [Epic-Name]"""

ARBEIT_PROJEKTE_LIST_SYSTEM_PROMPT = f"""Du bist ein Notion-Projektassistent.
Lies die Arbeitsprojekte-Datenbank (data_source_id: {ARBEIT_DB_ID}).
Zeige alle aktiven Projekte (Typ = Projekt, Status = In Arbeit).
Je Projekt: hole die 3 neuesten Features (Typ = Feature, Status = Offen oder In Arbeit) via Elterneintrag-Kette.
Format:
Zeile 1: "📁 Aktive Projekte ([N]):"
Je Projekt:
  "· [Projektname]"
  Je Feature: "  → [Feature-Name] ([Status])"
Falls keine Projekte: "Keine aktiven Projekte."
Kein Markdown."""

ARBEIT_STANDUP_SYSTEM_PROMPT = f"""Du bist ein Notion-Projektassistent.
Lies die Arbeitsprojekte-Datenbank (data_source_id: {ARBEIT_DB_ID}).
Suche das Projekt mit dem angegebenen Namen. Zeige alle offenen Features (Status = Offen oder In Arbeit).
Format:
Zeile 1: "🏗️ Standup: [Projektname]"
Je Feature: "· [Icon] [Feature-Name]"  — Icon: Offen=⬜ In Arbeit=🔨
Falls keine offenen Features: "Alle Features fertig! 🎉"
Kein Markdown."""


def _get_arbeit_features_prompt(proj_names: list) -> str:
    names_str = ", ".join(proj_names)
    return (
        "Du bist ein Notion-Projektassistent.\n"
        f"Lies die Arbeitsprojekte-Datenbank (data_source_id: {ARBEIT_DB_ID}).\n"
        "Finde alle Einträge mit Typ = Feature, Status = Offen oder In Arbeit.\n"
        f"Das übergeordnete Projekt (via Elterneintrag-Kette) muss eines dieser Projekte sein: {names_str}.\n"
        "Je Projekt maximal 3 Features (neueste zuerst nach Änderungsdatum).\n"
        'Antworte AUSSCHLIESSLICH mit JSON:\n'
        '{"features": [{"name": "...", "projekt": "...", "id": "<page_id_32_zeichen>"}]}\n'
        'Falls keine: {"features": []}'
    )


ENERGIE_ICONS = {"hoch": "🔋", "mittel": "⚡", "niedrig": "🪫"}

PRIO_ICONS = {"Hoch": "🔴", "Mittel": "🟡", "Niedrig": "🟢"}

BUTTON_MAP = {
    "📋 Task":     "task",
    "📅 Termin":   "termin",
    "💡 Ideen":    "ideen",
    "📚 Lern":     "lern",
    "🌅 Morgen":   "morgen",
    "🌙 Abend":    "abend",
    "📆 Woche":    "woche",
    "📥 Backlog":  "backlog_list",
    "🗂️ Projekte": "projekte",
    "🔋 Energie":  "energie",
    "🔄 Zyklen":   "zyklen",
}

_workflow: dict = {}
callback_state: dict = {}   # {chat_id: {action, page_id, task_name, field?, msg_id?}}


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

    settings = load_settings()
    energie_level = settings.get("energie_level")  # "hoch" / "mittel" / "niedrig" / None
    energie_icon = ENERGIE_ICONS.get(energie_level, "") if energie_level else ""

    tasks = data.get("tasks", [])
    projects: dict = {}
    for t in tasks:
        if t.get("projekt"):
            projects[t["projekt"]] = projects.get(t["projekt"], 0) + 1

    header = f"🌅 Guten Morgen! {today_str}"
    if energie_icon:
        header += f"\n{energie_icon} Energie: {energie_level.capitalize()}"
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

    # Energie-basierte Sortierung
    if energie_level == "niedrig":
        prio_order = {"Niedrig": 0, "Mittel": 1, "Hoch": 2}
    else:
        prio_order = {"Hoch": 0, "Mittel": 1, "Niedrig": 2}
    sorted_tasks = sorted(tasks, key=lambda t: prio_order.get(t.get("prio", "Mittel"), 1))

    for task in sorted_tasks:
        pid = task["id"].replace("-", "")
        prio_icon = PRIO_ICONS.get(task.get("prio", ""), "")
        label = f"{prio_icon} {task['name']}" if prio_icon else task["name"]
        if task.get("projekt"):
            label += f"  →{task['projekt']}"
        if energie_level == "niedrig" and task.get("prio") == "Hoch":
            label += "  ↔ Verschieben?"
        buttons = [[{"text": f"✅ {task['name']}", "callback_data": f"done:{pid}"}]]
        send_message(TOKEN, CHAT_ID, label, reply_markup={"inline_keyboard": buttons})

    for habit in data.get("habits", []):
        _send_habit_message(habit)

    proj_tasks = data.get("proj_tasks", [])
    if proj_tasks:
        lines = [f"🏗️ Projekt-Tasks heute ({len(proj_tasks)}):"]
        for pt in proj_tasks:
            icon = "🔨" if pt.get("status") == "In Arbeit" else "⬜"
            lines.append(f"· {icon} {pt['name']} ({pt.get('projekt', '?')})")
        send_message(TOKEN, CHAT_ID, "\n".join(lines))

    if not tasks and not data.get("habits") and not proj_tasks:
        send_message(TOKEN, CHAT_ID, "Nichts zu tun heute 🎉")


def _send_sport_challenges(chat_id: int) -> None:
    raw = run_claude_parse("Lade Sport Challenges.", system_prompt=SPORT_CHALLENGES_SYSTEM_PROMPT)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return
    kategorien = data.get("kategorien", {})
    for kat, challenges in kategorien.items():
        if not challenges:
            continue
        challenge = random.choice(challenges)
        pid = challenge["id"].replace("-", "")
        buttons = [[{"text": "✅ Erledigt", "callback_data": f"sport_done:{pid}"}]]
        send_message(TOKEN, chat_id, f"🏋️ {kat}: {challenge['name']}",
                     reply_markup={"inline_keyboard": buttons})


def _instanz_zyklen(today: str) -> None:
    prompt = ZYKLEN_INSTANZ_SYSTEM_PROMPT.replace("{today}", today)
    run_claude(prompt, automated=True)


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



def _build_projekte_message() -> tuple:
    registry = load_registry()
    if not registry:
        return "🗂️ Keine Projekte registriert.", []

    lines = ["🗂️ Aktive Projekte", ""]
    buttons = []
    for proj in registry:
        slug = proj.get("slug", "")
        name = proj.get("name", slug)
        status_path = HUB_DIR / "topics" / slug / "STATUS.md"
        features = []
        if status_path.exists():
            for line in status_path.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith("- [") and "]" in s:
                    tag = s[3:s.index("]")]
                    if tag in ("planned", "discussed"):
                        feat = s[s.index("]") + 1:].strip()
                        if " (" in feat:
                            feat = feat[:feat.index(" (")]
                        features.append(feat)
        lines.append(f"━━ {name} ━━")
        for feat in features[:3]:
            lines.append(f"· {feat}")
        if not features:
            lines.append("· (keine offenen Features)")
        buttons.append([{"text": f"📣 {name}", "callback_data": f"standup:{slug}"}])
        lines.append("")

    return "\n".join(lines).rstrip(), buttons


def start_workflow(kind: str, chat_id: int) -> None:
    today = date.today().isoformat()
    _workflow[chat_id] = {"step": f"{kind}:init", "data": {}}
    _abort = [[{"text": "✗ Abbrechen", "callback_data": "wf:abort"}]]

    if kind == "task":
        _workflow[chat_id]["step"] = "task:name"
        send_message(TOKEN, chat_id,
            "📋 Neuer Task\n\n1 / 2 · Name?",
            reply_markup={"inline_keyboard": _abort})

    elif kind == "lern":
        _workflow[chat_id]["step"] = "lern:name"
        send_message(TOKEN, chat_id,
            "📚 Neues Lernthema\n\n1 / 3 · Name?",
            reply_markup={"inline_keyboard": _abort})

    elif kind == "termin":
        _workflow[chat_id]["step"] = "termin:name"
        send_message(TOKEN, chat_id,
            "📅 Neuer Termin\n\n1 / 3 · Name?",
            reply_markup={"inline_keyboard": _abort})

    elif kind == "ideen":
        _workflow[chat_id]["step"] = "ideen:typ"
        buttons = [
            [
                {"text": "🎮 Spieleidee",  "callback_data": "ideen:typ:spieleidee"},
                {"text": "💡 Andere Idee", "callback_data": "ideen:typ:andere"},
            ],
            [{"text": "✗ Abbrechen", "callback_data": "wf:abort"}],
        ]
        send_message(TOKEN, chat_id,
            "💡 Neue Idee\n\n1 / 3 · Typ?",
            reply_markup={"inline_keyboard": buttons})

    elif kind == "morgen":
        _instanz_zyklen(today)
        send_message(TOKEN, chat_id, "⏳ Verarbeite...")
        raw = run_claude_parse(f"Heute ist {today}.", system_prompt=MOIN_JSON_SYSTEM_PROMPT)
        try:
            data = json.loads(raw)
            _send_moin_messages(data)
        except (json.JSONDecodeError, ValueError):
            response = run_claude(f"Heute ist {today}.", system_prompt=MOIN_SYSTEM_PROMPT)
            send_message(TOKEN, chat_id, response, reply_markup=REPLY_KEYBOARD)
        _send_sport_challenges(chat_id)
        _workflow.pop(chat_id, None)

    elif kind == "abend":
        send_message(TOKEN, chat_id, "⏳ Verarbeite...")
        raw = run_claude_parse(f"Heute ist {today}.", system_prompt=ABEND_JSON_SYSTEM_PROMPT)
        try:
            data = json.loads(raw)
            _send_abend_messages(data)
        except (json.JSONDecodeError, ValueError):
            response = run_claude(f"Heute ist {today}.", system_prompt=ABEND_SYSTEM_PROMPT)
            send_message(TOKEN, chat_id, response, reply_markup=REPLY_KEYBOARD)
        _workflow.pop(chat_id, None)

    elif kind == "woche":
        send_message(TOKEN, chat_id, "⏳ Verarbeite...")
        response = run_claude(f"Heute ist {today}.", system_prompt=WOCHENSICHT_SYSTEM_PROMPT)
        send_message(TOKEN, chat_id, response, reply_markup=REPLY_KEYBOARD)
        _workflow.pop(chat_id, None)

    elif kind == "backlog_list":
        send_message(TOKEN, chat_id, "⏳ Verarbeite...")
        raw = run_claude_parse(f"Heute ist {today}.", system_prompt=BACKLOG_JSON_SYSTEM_PROMPT)
        try:
            items = json.loads(raw).get("items", [])
        except (json.JSONDecodeError, ValueError):
            items = []

        if not items:
            send_message(TOKEN, chat_id, "📌 Backlog leer.", reply_markup=REPLY_KEYBOARD)
        else:
            PRIO_ICON = {"Hoch": "🔴", "Mittel": "🟡", "Niedrig": "🟢"}
            lines = [f"📌 Backlog ({len(items)} offen):"]
            buttons = []
            for i, item in enumerate(items, 1):
                icon = PRIO_ICON.get(item.get("prio", ""), "⚪")
                lines.append(f"{i}. {icon} {item['name']}")
                pid = item["id"].replace("-", "")
                buttons.append([
                    {"text": f"✅ {item['name']}", "callback_data": f"backlog_done:{pid}"},
                ])
            send_message(TOKEN, chat_id, "\n".join(lines),
                         reply_markup={"inline_keyboard": buttons})
        _workflow.pop(chat_id, None)

    elif kind == "projekte":
        msg, buttons = _build_projekte_message()
        send_message(TOKEN, chat_id, msg,
                     reply_markup={"inline_keyboard": buttons} if buttons else REPLY_KEYBOARD)
        _workflow.pop(chat_id, None)

    elif kind == "energie":
        settings = load_settings()
        current = settings.get("energie_level")
        icon = ENERGIE_ICONS.get(current, "")
        prefix = f"Aktuell: {icon} {current.capitalize()}\n\n" if current else ""
        buttons = [[
            {"text": "🔋 Hoch",    "callback_data": "energie:hoch"},
            {"text": "⚡ Mittel",  "callback_data": "energie:mittel"},
            {"text": "🪫 Niedrig", "callback_data": "energie:niedrig"},
        ]]
        send_message(TOKEN, chat_id,
            f"━━ Energie-Level ━━\n\n{prefix}Wie ist dein Energie heute?",
            reply_markup={"inline_keyboard": buttons})
        _workflow.pop(chat_id, None)

    elif kind == "zyklen":
        raw = run_claude_parse("Zeige alle Zyklen.", system_prompt=ZYKLEN_LIST_SYSTEM_PROMPT)
        try:
            zdata = json.loads(raw)
            zyklen = zdata.get("zyklen", [])
        except (json.JSONDecodeError, ValueError):
            zyklen = []

        if zyklen:
            lines = ["━━ Zyklische Tasks ━━", "", "📋 Aktiv:"]
            for z in zyklen:
                lines.append(f"  • {z['name']} — {z['zyklus']}")
            text = "\n".join(lines)
        else:
            text = "━━ Zyklische Tasks ━━\n\nKeine zyklischen Tasks."

        del_buttons = [
            [{"text": f"🗑️ {z['name']}", "callback_data": f"zyklen_del:{z['id'].replace('-', '')}"}]
            for z in zyklen
        ]
        action_buttons = [[
            {"text": "➕ Neu",       "callback_data": "zyklen:neu"},
            {"text": "✗ Schließen", "callback_data": "wf:abort"},
        ]]
        send_message(TOKEN, chat_id, text,
            reply_markup={"inline_keyboard": del_buttons + action_buttons})
        _workflow.pop(chat_id, None)


def handle_workflow_step(text: str, chat_id: int, today: str) -> bool:
    """Returns True if text was consumed by active workflow."""
    if chat_id not in _workflow:
        return False
    state = _workflow[chat_id]
    step = state["step"]
    _abort = [[{"text": "✗ Abbrechen", "callback_data": "wf:abort"}]]

    if step == "task:name":
        state["data"]["name"] = text
        state["step"] = "task:priority"
        buttons = [[
            {"text": "🔴 Hoch",    "callback_data": "task:priority:hoch"},
            {"text": "🟡 Mittel",  "callback_data": "task:priority:mittel"},
            {"text": "🟢 Niedrig", "callback_data": "task:priority:niedrig"},
        ]]
        send_message(TOKEN, chat_id,
            f'📋 "{text}"\n\n2 / 2 · Priorität?',
            reply_markup={"inline_keyboard": buttons})
        return True

    if step == "lern:name":
        state["data"]["name"] = text
        state["step"] = "lern:kategorie"
        buttons = [
            [
                {"text": "💻 Programmierung", "callback_data": "lern:kategorie:programmierung"},
                {"text": "🗣 Sprachen",        "callback_data": "lern:kategorie:sprachen"},
            ],
            [
                {"text": "📐 Mathematik",      "callback_data": "lern:kategorie:mathematik"},
                {"text": "🎨 Design",           "callback_data": "lern:kategorie:design"},
            ],
            [{"text": "📦 Sonstiges", "callback_data": "lern:kategorie:sonstiges"}],
        ]
        send_message(TOKEN, chat_id,
            f'📚 "{text}"\n\n2 / 3 · Kategorie?',
            reply_markup={"inline_keyboard": buttons})
        return True

    if step == "termin:name":
        state["data"]["name"] = text
        state["step"] = "termin:datum"
        send_message(TOKEN, chat_id,
            f'📅 "{text}"\n\n2 / 3 · Datum? (z.B. morgen, 2026-07-01, heute um 14:00)',
            reply_markup={"inline_keyboard": _abort})
        return True

    if step == "termin:datum":
        state["data"]["datum"] = text
        state["step"] = "termin:priority"
        name = state["data"]["name"]
        buttons = [[
            {"text": "🔴 Hoch",    "callback_data": "termin:priority:hoch"},
            {"text": "🟡 Mittel",  "callback_data": "termin:priority:mittel"},
            {"text": "🟢 Niedrig", "callback_data": "termin:priority:niedrig"},
        ]]
        send_message(TOKEN, chat_id,
            f'📅 "{name}" · {text}\n\n3 / 3 · Priorität?',
            reply_markup={"inline_keyboard": buttons})
        return True

    if step == "ideen:name":
        state["data"]["name"] = text
        state["step"] = "ideen:details"
        send_message(TOKEN, chat_id,
            f'💡 "{text}"\n\nBeschreibung? (oder "–" zum Überspringen)',
            reply_markup={"inline_keyboard": _abort})
        return True

    if step == "ideen:details":
        name = state["data"].get("name", "?")
        details = "" if text.strip() == "–" else text
        _workflow.pop(chat_id, None)
        full_text = f"{name}. {details}" if details else name
        result = run_claude(full_text, system_prompt=IDEE_SYSTEM_PROMPT, automated=True)
        send_message(TOKEN, chat_id, result, reply_markup=REPLY_KEYBOARD)
        return True

    if step == "zyklen:name":
        state["data"]["name"] = text
        state["step"] = "zyklen:rhythmus"
        buttons = [[
            {"text": "📅 Täglich",     "callback_data": "zyklen:rhythmus:täglich"},
            {"text": "📆 Wöchentlich", "callback_data": "zyklen:rhythmus:wöchentlich"},
        ]]
        send_message(TOKEN, chat_id,
            f'🔄 "{text}"\n\n2 / 2 · Rhythmus?',
            reply_markup={"inline_keyboard": buttons})
        return True

    return False


def _handle_callback(cq: dict) -> None:
    chat_id: int = cq["from"]["id"]
    data: str = cq.get("data", "")
    msg_id: int = cq["message"]["message_id"]
    msg_text: str = cq["message"].get("text", "")
    today: str = date.today().isoformat()

    # Workflow: abort
    if data == "wf:abort":
        _workflow.pop(chat_id, None)
        answer_callback_query(TOKEN, cq["id"])
        send_message(TOKEN, chat_id, "❌ Abgebrochen.", reply_markup=REPLY_KEYBOARD)
        return

    if data.startswith("energie:"):
        level = data.split(":")[1]
        settings = load_settings()
        settings["energie_level"] = level
        settings["energie_updated"] = datetime.now().isoformat(timespec="seconds")
        save_settings(settings)
        icon = ENERGIE_ICONS.get(level, "")
        send_message(TOKEN, CHAT_ID,
            f"✓ Energie: {icon} {level.capitalize()} gespeichert.",
            reply_markup=REPLY_KEYBOARD)
        return

    # Task: final priority step
    if data.startswith("task:priority:"):
        prio_key = data.split(":")[-1]
        prio = {"hoch": "Hoch", "mittel": "Mittel", "niedrig": "Niedrig"}.get(prio_key, "Mittel")
        state = _workflow.pop(chat_id, {})
        name = state.get("data", {}).get("name", "?")
        answer_callback_query(TOKEN, cq["id"])
        result = run_claude(
            f"Heute ist {today}. Backlog-Aufgabe: {name}. Priorität: {prio}.",
            system_prompt=BACKLOG_SYSTEM_PROMPT, automated=True,
        )
        send_message(TOKEN, chat_id, result, reply_markup=REPLY_KEYBOARD)
        return

    # Lern: kategorie step
    if data.startswith("lern:kategorie:"):
        kat_key = data.split(":")[-1]
        kat = {"programmierung": "Programmierung", "sprachen": "Sprachen",
               "mathematik": "Mathematik", "design": "Design",
               "sonstiges": "Sonstiges"}.get(kat_key, "Sonstiges")
        state = _workflow.get(chat_id, {})
        state.setdefault("data", {})["kategorie"] = kat
        state["step"] = "lern:prioritaet"
        answer_callback_query(TOKEN, cq["id"])
        name = state.get("data", {}).get("name", "?")
        buttons = [[
            {"text": "🔴 Hoch",    "callback_data": "lern:prioritaet:hoch"},
            {"text": "🟡 Mittel",  "callback_data": "lern:prioritaet:mittel"},
            {"text": "🟢 Niedrig", "callback_data": "lern:prioritaet:niedrig"},
        ]]
        send_message(TOKEN, chat_id,
            f'📚 "{name}" · {kat}\n\n3 / 3 · Priorität?',
            reply_markup={"inline_keyboard": buttons})
        return

    # Lern: final priority step
    if data.startswith("lern:prioritaet:"):
        prio_key = data.split(":")[-1]
        prio = {"hoch": "Hoch", "mittel": "Mittel", "niedrig": "Niedrig"}.get(prio_key, "Mittel")
        state = _workflow.pop(chat_id, {})
        name = state.get("data", {}).get("name", "?")
        kat = state.get("data", {}).get("kategorie", "Sonstiges")
        answer_callback_query(TOKEN, cq["id"])
        result = run_claude(
            f"{name}. Kategorie: {kat}. Priorität: {prio}.",
            system_prompt=LERN_SYSTEM_PROMPT, automated=True,
        )
        send_message(TOKEN, chat_id, result, reply_markup=REPLY_KEYBOARD)
        return

    # Termin: final priority step
    if data.startswith("termin:priority:"):
        prio_key = data.split(":")[-1]
        prio = {"hoch": "Hoch", "mittel": "Mittel", "niedrig": "Niedrig"}.get(prio_key, "Mittel")
        state = _workflow.pop(chat_id, {})
        name = state.get("data", {}).get("name", "?")
        datum = state.get("data", {}).get("datum", "heute")
        answer_callback_query(TOKEN, cq["id"])
        result = run_claude(
            f"Heute ist {today}. Termin: {name}. Datum/Uhrzeit: {datum}. Priorität: {prio}.",
            system_prompt=TERMIN_SYSTEM_PROMPT, automated=True,
        )
        send_message(TOKEN, chat_id, result, reply_markup=REPLY_KEYBOARD)
        return

    # Ideen: typ selection → move to name step
    if data.startswith("ideen:typ:"):
        typ_key = data.split(":")[-1]
        typ = "Spieleidee" if typ_key == "spieleidee" else "Andere Idee"
        state = _workflow.get(chat_id, {})
        state.setdefault("data", {})["typ"] = typ
        state["step"] = "ideen:name"
        answer_callback_query(TOKEN, cq["id"])
        send_message(TOKEN, chat_id,
            f'💡 {typ}\n\n2 / 3 · Name?',
            reply_markup={"inline_keyboard": [[{"text": "✗ Abbrechen", "callback_data": "wf:abort"}]]})
        return

    # Projekte: standup for a project
    if data.startswith("standup:"):
        slug = data[8:]
        status_path = HUB_DIR / "topics" / slug / "STATUS.md"
        answer_callback_query(TOKEN, cq["id"])
        if not status_path.exists():
            send_message(TOKEN, chat_id, f"❌ Kein STATUS.md für {slug}.", reply_markup=REPLY_KEYBOARD)
            return
        active = ""
        features = []
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Active:"):
                active = line[7:].strip()
            s = line.strip()
            if s.startswith("- [planned]") or s.startswith("- [discussed]"):
                feat = s.split("]", 1)[1].strip()
                if " (" in feat:
                    feat = feat[:feat.index(" (")]
                features.append(feat)
        lines = [f"📣 Standup — {slug}"]
        if active and active not in ("(none)", ""):
            lines.append(f"🔧 Aktiv: {active}")
        for feat in features:
            lines.append(f"· {feat}")
        if not features:
            lines.append("· (nichts in Planung)")
        send_message(TOKEN, chat_id, "\n".join(lines), reply_markup=REPLY_KEYBOARD)
        return

    if data == "zyklen:neu":
        _workflow[chat_id] = {"step": "zyklen:name", "data": {}}
        send_message(TOKEN, CHAT_ID,
            "🔄 Neuer zyklischer Task\n\n1 / 2 · Name?",
            reply_markup={"inline_keyboard": [[{"text": "✗ Abbrechen", "callback_data": "wf:abort"}]]})
        return

    if data.startswith("zyklen:rhythmus:"):
        rhythmus = data.split(":", 2)[2]
        if rhythmus == "wöchentlich":
            state = _workflow.get(chat_id, {})
            name = state.get("data", {}).get("name", "?")
            buttons = [[
                {"text": "Mo", "callback_data": "zyklen:tag:wöchentlich_mo"},
                {"text": "Di", "callback_data": "zyklen:tag:wöchentlich_di"},
                {"text": "Mi", "callback_data": "zyklen:tag:wöchentlich_mi"},
                {"text": "Do", "callback_data": "zyklen:tag:wöchentlich_do"},
            ], [
                {"text": "Fr", "callback_data": "zyklen:tag:wöchentlich_fr"},
                {"text": "Sa", "callback_data": "zyklen:tag:wöchentlich_sa"},
                {"text": "So", "callback_data": "zyklen:tag:wöchentlich_so"},
            ]]
            send_message(TOKEN, CHAT_ID,
                f'🔄 "{name}" — Wöchentlich\n\nWelcher Tag?',
                reply_markup={"inline_keyboard": buttons})
            return
        state = _workflow.pop(chat_id, {})
        name = state.get("data", {}).get("name", "?")
        result = run_claude(
            ZYKLEN_NEU_SYSTEM_PROMPT.replace("{name}", name).replace("{zyklus}", rhythmus),
            automated=True,
        )
        send_message(TOKEN, CHAT_ID, result, reply_markup=REPLY_KEYBOARD)
        return

    if data.startswith("zyklen:tag:"):
        zyklus = data.split(":", 2)[2]
        state = _workflow.pop(chat_id, {})
        name = state.get("data", {}).get("name", "?")
        result = run_claude(
            ZYKLEN_NEU_SYSTEM_PROMPT.replace("{name}", name).replace("{zyklus}", zyklus),
            automated=True,
        )
        send_message(TOKEN, CHAT_ID, result, reply_markup=REPLY_KEYBOARD)
        return

    if data.startswith("zyklen_del:"):
        page_id = data.split(":", 1)[1]
        result = run_claude(
            ZYKLEN_DELETE_SYSTEM_PROMPT.replace("{page_id}", page_id),
            automated=True,
        )
        send_message(TOKEN, CHAT_ID, result, reply_markup=REPLY_KEYBOARD)
        return

    if data.startswith("done:"):
        pid = data[5:]
        ok = notion_direct.mark_done(pid)
        label = _extract_name_from_message(msg_text)
        edit_message(TOKEN, chat_id, msg_id, f"✅ {label} — erledigt!" if ok else f"❌ Fehler bei {label}")

    elif data.startswith("habit_done:"):
        pid = data[11:]
        send_message(TOKEN, chat_id, "⏳ Habit wird aktualisiert...")
        result = run_claude(
            f"Heute ist {today}. page_id: {pid}.",
            system_prompt=HABIT_DONE_SYSTEM_PROMPT, automated=True,
        )
        edit_message(TOKEN, chat_id, msg_id, result)

    elif data.startswith("sport_done:"):
        pid = data[11:]
        ok = notion_direct.mark_sport_done(pid)
        label = _extract_name_from_message(msg_text)
        edit_message(TOKEN, chat_id, msg_id, f"✅ {label} — erledigt!" if ok else "❌ Fehler")

    if data.startswith("backlog_done:"):
        pid = data.split(":", 1)[1]
        answer_callback_query(TOKEN, cq["id"])
        ok = notion_direct.archive_backlog_item(pid)
        if ok:
            send_message(TOKEN, chat_id, "✅ Backlog-Item archiviert.", reply_markup=REPLY_KEYBOARD)
        else:
            send_message(TOKEN, chat_id, "❌ Archivierung fehlgeschlagen.", reply_markup=REPLY_KEYBOARD)
        return

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
            notion_direct.reschedule(pid, target)
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
    s = load_settings()
    s["active_session"] = "organizer"
    save_settings(s)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=3600, cwd=base_dir)
        if result.returncode != 0:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=3600, cwd=base_dir)
    finally:
        s = load_settings()
        s["active_session"] = None
        save_settings(s)
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


class _WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        self.send_response(200)
        self.end_headers()
        try:
            upd = json.loads(body)
        except Exception:
            return
        threading.Thread(target=_dispatch_update, args=(upd,), daemon=True).start()

    def log_message(self, *args):
        pass


def _dispatch_update(upd: dict) -> None:
    if "callback_query" in upd:
        cq = upd["callback_query"]
        if cq["from"]["id"] != CHAT_ID:
            return
        answer_callback_query(TOKEN, cq["id"])
        if cq.get("data") == "__freitext__":
            send_message(TOKEN, CHAT_ID, "Bitte Antwort eintippen:")
        else:
            _handle_callback(cq)
    elif "message" in upd:
        msg = upd.get("message", {})
        if msg.get("chat", {}).get("id") == CHAT_ID:
            _handle_message(msg)


def _handle_message(msg: dict) -> None:
    chat_id = msg.get("chat", {}).get("id")
    if not chat_id:
        return

    if "voice" in msg:
        try:
            raw = transcribe_voice(TOKEN, msg["voice"]["file_id"])
            text = normalize_voice(raw)
        except Exception as e:
            send_message(TOKEN, CHAT_ID, f"❌ Spracheingabe fehlgeschlagen: {e}")
            return
    else:
        text = msg.get("text", "").strip()
    if not text:
        return

    today = date.today().isoformat()

    if chat_id in callback_state and text:
        cb = callback_state[chat_id]
        _is_interrupt = (
            text.lower() in ("erinnerungen", "/plans")
            or any(text.lower().startswith(p) for p in (
                "erinnere", "erinnerung:", "implement-plan:",
                "abort-plan:", "impl-mode:"))
            or text in BUTTON_MAP
        )
        if _is_interrupt:
            del callback_state[chat_id]
        elif cb["action"] == "edit_text":
            del callback_state[chat_id]
            _apply_task_update(cb["page_id"], cb["field"], text, today)
            send_message(TOKEN, CHAT_ID,
                         f"✏️ {cb['task_name']} · {cb['field'].capitalize()} aktualisiert",
                         reply_markup=REPLY_KEYBOARD)
            return
        elif cb["action"] == "reschedule_text":
            del callback_state[chat_id]
            _apply_task_update(cb["page_id"], "datum", text, today)
            send_message(TOKEN, CHAT_ID,
                         f"📅 {cb.get('task_name', '')} — Datum aktualisiert",
                         reply_markup=REPLY_KEYBOARD)
            return

    if handle_workflow_step(text, chat_id, today):
        return

    t = text.strip()
    response = None

    if t.lower().startswith("erinnere") or t.lower().startswith("erinnerung:"):
        now_time = datetime.now().strftime("%H:%M")
        raw = run_claude_parse(
            f"Heute ist {today}, aktuelle Uhrzeit: {now_time}. Nutzer schreibt: {text}",
            system_prompt=REMINDER_PARSE_SYSTEM_PROMPT,
        )
        try:
            parsed = json.loads(raw)
            _add_reminder(parsed["text"], parsed["due"])
            due_dt = datetime.fromisoformat(parsed["due"])
            response = f"⏰ Erinnerung gesetzt: {parsed['text']} — {due_dt.strftime('%d.%m.%Y um %H:%M')}"
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[reminder parse error] raw={repr(raw)} exc={e}")
            response = "❌ Konnte Erinnerung nicht parsen. Versuche: erinnere mich um 14:00 an Zahnarzt"

    elif t.lower() == "erinnerungen":
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

    elif t.lower() == "/plans":
        response = _format_plans()

    elif t in ("/energie",):
        start_workflow("energie", chat_id)
        return

    elif t in ("/zyklen",):
        start_workflow("zyklen", chat_id)
        return

    elif t in BUTTON_MAP:
        start_workflow(BUTTON_MAP[t], chat_id)
        return

    if response:
        send_message(TOKEN, CHAT_ID, response, reply_markup=REPLY_KEYBOARD)


def main():
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

    set_my_commands(TOKEN, [
        {"command": "plans",   "description": "Geplante Implementierungen anzeigen"},
        {"command": "energie", "description": "Energie-Level für heute setzen"},
        {"command": "zyklen",  "description": "Zyklische Tasks verwalten"},
    ])

    server = ThreadingHTTPServer(("127.0.0.1", PORT), _WebhookHandler)
    print(f"Organizer Bot gestartet (webhook, port {PORT}, chat_id={CHAT_ID})")
    server.serve_forever()


if __name__ == "__main__":
    main()

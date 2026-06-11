import os, re, subprocess, requests, tempfile, sys, json
from datetime import date
from pathlib import Path
from groq import Groq

TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
MY_CHAT_ID = 8896609541
HABITS_DATA_SOURCE_ID = "6a4d7e7d-dcde-44e3-b7a0-c46330a6261c"
BASE = f"https://api.telegram.org/bot{TOKEN}"
WORK_DIR = r"C:\Projekte\telegram-notion-bot"
TEACH_DIR = r"C:\Projekte\teach"
PAGES_BASE = "https://djtj9.github.io/teach-lessons"
COURSE_NAMES = {
    "cli-notion-agent": "Kurs: CLI Notion Agent",
    "projekt-planung":  "Kurs: Projekt-Planung",
}

PROJECTS = {
    "notion": {"path": r"C:\Projekte\telegram-notion-bot", "notion_name": "Notion-Bot"},
    "dart":   {"path": r"C:\Unity\Aktuelle Projekte\DartTrainingsApp", "notion_name": "Dart-App"},
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

🛠 Sonstiges
  teach: <text> — Lernkurs erstellen
  restart — Bot neu starten

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
Zeige alle Tasks mit Datum = heute ODER ohne Datum, Status Not started oder In progress.

Format:
Zeile 1: "🌅 Guten Morgen! [N] Tasks heute"
Zeile 2 (nur wenn Projekt-Tasks vorhanden): "📁 " + je Projekt "[Name] ([N])" mit " · " getrennt
Leerzeile
Je Task: "· [Prio-Icon] [→Projekt falls gesetzt] [Name]"
Prio-Icons: Hoch=🔴 Mittel=🟡 Niedrig=🟢
Sortiere nach Priorität (Hoch zuerst), dann alphabetisch.

Dann lies die Habits-Datenbank (data_source_id: {HABITS_DATA_SOURCE_ID}).
Zeige alle Habits mit Nächste Fälligkeit ≤ heute UND Status = Aktiv.
Falls solche Habits vorhanden:
  Leerzeile
  Zeile: "🔄 Habits heute ([N]):"
  Je Habit: "· [Name] (alle [Intervall] Tage)"
Falls keine fälligen Habits: diese Sektion weglassen.

Kein Markdown. Kein Datum in der Task-Liste."""

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

def run_claude(prompt, system_prompt=None, cwd=None):
    cmd = ["claude", "--dangerously-skip-permissions"]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    cmd += ["-p", prompt]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=1200, cwd=cwd or WORK_DIR)
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
                prompt="task: erledigt: status: fokus: lern: idee: habit: verschieben:",
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
_active_permission_id = None

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

if __name__ == "__main__":
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
                cmd = str(tool_input.get("command", tool_input))[:200]
                msg_text = f"🔐 Permission needed:\nTool: {req['tool']}\n$ {cmd}"
                inline_kb = {"inline_keyboard": [[
                    {"text": "Ja ✅", "callback_data": f"approve_{req['request_id']}"},
                    {"text": "Nein ❌", "callback_data": f"deny_{req['request_id']}"},
                ]]}
                send_message(MY_CHAT_ID, msg_text, reply_markup=inline_kb)
                _active_permission_id = req["request_id"]
                pending_path.unlink()
            except Exception as e:
                print(f"permission check error: {e}")

        poll_timeout = 5 if _active_permission_id else 30
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
                cb_data = cb.get("data", "")
                if cb_data.startswith("approve_") or cb_data.startswith("deny_"):
                    request_id = cb_data.split("_", 1)[1]
                    approved = cb_data.startswith("approve_")
                    resp_path = Path(WORK_DIR) / f"permission_response_{request_id}.json"
                    resp_path.write_text(json.dumps({"approved": approved, "request_id": request_id}))
                    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                    action = "genehmigt ✅" if approved else "abgelehnt ❌"
                    send_message(MY_CHAT_ID, f"Permission {action}")
                    if _active_permission_id == request_id:
                        _active_permission_id = None
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
                    text = normalize_voice(transcribe_voice(voice["file_id"]))
                    send_message(chat_id, f"🎤 Erkannt: {text}")
                except Exception as e:
                    send_message(chat_id, f"❌ Transkription fehlgeschlagen: {e}")
                    continue
            elif not text:
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

            if text.lower() == "projekte":
                lines = ["📁 Verfügbare Projekte:"]
                for name, info in PROJECTS.items():
                    lines.append(f"  {name}: → {info['path']}")
                lines.append("\nNutzung: <name>: <frage>  |  <name>: tasks  |  <name>: task: <aufgabe>")
                send_message(chat_id, "\n".join(lines))
                continue

            if chat_id in pending_task_input:
                _is_command = (text.lower() in ("restart", "projekte", "moin", "abend", "woche", "hilfe")
                               or any(text.lower().startswith(p) for p in
                                      ("task:", "status:", "fokus:", "verschieben:", "lern:",
                                       "idee:", "habit:", "projekt:", "teach:")))
                if _is_command:
                    del pending_task_input[chat_id]
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
                    pending_task_input[chat_id] = True
                    response = "Schreib mir: Name, Priorität (Hoch/Mittel/Niedrig), Bereich (Arbeit/Privat/Lernen/Gesundheit)\nz.B.: Arzttermin, Hoch, Gesundheit"
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
            elif text.lower() == "hilfe":
                response = HILFE_TEXT
            elif text.lower().startswith("status:"):
                status_text = text[7:].strip()
                if not status_text:
                    response = "Nutzung: status: <Taskname> <Status>  z.B. status: Sport erledigt"
                else:
                    prompt = f"Heute ist {today}. Anfrage: {status_text}"
                    response = run_claude(prompt, system_prompt=STATUS_SYSTEM_PROMPT)
            elif text.lower().startswith("/teach") or text.lower().startswith("teach:"):
                response = run_claude_with_history(chat_id, text, cwd=os.path.dirname(TEACH_DIR))
            else:
                response = run_claude_with_history(chat_id, text, cwd=project_cwd)

            send_message(chat_id, response, reply_markup=REPLY_KEYBOARD)
            publish_new_lessons(chat_id)
            print(f"[{text[:40]}] → {response[:60]}")

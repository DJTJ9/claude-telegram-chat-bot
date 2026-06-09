import os, subprocess, requests
from datetime import date

TOKEN = os.environ["TELEGRAM_TOKEN"]
MY_CHAT_ID = 8896609541
BASE = f"https://api.telegram.org/bot{TOKEN}"
WORK_DIR = r"C:\Unity\Aktuelle Projekte\DartTrainingsApp"

TASK_SYSTEM_PROMPT = """Du bist ein Notion-Task-Assistent. Der Nutzer schickt eine Aufgabe als Freitext.
Lege die Aufgabe im Tagesorganizer an (data_source_id: c9d2abbe-5607-44c2-bbf4-9aa673e0c4a0).
Leite aus dem Text ab: Name, Datum (ISO 8601, heute falls nicht angegeben), Priorität (Hoch/Mittel/Niedrig, Mittel falls nicht angegeben), Bereich (Arbeit/Privat/Lernen/Gesundheit, Privat falls unklar).
Antworte NUR mit einer Zeile: ✅ Task angelegt: [Name] · [Datum] · [Priorität] · [Bereich]"""

def get_updates(offset=None):
    params = {"timeout": 30, "offset": offset}
    r = requests.get(f"{BASE}/getUpdates", params=params, timeout=35)
    return r.json().get("result", [])

def send_message(chat_id, text):
    requests.post(f"{BASE}/sendMessage", json={"chat_id": chat_id, "text": text})

def run_claude(prompt, system_prompt=None):
    cmd = ["claude", "--dangerously-skip-permissions"]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    cmd += ["-p", prompt]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120, cwd=WORK_DIR)
    return (result.stdout or "").strip() or (result.stderr or "").strip() or "(keine Antwort)"

offset = None
today = date.today().isoformat()
print(f"Bridge läuft ({today}). Strg+C zum Beenden.")

while True:
    updates = get_updates(offset)
    for update in updates:
        offset = update["update_id"] + 1
        msg = update.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "").strip()

        if chat_id != MY_CHAT_ID or not text:
            continue

        send_message(chat_id, "⏳ Denke nach...")

        if text.lower().startswith("task:"):
            task_text = text[5:].strip()
            prompt = f"Heute ist {today}. Aufgabe: {task_text}"
            response = run_claude(prompt, system_prompt=TASK_SYSTEM_PROMPT)
        else:
            response = run_claude(text)

        send_message(chat_id, response)
        print(f"[{text[:40]}] → {response[:60]}")

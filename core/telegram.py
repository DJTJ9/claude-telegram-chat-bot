import os, re, tempfile
import requests
from groq import Groq

_groq = None

def _groq_client():
    global _groq
    if _groq is None:
        _groq = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _groq

def _base(token):
    return f"https://api.telegram.org/bot{token}"

def get_updates(token, offset=None, timeout=30):
    params = {"timeout": timeout, "offset": offset}
    r = requests.get(f"{_base(token)}/getUpdates", params=params, timeout=timeout + 5)
    return r.json().get("result", [])

def send_message(token, chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    r = requests.post(f"{_base(token)}/sendMessage", json=payload)
    return r.json().get("result", {}).get("message_id")

def answer_callback_query(token, callback_query_id):
    requests.post(f"{_base(token)}/answerCallbackQuery",
                  json={"callback_query_id": callback_query_id})

def edit_message_keyboard(token, chat_id, message_id, inline_keyboard):
    requests.post(
        f"{_base(token)}/editMessageReplyMarkup",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": {"inline_keyboard": inline_keyboard},
        },
    )

def build_inline_keyboard(question):
    """Parse question text and return InlineKeyboardMarkup rows."""
    q = question.lower()
    rows = []
    opts = re.findall(r'\b([A-D])\)', question)
    if opts:
        rows.append([{"text": o, "callback_data": o} for o in opts])
        rows.append([{"text": "Freitext", "callback_data": "__freitext__"}])
        return rows
    if re.search(r'\bja\b', q) and re.search(r'\bnein\b', q):
        rows.append([
            {"text": "Ja", "callback_data": "ja"},
            {"text": "Nein", "callback_data": "nein"},
        ])
        rows.append([{"text": "Freitext", "callback_data": "__freitext__"}])
        return rows
    if re.search(r'\byes\b', q) and re.search(r'\bno\b', q):
        rows.append([
            {"text": "Yes", "callback_data": "yes"},
            {"text": "No", "callback_data": "no"},
        ])
        rows.append([{"text": "Freitext", "callback_data": "__freitext__"}])
        return rows
    rows.append([{"text": "Freitext", "callback_data": "__freitext__"}])
    return rows

def transcribe_voice(token, file_id):
    r = requests.get(f"{_base(token)}/getFile", params={"file_id": file_id})
    file_path = r.json()["result"]["file_path"]
    audio_data = requests.get(
        f"https://api.telegram.org/file/bot{token}/{file_path}"
    ).content
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_data)
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as f:
            t = _groq_client().audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                prompt="task: erledigt: status: fokus: lern: idee: habit: verschieben: erinnere mich um:",
            )
        return t.text
    finally:
        os.unlink(tmp_path)

def normalize_voice(text):
    text = re.sub(r' Doppelpunkt\b', ':', text, flags=re.IGNORECASE)
    text = re.sub(r' Komma\b', ',', text, flags=re.IGNORECASE)
    text = re.sub(r' Punkt\b', '.', text, flags=re.IGNORECASE)
    return text

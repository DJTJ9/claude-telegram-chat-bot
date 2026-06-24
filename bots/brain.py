import os, sys, json, time
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

from core.telegram import (
    get_updates, send_message, answer_callback_query,
    edit_message, transcribe_voice, build_inline_keyboard,
)
from core.settings import load_settings, save_settings

TOKEN = os.environ["TOKEN_BRAIN"]
CHAT_ID = int(os.environ.get("CHAT_ID", "0"))
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
HUB_DIR = Path(os.environ.get("HUB_DIR", str(WORK_DIR)))

_relay_request_id: str | None = None
_accordion_msg_id: int | None = None
_capture_state: dict | None = None


# ── Relay watchdog ────────────────────────────────────────────────────────────

def _write_relay_response(request_id: str, answer: str) -> None:
    (WORK_DIR / f"question_response_{request_id}.json").write_text(
        json.dumps({"answer": answer})
    )


def _check_relay_question() -> None:
    global _relay_request_id
    pq_path = WORK_DIR / "pending_question.json"
    if not pq_path.exists():
        return
    try:
        data = json.loads(pq_path.read_text())
    except Exception:
        return
    request_id = data.get("request_id")
    if not request_id or request_id == _relay_request_id:
        return
    question = data.get("question", "")
    keyboard = build_inline_keyboard(question)
    send_message(TOKEN, CHAT_ID, f"🤖 CC-Session fragt:\n{question}",
                 reply_markup={"inline_keyboard": keyboard})
    _relay_request_id = request_id


def _handle_relay_callback(callback_query_id: str, answer: str) -> None:
    global _relay_request_id
    if _relay_request_id is None:
        answer_callback_query(TOKEN, callback_query_id)
        return
    _write_relay_response(_relay_request_id, answer)
    _relay_request_id = None
    (WORK_DIR / "pending_question.json").unlink(missing_ok=True)
    answer_callback_query(TOKEN, callback_query_id)
    send_message(TOKEN, CHAT_ID, f"✅ Antwort gesendet: {answer}")


# ── Accordion UI ──────────────────────────────────────────────────────────────

def _load_projects() -> list[dict]:
    path = HUB_DIR / "projects-registry.json"
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _get_dev_status(slug: str) -> tuple[str, str]:
    path = HUB_DIR / "topics" / slug / "STATUS.md"
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return "", ""
    active = phase = ""
    for line in lines:
        if line.startswith("Active:"):
            active = line.split(":", 1)[1].strip()
        elif line.startswith("Phase:"):
            phase = line.split(":", 1)[1].strip()
    return active, phase


def _build_main_keyboard(projects: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = [[
        {"text": "🔔 Notify an", "callback_data": "notify:on"},
        {"text": "🔇 Notify aus", "callback_data": "notify:off"},
    ]]
    for p in projects:
        rows.append([{"text": f"📁 {p['name']}", "callback_data": f"proj:{p['slug']}"}])
    return rows


def _show_main_menu() -> None:
    global _accordion_msg_id
    projects = _load_projects()
    keyboard = _build_main_keyboard(projects)
    text = "🤖 Brain Bot\nWähle ein Projekt oder Aktion:"
    if _accordion_msg_id:
        edit_message(TOKEN, CHAT_ID, _accordion_msg_id, text,
                     reply_markup={"inline_keyboard": keyboard})
    else:
        mid = send_message(TOKEN, CHAT_ID, text,
                           reply_markup={"inline_keyboard": keyboard})
        if mid:
            _accordion_msg_id = mid


def _toggle_notify(value: bool) -> None:
    path = WORK_DIR / "settings.json"
    try:
        settings = json.loads(path.read_text())
    except Exception:
        settings = {}
    settings["notifications_enabled"] = value
    path.write_text(json.dumps(settings, indent=2))


def _handle_callback(cq: dict) -> None:
    global _capture_state
    cq_id = cq["id"]
    data = cq.get("data", "")

    if data == "__freitext__":
        send_message(TOKEN, CHAT_ID, "Bitte Antwort eintippen:")
        answer_callback_query(TOKEN, cq_id)
        return

    is_relay_answer = (
        _relay_request_id is not None
        and not data.startswith(("proj:", "notify:", "status:", "capture:", "back"))
    )
    if is_relay_answer:
        _handle_relay_callback(cq_id, data)
        return

    if data == "back":
        _show_main_menu()
        answer_callback_query(TOKEN, cq_id)

    elif data.startswith("proj:"):
        slug = data[5:]
        projects = _load_projects()
        proj = next((p for p in projects if p["slug"] == slug), {"name": slug})
        active, phase = _get_dev_status(slug)
        status_text = f"Active: {active}\nPhase: {phase}" if active else "(kein aktives Feature)"
        sub_keyboard = [
            [
                {"text": "📊 Dev Status", "callback_data": f"status:{slug}"},
                {"text": "💡 Idee erfassen", "callback_data": f"capture:{slug}"},
            ],
            [{"text": "← Zurück", "callback_data": "back"}],
        ]
        if _accordion_msg_id:
            edit_message(TOKEN, CHAT_ID, _accordion_msg_id,
                         f"📁 {proj['name']}\n{status_text}",
                         reply_markup={"inline_keyboard": sub_keyboard})
        answer_callback_query(TOKEN, cq_id)

    elif data.startswith("status:"):
        slug = data[7:]
        active, phase = _get_dev_status(slug)
        answer_callback_query(TOKEN, cq_id,
                              text=f"Active: {active or '—'} | Phase: {phase or '—'}")

    elif data == "notify:on":
        _toggle_notify(True)
        answer_callback_query(TOKEN, cq_id, text="✅ Notify an")

    elif data == "notify:off":
        _toggle_notify(False)
        answer_callback_query(TOKEN, cq_id, text="✅ Notify aus")

    elif data.startswith("capture:"):
        slug = data[8:]
        projects = _load_projects()
        proj = next((p for p in projects if p["slug"] == slug), {"name": slug})
        _capture_state = {"slug": slug, "name": proj["name"]}
        send_message(TOKEN, CHAT_ID,
                     f"💡 Schreib oder sprich deine Idee für {proj['name']}:")
        answer_callback_query(TOKEN, cq_id)

    else:
        answer_callback_query(TOKEN, cq_id)


# ── Quick-Capture ─────────────────────────────────────────────────────────────

def _groq_client():
    from groq import Groq
    return Groq()


def _summarize_idea(text: str) -> str:
    response = _groq_client().chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{
            "role": "user",
            "content": (
                f"Fasse diese Idee in einem prägnanten Satz zusammen "
                f"(max. 100 Zeichen): {text}"
            ),
        }],
    )
    return response.choices[0].message.content.strip()


def _append_idea(slug: str, summary: str) -> None:
    idea_line = f"- [idea]      {summary}\n"
    for filename in ("STATUS.md", "VISION.md"):
        path = HUB_DIR / "topics" / slug / filename
        if path.exists():
            with open(path, "a") as f:
                f.write(idea_line)


def _handle_message(msg: dict) -> None:
    global _capture_state
    text = msg.get("text", "")

    if text == "/start":
        _show_main_menu()
        return

    if _capture_state is None:
        return

    slug = _capture_state["slug"]
    name = _capture_state["name"]
    _capture_state = None

    if "voice" in msg:
        raw = transcribe_voice(TOKEN, msg["voice"]["file_id"])
    else:
        raw = text

    if not raw:
        send_message(TOKEN, CHAT_ID, "❌ Keine Idee erkannt.")
        return

    try:
        summary = _summarize_idea(raw)
    except Exception:
        summary = raw[:100]

    _append_idea(slug, summary)
    send_message(TOKEN, CHAT_ID, f"✅ Idee erfasst: {summary}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    offset = None
    print(f"Brain Bot gestartet (CHAT_ID={CHAT_ID})")
    _show_main_menu()
    while True:
        try:
            updates = get_updates(TOKEN, offset=offset)
            for upd in updates:
                offset = upd["update_id"] + 1
                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    if cq.get("from", {}).get("id") != CHAT_ID:
                        continue
                    _handle_callback(cq)
                elif "message" in upd:
                    msg = upd["message"]
                    if msg.get("chat", {}).get("id") != CHAT_ID:
                        continue
                    _handle_message(msg)
            _check_relay_question()
        except Exception as e:
            print(f"Brain Bot error: {e}", file=sys.stderr)
        time.sleep(1)


if __name__ == "__main__":
    main()

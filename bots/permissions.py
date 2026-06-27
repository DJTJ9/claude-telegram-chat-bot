import os, json, sys, time, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
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

from core.telegram import get_updates, send_message, build_inline_keyboard, answer_callback_query
from core.settings import load_settings, save_settings

TOKEN = os.environ["TOKEN_PERMISSIONS"]
CHAT_ID = int(os.environ.get("CHAT_ID", "8896609541"))
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
PORT = int(os.environ.get("PORT", "8004"))

HILFE = """🔐 Permissions Bot

/bot-notify an|aus — Benachrichtigungen ein-/ausschalten
hilfe — Diese Hilfe

Empfängt automatisch:
• Tool-Genehmigungsanfragen von Claude Code
• Claude-Stop-Notifikationen
• Fragen ohne aktive Session"""

_active_permission_id = None
_active_question_id = None


def _write_question_response(request_id, answer):
    (WORK_DIR / f"question_response_{request_id}.json").write_text(
        json.dumps({"answer": answer})
    )

def _write_permission_response(request_id, approved):
    (WORK_DIR / f"permission_response_{request_id}.json").write_text(
        json.dumps({"approved": approved})
    )

def _handle_callback(cq: dict) -> None:
    global _active_permission_id, _active_question_id
    answer_callback_query(TOKEN, cq["id"])
    data = cq.get("data", "")
    if data == "__freitext__":
        send_message(TOKEN, CHAT_ID, "Bitte Antwort eintippen:")
        return
    if _active_permission_id:
        approved = data == "approve"
        _write_permission_response(_active_permission_id, approved)
        _active_permission_id = None
        send_message(TOKEN, CHAT_ID, "✅ Genehmigt" if approved else "❌ Abgelehnt")
    elif _active_question_id:
        _write_question_response(_active_question_id, data)
        _active_question_id = None
        send_message(TOKEN, CHAT_ID, f"💬 Antwort: {data}")


def _handle_message(msg: dict) -> None:
    global _active_permission_id, _active_question_id
    text = msg.get("text", "").strip()
    if not text:
        return

    if _active_question_id:
        _write_question_response(_active_question_id, text)
        _active_question_id = None
        send_message(TOKEN, CHAT_ID, f"💬 Antwort: {text}")
        return

    if _active_permission_id:
        approved = text.lower() in ("ja", "y", "yes", "approve", "j")
        _write_permission_response(_active_permission_id, approved)
        _active_permission_id = None
        send_message(TOKEN, CHAT_ID, "✅ Genehmigt" if approved else "❌ Abgelehnt")
        return

    t = text.lower()
    if t.startswith("/bot-notify"):
        arg = text[11:].strip().lower()
        s = load_settings()
        if arg == "an":
            s["notifications_enabled"] = True
            save_settings(s)
            send_message(TOKEN, CHAT_ID, "🔔 Benachrichtigungen aktiviert")
        elif arg == "aus":
            s["notifications_enabled"] = False
            save_settings(s)
            send_message(TOKEN, CHAT_ID, "🔕 Benachrichtigungen deaktiviert")
        else:
            state = "aktiviert 🔔" if s.get("notifications_enabled", True) else "deaktiviert 🔕"
            send_message(TOKEN, CHAT_ID, f"Benachrichtigungen: {state}")
    elif t == "hilfe":
        send_message(TOKEN, CHAT_ID, HILFE)
    else:
        send_message(TOKEN, CHAT_ID, f"Unbekannt: {text}\nTippe 'hilfe'")


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
        if cq.get("from", {}).get("id") == CHAT_ID:
            _handle_callback(cq)
    elif "message" in upd:
        msg = upd["message"]
        if msg.get("chat", {}).get("id") == CHAT_ID:
            _handle_message(msg)


def _check_pending_files() -> None:
    global _active_permission_id, _active_question_id
    if not _active_permission_id:
        perm_path = WORK_DIR / "pending_permission.json"
        if perm_path.exists():
            try:
                data = json.loads(perm_path.read_text())
                perm_path.unlink()
                _active_permission_id = data["request_id"]
                tool = data.get("tool", "Unknown")
                inp = json.dumps(data.get("input", {}), ensure_ascii=False)[:200]
                kb = [[
                    {"text": "✅ Genehmigen", "callback_data": "approve"},
                    {"text": "❌ Ablehnen", "callback_data": "deny"},
                ]]
                send_message(TOKEN, CHAT_ID,
                             f"🔐 Tool-Anfrage: {tool}\n{inp}",
                             reply_markup={"inline_keyboard": kb})
            except Exception as e:
                print(f"permission file error: {e}")

    if not _active_question_id:
        q_path = WORK_DIR / "pending_question.json"
        if q_path.exists():
            try:
                data = json.loads(q_path.read_text())
                if data.get("target_bot", "permissions") == "permissions":
                    q_path.unlink()
                    _active_question_id = data["request_id"]
                    kb = build_inline_keyboard(data["question"])
                    send_message(TOKEN, CHAT_ID, f"❓ {data['question']}",
                                 reply_markup={"inline_keyboard": kb})
            except Exception as e:
                print(f"question file error: {e}")


def main():
    print(f"Permissions Bot gestartet (webhook, port {PORT}, chat_id={CHAT_ID})")

    def _file_poll():
        while True:
            try:
                _check_pending_files()
            except Exception as e:
                print(f"file poll error: {e}")
            time.sleep(1)

    threading.Thread(target=_file_poll, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), _WebhookHandler)
    server.serve_forever()

if __name__ == "__main__":
    main()

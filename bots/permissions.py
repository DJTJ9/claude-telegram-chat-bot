import os, json, sys, time
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

HILFE = """🔐 Permissions Bot

/bot-notify an|aus — Benachrichtigungen ein-/ausschalten
hilfe — Diese Hilfe

Empfängt automatisch:
• Tool-Genehmigungsanfragen von Claude Code
• Claude-Stop-Notifikationen
• Fragen ohne aktive Session"""

def _write_question_response(request_id, answer):
    (WORK_DIR / f"question_response_{request_id}.json").write_text(
        json.dumps({"answer": answer})
    )

def _write_permission_response(request_id, approved):
    (WORK_DIR / f"permission_response_{request_id}.json").write_text(
        json.dumps({"approved": approved})
    )

def main():
    offset = None
    active_permission_id = None
    active_question_id = None
    print(f"Permissions Bot gestartet (chat_id={CHAT_ID})")

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
                    data = cq.get("data", "")
                    if data == "__freitext__":
                        send_message(TOKEN, CHAT_ID, "Bitte Antwort eintippen:")
                        continue
                    if active_permission_id:
                        approved = data == "approve"
                        _write_permission_response(active_permission_id, approved)
                        active_permission_id = None
                        send_message(TOKEN, CHAT_ID, "✅ Genehmigt" if approved else "❌ Abgelehnt")
                    elif active_question_id:
                        _write_question_response(active_question_id, data)
                        active_question_id = None
                        send_message(TOKEN, CHAT_ID, f"💬 Antwort: {data}")
                    continue

                msg = upd.get("message", {})
                if not msg:
                    continue
                chat_id = msg.get("chat", {}).get("id")
                if chat_id != CHAT_ID:
                    continue
                text = msg.get("text", "").strip()
                if not text:
                    continue

                if active_question_id:
                    _write_question_response(active_question_id, text)
                    active_question_id = None
                    send_message(TOKEN, CHAT_ID, f"💬 Antwort: {text}")
                    continue

                if active_permission_id:
                    approved = text.lower() in ("ja", "y", "yes", "approve", "j")
                    _write_permission_response(active_permission_id, approved)
                    active_permission_id = None
                    send_message(TOKEN, CHAT_ID, "✅ Genehmigt" if approved else "❌ Abgelehnt")
                    continue

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

            if not active_permission_id:
                perm_path = WORK_DIR / "pending_permission.json"
                if perm_path.exists():
                    try:
                        data = json.loads(perm_path.read_text())
                        perm_path.unlink()
                        active_permission_id = data["request_id"]
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

            if not active_question_id:
                q_path = WORK_DIR / "pending_question.json"
                if q_path.exists():
                    try:
                        data = json.loads(q_path.read_text())
                        if data.get("target_bot", "permissions") == "permissions":
                            q_path.unlink()
                            active_question_id = data["request_id"]
                            kb = build_inline_keyboard(data["question"])
                            send_message(TOKEN, CHAT_ID, f"❓ {data['question']}",
                                         reply_markup={"inline_keyboard": kb})
                    except Exception as e:
                        print(f"question file error: {e}")

            time.sleep(0.3)
        except Exception as e:
            print(f"permissions bot error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

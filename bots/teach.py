import os, sys, json, re, subprocess, threading, time
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

TOKEN = os.environ["TOKEN_TEACH"]
CHAT_ID = int(os.environ.get("CHAT_ID", "8896609541"))
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
TEACH_DIR = Path(os.environ.get("TEACH_DIR", str(PROJECT_DIR.parent / "teach")))

PAGES_BASE = "https://djtj9.github.io/teach-lessons"
COURSE_NAMES = {
    "cli-notion-agent":  "Kurs: CLI Notion Agent",
    "projekt-planung":   "Kurs: Projekt-Planung",
    "python-grundlagen": "Kurs: Python Grundlagen",
}

HILFE_TEXT = """📚 Teach Bot

teach: <thema + warum> — Lernkurs erstellen oder planen
  z.B. teach: Python Grundlagen, weil ich Skripte automatisieren will
hilfe — Diese Hilfe"""

_active_question_id = None


def _write_question_response(request_id, answer):
    (WORK_DIR / f"question_response_{request_id}.json").write_text(json.dumps({"answer": answer}))


def _set_session():
    s = load_settings()
    s["active_session"] = "teach"
    s["active_session_bot"] = "teach"
    save_settings(s)


def _clear_session():
    s = load_settings()
    s["active_session"] = None
    s["active_session_bot"] = None
    save_settings(s)


def _update_index_html(lesson_path):
    parts = lesson_path.replace("\\", "/").split("/")
    if len(parts) < 3:
        return
    course_slug = parts[0]
    filename = parts[-1]
    m = re.match(r"lektion-(\d+)-", filename)
    if not m:
        return
    num = m.group(1)

    title = filename.replace(".html", "").replace("-", " ").title()
    html_file = TEACH_DIR / lesson_path.replace("/", os.sep)
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

    index_path = TEACH_DIR / "index.html"
    with open(index_path, encoding="utf-8") as f:
        content = f.read()

    h2_pos = content.find(f"<h2>{section_header}</h2>")
    if h2_pos == -1:
        return
    if href in content:
        return
    ul_close = content.find("</ul>", h2_pos)
    if ul_close == -1:
        return
    content = content[:ul_close] + new_li + content[ul_close:]

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)


def publish_new_lessons():
    try:
        result = subprocess.run(
            ["git", "-C", str(TEACH_DIR), "status", "--porcelain"],
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
        subprocess.run(["git", "-C", str(TEACH_DIR), "add", "."], capture_output=True)
        names = ", ".join(os.path.basename(p) for p in new_lessons)
        subprocess.run(
            ["git", "-C", str(TEACH_DIR), "commit", "-m", f"Add lesson: {names}"],
            capture_output=True, text=True, encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(TEACH_DIR), "push"], capture_output=True)
        urls = "\n".join(f"{PAGES_BASE}/{p}" for p in new_lessons)
        send_message(TOKEN, CHAT_ID, f"📚 Neue Lektion verfügbar:\n{urls}")
    except Exception as e:
        print(f"publish_new_lessons error: {e}")


def _run_teach(topic):
    _set_session()
    safe_topic = topic[:500]
    telegram_ask_path = WORK_DIR / "scripts" / "telegram_ask.py"
    prompt = (
        f"Invoke the /teach skill. "
        f"Topic and context from user: {safe_topic}. "
        f'Use python "{telegram_ask_path}" for ALL questions '
        f"(notifications_enabled is true — do not output anything to terminal)."
    )
    cmd = ["claude", "--dangerously-skip-permissions", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            timeout=3600, cwd=str(TEACH_DIR.parent), env=env
        )
        if result.returncode == 0:
            send_message(TOKEN, CHAT_ID, "✅ Teach-Session abgeschlossen")
            publish_new_lessons()
        else:
            send_message(TOKEN, CHAT_ID, f"❌ Teach-Session fehlgeschlagen\n{(result.stderr or '')[-300:]}")
    except subprocess.TimeoutExpired:
        send_message(TOKEN, CHAT_ID, "❌ Teach-Timeout (1h überschritten)")
    finally:
        _clear_session()


def main():
    global _active_question_id

    offset = None
    print(f"Teach Bot gestartet (chat_id={CHAT_ID})")

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
                    elif _active_question_id:
                        _write_question_response(_active_question_id, data)
                        _active_question_id = None
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

                if _active_question_id:
                    _write_question_response(_active_question_id, text)
                    _active_question_id = None
                    send_message(TOKEN, CHAT_ID, f"💬 Antwort: {text}")
                    continue

                t = text.lower()

                if t.startswith("/teach") or t.startswith("teach:"):
                    topic = text.split(":", 1)[1].strip() if ":" in text else text[6:].strip()
                    if not topic:
                        send_message(TOKEN, CHAT_ID,
                            "Nutzung: teach: <thema + warum>\nz.B. teach: Python Grundlagen, weil ich Skripte automatisieren will")
                    else:
                        send_message(TOKEN, CHAT_ID, "📚 Teach-Session gestartet — Fragen kommen gleich über den Chat")
                        threading.Thread(target=_run_teach, args=(topic,), daemon=True).start()
                elif t == "hilfe":
                    send_message(TOKEN, CHAT_ID, HILFE_TEXT)
                else:
                    send_message(TOKEN, CHAT_ID, f"Unbekannt: {text}\nTippe 'hilfe'")

            q_path = WORK_DIR / "pending_question.json"
            if not _active_question_id and q_path.exists():
                try:
                    data = json.loads(q_path.read_text())
                    if data.get("target_bot", "permissions") == "teach":
                        q_path.unlink()
                        _active_question_id = data["request_id"]
                        kb = build_inline_keyboard(data["question"])
                        send_message(TOKEN, CHAT_ID, f"❓ {data['question']}",
                                     reply_markup={"inline_keyboard": kb})
                except Exception as e:
                    print(f"question file error: {e}")

            time.sleep(0.3)
        except Exception as e:
            print(f"teach bot error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()

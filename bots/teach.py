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

from core.telegram import get_updates, send_message, build_inline_keyboard, answer_callback_query, transcribe_voice, normalize_voice
from core.settings import load_settings, save_settings

TOKEN = os.environ["TOKEN_TEACH"]
CHAT_ID = int(os.environ.get("CHAT_ID", "8896609541"))
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
TEACH_DIR = Path(os.environ.get("TEACH_DIR", str(PROJECT_DIR.parent / "teach")))

PAGES_BASE = "https://djtj9.github.io/teach-lessons"
ABORT_SIGNAL = WORK_DIR / ".teach_abort"

HILFE_TEXT = """📚 Teach Bot

Schreib einfach was du lernen willst — z.B.:
  "Python lernen, weil ich Skripte schreiben will"
  "SQL Grundlagen für Datenbankabfragen"

lessons: — Alle Lernthemen anzeigen
hilfe    — Diese Hilfe"""


def _lesson_title_from_filename(filename: str) -> str:
    name = filename.replace(".html", "")
    name = re.sub(r"^lektion-\d+-", "", name)
    name = re.sub(r"^\d+-", "", name)
    return name.replace("-", " ").title()


def _get_topics(teach_dir=None) -> list:
    base = teach_dir or TEACH_DIR
    topics = []
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        lessons_dir = d / "lessons"
        if not lessons_dir.exists():
            continue
        if not any(lessons_dir.glob("*.html")):
            continue
        slug = d.name
        label = slug.replace("-", " ").title()
        topics.append((slug, label))
    return topics


def _build_lessons_keyboard(topics: list) -> list:
    rows = []
    for i in range(0, len(topics), 2):
        row = [
            {"text": label, "callback_data": f"lessons__{slug}"}
            for slug, label in topics[i:i + 2]
        ]
        rows.append(row)
    return rows


def _send_lesson_list(slug: str, teach_dir=None) -> None:
    base = teach_dir or TEACH_DIR
    label = slug.replace("-", " ").title()
    lessons_dir = base / slug / "lessons"
    files = sorted(f.name for f in lessons_dir.glob("*.html"))
    if not files:
        send_message(TOKEN, CHAT_ID, f"Keine Lektionen für {label} gefunden.")
        return
    buttons = []
    for i, fname in enumerate(files, 1):
        title = _lesson_title_from_filename(fname)
        url = f"{PAGES_BASE}/{slug}/lessons/{fname}"
        buttons.append([{"text": f"{i}. {title}", "url": url}])
    send_message(
        TOKEN, CHAT_ID,
        f"📚 {label} — {len(files)} Lektionen:",
        reply_markup={"inline_keyboard": buttons},
    )


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


def _update_index_html(lesson_path, teach_dir=None):
    base = teach_dir or TEACH_DIR
    parts = lesson_path.replace("\\", "/").split("/")
    if len(parts) < 3:
        return
    course_slug = parts[0]
    filename = parts[-1]
    m = re.match(r"lektion-(\d+)-", filename)
    if not m:
        return
    num = m.group(1)

    display_name = course_slug.replace("-", " ").title()
    title = display_name
    html_file = base / lesson_path.replace("/", os.sep)
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

    index_path = base / "index.html"
    with open(index_path, encoding="utf-8") as f:
        content = f.read()

    if href in content:
        return

    h2_tag = f"<h2>{display_name}</h2>"
    h2_pos = content.find(h2_tag)
    if h2_pos == -1:
        new_section = f"\n<h2>{display_name}</h2>\n<ul>\n</ul>\n"
        content = content.replace("</body>", new_section + "</body>")
        h2_pos = content.find(h2_tag)

    ul_close = content.find("</ul>", h2_pos)
    if ul_close == -1:
        return
    content = content[:ul_close] + new_li + content[ul_close:]

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)


def _inject_lesson_navigation(course_slug, teach_dir=None):
    base = teach_dir or TEACH_DIR
    lessons_dir = base / course_slug / "lessons"
    files = sorted(f.name for f in lessons_dir.glob("*.html"))
    if not files:
        return
    for i, fname in enumerate(files):
        fpath = lessons_dir / fname
        try:
            content = fpath.read_text(encoding="utf-8")
        except Exception:
            continue
        if "<footer>" not in content:
            continue
        parts = []
        if i > 0:
            parts.append(f'<a href="{files[i-1]}">← Lektion {i}</a>')
        if i < len(files) - 1:
            parts.append(f'<a href="{files[i+1]}">Weiter: Lektion {i+2} →</a>')
        else:
            parts.append("✅ Kurs abgeschlossen")
        new_footer = f'<footer>{" &nbsp;|&nbsp; ".join(parts)}</footer>'
        content = re.sub(r"<footer>.*?</footer>", new_footer, content, flags=re.DOTALL)
        fpath.write_text(content, encoding="utf-8")


def publish_new_lessons() -> int:
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
            return 0
        for p in new_lessons:
            _update_index_html(p)
        course_slugs = {p.split("/")[0] for p in new_lessons}
        for slug in course_slugs:
            _inject_lesson_navigation(slug)
        subprocess.run(["git", "-C", str(TEACH_DIR), "add", "."], capture_output=True)
        names = ", ".join(os.path.basename(p) for p in new_lessons)
        subprocess.run(
            ["git", "-C", str(TEACH_DIR), "commit", "-m", f"Add lesson: {names}"],
            capture_output=True, text=True, encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(TEACH_DIR), "push"], capture_output=True)
        return len(new_lessons)
    except Exception as e:
        print(f"publish_new_lessons error: {e}")
        return 0


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

    kb = [[{"text": "🛑 Abbrechen", "callback_data": "teach_abort"}]]
    send_message(TOKEN, CHAT_ID,
                 "📚 Teach-Session gestartet — Fragen kommen gleich über den Chat",
                 reply_markup={"inline_keyboard": kb})

    aborted = False
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=str(TEACH_DIR.parent), env=env
        )

        def _monitor():
            nonlocal aborted
            while proc.poll() is None:
                if ABORT_SIGNAL.exists():
                    ABORT_SIGNAL.unlink(missing_ok=True)
                    proc.terminate()
                    aborted = True
                    return
                time.sleep(2)

        t = threading.Thread(target=_monitor, daemon=True)
        t.start()

        try:
            _, stderr = proc.communicate(timeout=3600)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, stderr = proc.communicate()
            send_message(TOKEN, CHAT_ID, "❌ Teach-Timeout (1h überschritten)")
            return
        finally:
            t.join(timeout=3)

        count = publish_new_lessons()

        if aborted:
            send_message(TOKEN, CHAT_ID,
                         f"🛑 Abgebrochen — {count} Lektion(en) gespeichert — tippe 'lessons' zum Öffnen")
        elif proc.returncode == 0:
            send_message(TOKEN, CHAT_ID,
                         f"✅ {count} Lektion(en) erstellt — tippe 'lessons' zum Öffnen")
        else:
            send_message(TOKEN, CHAT_ID,
                         f"❌ Teach-Session fehlgeschlagen\n{(stderr or '')[-300:]}")
    except Exception as e:
        send_message(TOKEN, CHAT_ID, f"❌ Fehler: {e}")
    finally:
        ABORT_SIGNAL.unlink(missing_ok=True)
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
                    if data.startswith("lessons__"):
                        _send_lesson_list(data[9:])
                    elif data == "teach_abort":
                        (WORK_DIR / ".teach_abort").write_text("")
                        send_message(TOKEN, CHAT_ID, "⏳ Abbruch wird nach aktueller Lektion wirksam...")
                    elif data == "__freitext__":
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
                if not text and "voice" in msg:
                    try:
                        raw = transcribe_voice(TOKEN, msg["voice"]["file_id"])
                        text = normalize_voice(raw)
                        send_message(TOKEN, CHAT_ID, f"🎤 {text}")
                    except Exception as e:
                        send_message(TOKEN, CHAT_ID, f"❌ Spracherkennung fehlgeschlagen: {e}")
                        continue
                if not text:
                    continue

                if _active_question_id:
                    _write_question_response(_active_question_id, text)
                    _active_question_id = None
                    send_message(TOKEN, CHAT_ID, f"💬 Antwort: {text}")
                    continue

                t = text.lower()

                if t.startswith("/lessons") or t.startswith("lessons:") or t == "lessons":
                    topics = _get_topics()
                    if not topics:
                        send_message(TOKEN, CHAT_ID, "Noch keine Lektionen vorhanden.")
                    else:
                        kb = _build_lessons_keyboard(topics)
                        send_message(TOKEN, CHAT_ID, "📚 Welches Thema?",
                                     reply_markup={"inline_keyboard": kb})
                elif t == "hilfe":
                    send_message(TOKEN, CHAT_ID, HILFE_TEXT)
                else:
                    threading.Thread(target=_run_teach, args=(text,), daemon=True).start()

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

import os, sys, json, time, subprocess, threading
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

from core.telegram import (
    get_updates, send_message, answer_callback_query,
    edit_message, transcribe_voice,
)
from core.settings import load_settings, save_settings
from core import nocodb_direct

TOKEN = os.environ["TOKEN_BRAIN"]
CHAT_ID = int(os.environ.get("CHAT_ID", "0"))
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
HUB_DIR = Path(os.environ.get("HUB_DIR", str(WORK_DIR)))
PORT = int(os.environ.get("PORT", "8001"))

_accordion_msg_id: int | None = None
_capture_state: dict | None = None
_impl_state: dict | None = None
_bug_state: dict | None = None


# ── Webhook server ───────────────────────────────────────────────────────────

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


# ── Wait-Notify (Session wartet auf Terminal-Input) ──────────────────────────

_wait_notified: dict[str, float] = {}


def _check_wait_notify() -> None:
    for path in sorted(WORK_DIR.glob("pending_wait_*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        session_id = path.stem[len("pending_wait_"):]
        ts = data.get("timestamp", 0)
        if _wait_notified.get(session_id) == ts:
            continue
        _wait_notified[session_id] = ts
        slug = data.get("slug", "?")
        _, phase = _get_dev_status(slug)
        suffix = f" ({phase})" if phase else ""
        send_message(
            TOKEN, CHAT_ID,
            f"⏳ dev-Session {slug}{suffix} wartet auf Antwort",
        )


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


def _get_dev_status_full(slug: str) -> str:
    path = HUB_DIR / "topics" / slug / "STATUS.md"
    try:
        content = path.read_text()
    except FileNotFoundError:
        return "❌ STATUS.md nicht gefunden"

    active = phase = ""
    roadmap_items: list[dict] = []
    in_roadmap = False

    for line in content.splitlines():
        if line.startswith("Active:"):
            active = line.split(":", 1)[1].strip()
        elif line.startswith("Phase:"):
            phase = line.split(":", 1)[1].strip()
        elif line.startswith("## Roadmap"):
            in_roadmap = True
        elif in_roadmap and line.startswith("- ["):
            close = line.index("]")
            tag = line[3:close]
            name = line[close + 1:].strip()
            roadmap_items.append({"tag": tag, "name": name})

    epics: dict[str, dict] = {}
    for item in roadmap_items:
        prefix = item["name"].split(":")[0].strip() if ":" in item["name"] else "(Sonstige)"
        if prefix not in epics:
            epics[prefix] = {"open": 0, "done": 0}
        if item["tag"] == "done":
            epics[prefix]["done"] += 1
        else:
            epics[prefix]["open"] += 1

    next_items = [i["name"] for i in roadmap_items if i["tag"] != "done"][:5]
    total_open = sum(e["open"] for e in epics.values())
    total_done = sum(e["done"] for e in epics.values())

    proj_name = slug.replace("-", " ").title()
    out = [f"📊 Dev Status — {proj_name}", ""]
    out.append(f"▶ Aktiv: {active} ({phase})" if active else "▶ Aktiv: (kein aktives Feature)")
    out.append("")
    out.append("━━ Epics ━━")
    for epic, counts in epics.items():
        out.append(f"🔷 {epic:<18} {counts['open']} offen · {counts['done']} done")
    out.append("")
    if next_items:
        out.append("⏭ Nächste 5:")
        for i, name in enumerate(next_items, 1):
            out.append(f"{i}. {name}")
        out.append("")
    out.append(f"📈 Gesamt: {total_open} offen · {total_done} done")
    return "\n".join(out)


def _get_planned_items(slug: str) -> list[dict]:
    path = HUB_DIR / "topics" / slug / "STATUS.md"
    try:
        content = path.read_text()
    except FileNotFoundError:
        return []
    items, in_roadmap = [], False
    for line in content.splitlines():
        if line.startswith("## Roadmap"):
            in_roadmap = True
            continue
        if in_roadmap and "- [planned]" in line:
            name = line.split("[planned]", 1)[1].strip()
            name_kebab = name.lower().replace(" ", "-")
            plan_path = None
            plans_dir = HUB_DIR / "topics" / slug / "plans"
            if plans_dir.exists():
                for f in sorted(plans_dir.glob("*.md"), reverse=True):
                    if any(w in f.name for w in name_kebab.split("-")[:3] if len(w) > 3):
                        plan_path = f"topics/{slug}/plans/{f.name}"
                        break
            items.append({"name": name, "plan_path": plan_path})
    return items


def _schedule_plan(slug: str, plan_name: str, plan_path: str, time_str: str) -> None:
    from datetime import datetime, timedelta
    if time_str.lower() == "jetzt":
        t = datetime.now() + timedelta(minutes=1)
        scheduled_time = t.strftime("%H:%M")
    else:
        scheduled_time = time_str.strip()
    plan_slug = Path(plan_path).stem.lstrip("0123456789-")
    plans_file = HUB_DIR / "scheduled_plans.json"
    try:
        plans = json.loads(plans_file.read_text())
    except Exception:
        plans = []
    plans.append({
        "slug": plan_slug,
        "plan_path": plan_path,
        "scheduled_time": scheduled_time,
        "status": "pending",
        "project_slug": slug,
    })
    plans_file.write_text(json.dumps(plans, indent=2))
    subprocess.run(["git", "-C", str(HUB_DIR), "add", "scheduled_plans.json"],
                   capture_output=True)
    subprocess.run(["git", "-C", str(HUB_DIR), "commit", "-m",
                    f"chore({slug}): schedule plan {plan_slug} at {scheduled_time}"],
                   capture_output=True)


def _handle_impl_time_input(text: str) -> None:
    global _impl_state
    if not _impl_state or _impl_state.get("step") != "await_time":
        return
    slug = _impl_state["slug"]
    plan_name = _impl_state["plan_name"]
    plan_path = _impl_state["plan_path"]
    _impl_state = None
    _schedule_plan(slug, plan_name, plan_path, text.strip())
    send_message(TOKEN, CHAT_ID, f"✅ Plan '{plan_name}' geplant für {text.strip()}")


def _build_main_keyboard(projects: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for p in projects:
        rows.append([{"text": f"📁 {p['name']}", "callback_data": f"proj:{p['slug']}"}])
    return rows


def _setup_reply_keyboard() -> None:
    send_message(TOKEN, CHAT_ID, "🤖", reply_markup={
        "keyboard": [["🤖"]],
        "resize_keyboard": True,
        "is_persistent": True,
    })


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


def _handle_callback(cq: dict) -> None:
    global _capture_state, _impl_state, _bug_state
    cq_id = cq["id"]
    data = cq.get("data", "")

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
            [{"text": "🐛 Bug festhalten", "callback_data": f"bug:{slug}"}],
            [{"text": "← Zurück", "callback_data": "back"}],
        ]
        if _accordion_msg_id:
            edit_message(TOKEN, CHAT_ID, _accordion_msg_id,
                         f"📁 {proj['name']}\n{status_text}",
                         reply_markup={"inline_keyboard": sub_keyboard})
        answer_callback_query(TOKEN, cq_id)

    elif data.startswith("status:"):
        slug = data[7:]
        status_text = _get_dev_status_full(slug)
        send_message(TOKEN, CHAT_ID, status_text)
        answer_callback_query(TOKEN, cq_id, text="📊 Status geladen")

    elif data.startswith("capture:"):
        slug = data[8:]
        projects = _load_projects()
        proj = next((p for p in projects if p["slug"] == slug), {"name": slug})
        _capture_state = {"slug": slug, "name": proj["name"]}
        send_message(TOKEN, CHAT_ID,
                     f"💡 Schreib oder sprich deine Idee für {proj['name']}:")
        answer_callback_query(TOKEN, cq_id)

    elif data.startswith("bug:"):
        slug = data[4:]
        _bug_state = {"slug": slug}
        send_message(TOKEN, CHAT_ID, "🐛 Beschreibe den Bug — Freitext oder Sprachnachricht:")
        answer_callback_query(TOKEN, cq_id)

    elif data.startswith("bug_save:"):
        slug = data[9:]
        if not _bug_state or "pending" not in _bug_state:
            answer_callback_query(TOKEN, cq_id, text="❌ Kein Bug pending")
            return
        pending = _bug_state["pending"]
        title = pending["title"]
        _bug_state = None
        _append_bug_to_status_md(slug, title)
        subprocess.run(
            ["python", str(WORK_DIR / "scripts" / "nocodb_sync.py"),
             "--direction", "dev-to-nocodb",
             "--slug", slug,
             "--feature", title,
             "--status", "bug",
             "--insert-position", "top"],
            capture_output=True,
        )
        answer_callback_query(TOKEN, cq_id, text="🐛 Bug gespeichert!")

    elif data == "bug_cancel":
        _bug_state = None
        answer_callback_query(TOKEN, cq_id, text="❌ Abgebrochen")

    elif data.startswith("impl:"):
        slug = data[5:]
        items = _get_planned_items(slug)
        if not items:
            answer_callback_query(TOKEN, cq_id, text="Keine [planned]-Pläne vorhanden")
            return
        _impl_state = {"step": "select_plan", "slug": slug, "plans": items}
        rows = [
            [{"text": f"📋 {it['name']}", "callback_data": f"impl_select:{i}"}]
            for i, it in enumerate(items)
        ]
        rows.append([{"text": "← Zurück", "callback_data": f"proj:{slug}"}])
        if _accordion_msg_id:
            edit_message(TOKEN, CHAT_ID, _accordion_msg_id, "Welchen Plan umsetzen?",
                         reply_markup={"inline_keyboard": rows})
        answer_callback_query(TOKEN, cq_id)

    elif data.startswith("impl_select:"):
        if not _impl_state or _impl_state.get("step") != "select_plan":
            answer_callback_query(TOKEN, cq_id)
            return
        idx = int(data[12:])
        plans_list = _impl_state["plans"]
        if idx >= len(plans_list):
            answer_callback_query(TOKEN, cq_id, text="Ungültiger Plan")
            return
        chosen = plans_list[idx]
        _impl_state = {
            "step": "await_time",
            "slug": _impl_state["slug"],
            "plan_name": chosen["name"],
            "plan_path": chosen["plan_path"],
        }
        send_message(TOKEN, CHAT_ID,
                     f"⏰ Wann soll '{chosen['name']}' umgesetzt werden?\n"
                     "HH:MM eingeben oder 'jetzt':")
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


def _run_bug_summary(description: str) -> dict:
    response = _groq_client().chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{
            "role": "user",
            "content": (
                "Erstelle aus dieser Bug-Beschreibung einen kurzen Titel (max 60 Zeichen) "
                "und eine kompakte Beschreibung (2-3 Sätze).\n\n"
                "Format:\nTITEL: <titel>\nBESCHREIBUNG: <beschreibung>\n\n"
                f"Bug-Beschreibung: {description}"
            ),
        }],
    )
    text = response.choices[0].message.content.strip()
    title = summary = ""
    for line in text.splitlines():
        if line.startswith("TITEL:"):
            title = "Bug: " + line[6:].strip()
        elif line.startswith("BESCHREIBUNG:"):
            summary = line[13:].strip()
        elif summary and line.strip():
            summary += " " + line.strip()
    if not title:
        title = "Bug: " + description[:50]
    if not summary:
        summary = description
    return {"title": title, "summary": summary}


def _append_idea(slug: str, summary: str) -> None:
    idea_line = f"- [idea]      {summary}\n"
    for filename in ("STATUS.md", "VISION.md"):
        path = HUB_DIR / "topics" / slug / filename
        if path.exists():
            with open(path, "a") as f:
                f.write(idea_line)


def _append_bug_to_status_md(slug: str, title: str) -> None:
    path = HUB_DIR / "topics" / slug / "STATUS.md"
    if path.exists():
        with open(path, "a") as f:
            f.write(f"- [idea]      {title}\n")


def _handle_message(msg: dict) -> None:
    global _capture_state, _impl_state, _bug_state, _accordion_msg_id
    text = msg.get("text", "")

    if text in ("/start", "🤖"):
        _accordion_msg_id = None
        _setup_reply_keyboard()
        _show_main_menu()
        return

    if _impl_state and _impl_state.get("step") == "await_time":
        _handle_impl_time_input(text)
        return

    if _bug_state is not None and "pending" not in _bug_state:
        slug = _bug_state["slug"]
        if "voice" in msg:
            raw = transcribe_voice(TOKEN, msg["voice"]["file_id"])
        else:
            raw = text
        if not raw:
            send_message(TOKEN, CHAT_ID, "❌ Keine Beschreibung erkannt.")
            _bug_state = None
            return
        try:
            result = _run_bug_summary(raw)
        except Exception:
            result = {"title": "Bug: " + raw[:50], "summary": raw}
        _bug_state["pending"] = result
        confirm_text = (
            f"🐛 Bug erkannt:\n{result['title']}\n\n{result['summary']}\n\nAlles korrekt?"
        )
        send_message(TOKEN, CHAT_ID, confirm_text, reply_markup={
            "inline_keyboard": [[
                {"text": "✅ Speichern", "callback_data": f"bug_save:{slug}"},
                {"text": "❌ Abbrechen", "callback_data": "bug_cancel"},
            ]]
        })
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
    try:
        nocodb_direct.add_idea(summary)
    except Exception:
        pass


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), _WebhookHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Brain Bot gestartet (webhook, port {PORT}, CHAT_ID={CHAT_ID})")
    _setup_reply_keyboard()
    _show_main_menu()
    while True:
        try:
            _check_wait_notify()
        except Exception as e:
            print(f"wait-notify error: {e}", file=sys.stderr)
        time.sleep(0.1)


if __name__ == "__main__":
    main()

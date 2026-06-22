import os, sys, json, re, subprocess, threading, time, signal
from datetime import date
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

from core.telegram import get_updates, send_message, build_inline_keyboard, answer_callback_query, edit_message_keyboard, transcribe_voice, normalize_voice
from core.settings import load_settings, save_settings
from core.state import load_registry, save_registry, load_plans
from core import session_manager

TOKEN = os.environ["TOKEN_BRAIN"]
CHAT_ID = int(os.environ.get("CHAT_ID", "8896609541"))
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
HUB_DIR = Path(os.environ.get("HUB_DIR", str(WORK_DIR)))

HILFE_TEXT = """🧠 Brain Bot

brainstorming: <idee> — Feature brainstormen
brainstorming: <idee>, basis: <slug> — Mit vorheriger Spec als Kontext
vision: <slug> — Vision-Session für Projekt starten
vision:end — Laufende Vision-Session beenden
projekte — Alle Projekte anzeigen / anlegen
/specs — Alle vorhandenen Specs anzeigen
hilfe — Diese Hilfe"""

_pending_new_project: dict = {}
_active_question_id = None
_proj_msg_id: dict = {}  # chat_id → message_id of last project list message


def _set_session(session_type):
    s = load_settings()
    s["active_session"] = session_type
    s["active_session_bot"] = "brain"
    save_settings(s)


def _clear_session():
    s = load_settings()
    s["active_session"] = None
    s["active_session_bot"] = None
    save_settings(s)


def _write_question_response(request_id, answer):
    (WORK_DIR / f"question_response_{request_id}.json").write_text(json.dumps({"answer": answer}))


def _format_specs():
    topics_dir = HUB_DIR / "topics"
    if not topics_dir.exists():
        return "Keine Specs gefunden."
    specs = sorted(topics_dir.glob("*/specs/*.md"))
    if not specs:
        return "Keine Specs gefunden."
    lines = [f"📄 Specs ({len(specs)}):"]
    for s in specs:
        parts = s.relative_to(topics_dir).parts
        slug = parts[0]
        filename = parts[-1]
        lines.append(f"• [{slug}] {filename}")
    return "\n".join(lines)


def _format_plans_for_slug(slug):
    plans_dir = HUB_DIR / "topics" / slug / "plans"
    if not plans_dir.exists():
        return f"Keine Pläne für {slug}."
    files = sorted(plans_dir.glob("*.md"))
    if not files:
        return f"Keine Pläne für {slug}."
    scheduled = {p["slug"]: p for p in load_plans()}
    lines = [f"📋 Pläne für {slug}:"]
    for f in files:
        derived = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", f.stem)
        status_info = f" [{scheduled[derived]['status']}]" if derived in scheduled else ""
        lines.append(f"• {f.name}{status_info}")
    return "\n".join(lines)


def _parse_backlog(slug):
    vision_path = HUB_DIR / "topics" / slug / "VISION.md"
    if not vision_path.exists():
        return []
    in_section = False
    features = []
    for line in vision_path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^## (features|backlog)", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("- [ ] "):
            raw = line[6:].strip()
            meta_match = re.search(r"<!--\s*prio:(\d+)(?:\s+deps:([\w,\-]+))?\s*-->", raw)
            title = re.sub(r"\s*<!--.*?-->", "", raw).strip()
            prio = int(meta_match.group(1)) if meta_match else 99
            deps = meta_match.group(2).split(",") if (meta_match and meta_match.group(2)) else []
            features.append({"title": title, "prio": prio, "deps": deps})
    features.sort(key=lambda f: f["prio"])
    return features


def _mark_feature_done(slug, feature_text):
    vision_path = HUB_DIR / "topics" / slug / "VISION.md"
    if not vision_path.exists():
        return
    today = date.today().isoformat()
    content = vision_path.read_text(encoding="utf-8")
    vision_path.write_text(
        content.replace(f"- [ ] {feature_text}", f"- [x] {feature_text} (geplant {today})", 1),
        encoding="utf-8",
    )


def _project_list_keyboard():
    registry = load_registry()
    buttons = []
    for proj in registry:
        buttons.append([{"text": proj["name"], "callback_data": f"proj_sel:{proj['slug']}"}])
    buttons.append([{"text": "➕ Neues Projekt", "callback_data": "new_proj"}])
    return buttons


def _run_vision(slug):
    _set_session("vision")
    registry = load_registry()
    proj = next((p for p in registry if p["slug"] == slug),
                {"slug": slug, "name": slug, "path": "", "repo": ""})
    hub_path = HUB_DIR / "topics" / slug
    hub_path.mkdir(parents=True, exist_ok=True)
    vision_path = hub_path / "VISION.md"
    telegram_ask_path = WORK_DIR / "scripts" / "telegram_ask.py"
    vision_note = (
        f"Read {vision_path} first — it exists. Append/refine sections, do NOT overwrite entirely."
        if vision_path.exists() else
        f"Create {vision_path} with this structure:\n"
        f"# {proj['name']} — Vision\n\n## Ziel\n\n"
        f"## Features (Backlog — priorisiert)\n- [ ] ...\n\n"
        f"## Architektur\n\n## Offene Fragen\n\n## Entscheidungen\n"
    )
    code_note = (
        f"Project code is at {proj['path']} — read its structure for architecture context."
        if proj.get("path") and Path(proj["path"]).exists() else ""
    )
    registry_json = json.dumps(registry, ensure_ascii=False)
    prompt = (
        f"You are running a project vision session for: {proj['name']} (slug: {slug}). "
        f"You have full tool access: write files, run Bash commands including git. "
        f"Project registry (all known projects for cross-reference): {registry_json}. "
        f"{code_note} "
        f"{vision_note} "
        f"Through dialogue, explore: project goal, required features (ordered by dependency), "
        f"architecture decisions, open questions. Ask one question at a time via: "
        f'python "{telegram_ask_path}" "your question here". '
        f"If any telegram_ask.py call returns exactly 'vision:end': stop asking questions immediately. "
        f"Write/update {vision_path} with all discussed content. "
        f"Then: git -C {HUB_DIR} add -A && git -C {HUB_DIR} commit -m \"vision: update {slug}\" && git -C {HUB_DIR} push. "
        f"Then exit. "
        f"When you have covered goal, top features, architecture, and open questions: "
        f"ask via telegram_ask.py: 'Soll ich die Vision-Session jetzt abschließen? (ja / vision:end / weiter)'. "
        f"On 'ja' or 'vision:end': write VISION.md and commit. On 'weiter': continue exploring. "
        f"When writing {vision_path}, always include/update these two sections: "
        f"'## Letzter Stand' with today's date, summary of topics discussed, and priorities for next session. "
        f"'## Confidence-Scores' as a markdown table: "
        f"| Position | Bestätigungen | Anzweiflungen | Bewertung | "
        f"Fill based on how often each architectural decision was confirmed vs. questioned in the dialogue. "
        f"Use 🟢 hoch / 🟡 mittel / 🔴 niedrig."
    )
    cmd = ["claude", "--allowedTools", "Bash,Read,Write,Edit,Grep,Glob", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", cwd=str(hub_path), env=env)
        session_manager.save_session("vision", slug, proc.pid)
        stdout, stderr = proc.communicate(timeout=3600)
        if proc.returncode == 0:
            send_message(TOKEN, CHAT_ID, f"🔭 Vision-Session für {proj['name']} abgeschlossen")
        else:
            send_message(TOKEN, CHAT_ID, f"❌ Vision-Session fehlgeschlagen\n{(stderr or '')[-300:]}")
    except subprocess.TimeoutExpired:
        proc.kill()
        send_message(TOKEN, CHAT_ID, "❌ Vision-Timeout (1h überschritten)")
    finally:
        session_manager.clear_session()
        _clear_session()


def _create_project_entry(slug, name, path):
    registry = load_registry()
    if not any(p["slug"] == slug for p in registry):
        registry.append({"slug": slug, "name": name, "path": path or "", "repo": "", "description": ""})
        save_registry(registry)
        subprocess.run(["git", "-C", str(HUB_DIR), "add", "projects-registry.json"], capture_output=True)
        subprocess.run(["git", "-C", str(HUB_DIR), "commit", "-m", f"chore: add project {slug}"], capture_output=True)
    topic_dir = HUB_DIR / "topics" / slug
    (topic_dir / "specs").mkdir(parents=True, exist_ok=True)
    (topic_dir / "plans").mkdir(parents=True, exist_ok=True)
    send_message(TOKEN, CHAT_ID, f"✅ Projekt {name} angelegt. Starte Vision-Session...")
    threading.Thread(target=_run_vision, args=(slug,), daemon=True).start()


def _run_brainstorming(topic, basis_slug=None, project_slug=None):
    _set_session("brainstorming")
    safe_topic = topic[:500]
    telegram_ask_path = WORK_DIR / "scripts" / "telegram_ask.py"

    if project_slug:
        registry = load_registry()
        proj = next((p for p in registry if p["slug"] == project_slug),
                    {"slug": project_slug, "name": project_slug, "path": "", "repo": ""})
        hub_path = HUB_DIR / "topics" / project_slug
        hub_path.mkdir(parents=True, exist_ok=True)
        vision_path = hub_path / "VISION.md"
        prior_specs = sorted((hub_path / "specs").glob("*.md")) if (hub_path / "specs").exists() else []
        registry_json = json.dumps(registry, ensure_ascii=False)
        proj_path = proj.get("path", "")
        vision_note = (f"Read {vision_path} for project context, architecture, and feature backlog."
                       if vision_path.exists() else "")
        specs_note = (f"Prior specs for cross-session context: {', '.join(str(s) for s in prior_specs[-3:])}"
                      if prior_specs else "")
        push_proj = (
            f"git -C {proj_path!r} add -A && "
            f"git -C {proj_path!r} commit -m \"feat: {safe_topic[:40]}\" && "
            f"git -C {proj_path!r} push"
            if proj_path else ""
        )
        post_impl = (
            f"After successful implementation:\n"
            f"1. In {vision_path}, change '- [ ] {safe_topic}' to "
            f"'- [x] {safe_topic} (implementiert {date.today().isoformat()})'.\n"
            f"2. git -C {HUB_DIR} add -A && git -C {HUB_DIR} commit -m "
            f"\"chore: {project_slug} after {safe_topic[:30]}\" && git -C {HUB_DIR} push\n"
            f"3. {push_proj}"
        )
        prompt = (
            f"Invoke the superpowers:brainstorming skill. "
            f"Project: {proj['name']} (slug: {project_slug}). "
            f"Feature to brainstorm: {safe_topic}. "
            f"Project registry: {registry_json}. "
            f"{vision_note} {specs_note} "
            f"Save spec to {hub_path}/specs/YYYY-MM-DD-<topic>-design.md. "
            f"Save plan to {hub_path}/plans/YYYY-MM-DD-<topic>.md. "
            f'Use python "{telegram_ask_path}" for ALL questions and gate decisions. '
            f"{post_impl}"
        )
        exec_cwd = str(hub_path)
    else:
        vision_path = WORK_DIR / "VISION.md"
        vision_note = (
            f"Read {vision_path} first for existing project context and backlog."
            if vision_path.exists() else ""
        )
        basis_note = (
            f"Also read the spec file in docs/superpowers/specs/ whose name contains '{basis_slug}' "
            f"as prior session context before starting brainstorming."
            if basis_slug else ""
        )
        prompt = (
            f"Invoke the superpowers:brainstorming skill. "
            f"Feature idea from user: {safe_topic}. "
            f"{vision_note} {basis_note}"
            f'Use python "{telegram_ask_path}" for ALL questions and gate decisions '
            f"(notifications_enabled is true — do not output anything to terminal). "
            f"After the spec and plan are written and committed, update VISION.md in {WORK_DIR}: "
            f"add the new feature under Implementiert, move any collected-but-not-chosen ideas to Backlog, "
            f"record key decisions under Entscheidungen."
        )
        exec_cwd = str(WORK_DIR)

    cmd = ["claude", "--allowedTools", "Bash,Read,Write,Edit,Grep,Glob", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", cwd=exec_cwd, env=env)
        session_manager.save_session("brainstorming", project_slug or "general", proc.pid)
        stdout, stderr = proc.communicate(timeout=7200)
        if proc.returncode == 0:
            if project_slug:
                _mark_feature_done(project_slug, safe_topic)
            send_message(TOKEN, CHAT_ID, "✅ Brainstorming abgeschlossen")
        else:
            send_message(TOKEN, CHAT_ID, f"❌ Brainstorming fehlgeschlagen\n{(stderr or '')[-300:]}")
    except subprocess.TimeoutExpired:
        proc.kill()
        send_message(TOKEN, CHAT_ID, "❌ Brainstorming-Timeout (2h überschritten)")
    finally:
        session_manager.clear_session()
        _clear_session()


def _run_status(slug):
    registry = load_registry()
    proj = next((p for p in registry if p["slug"] == slug),
                {"slug": slug, "name": slug, "path": "", "repo": ""})
    hub_path = HUB_DIR / "topics" / slug
    hub_path.mkdir(parents=True, exist_ok=True)
    vision_path = hub_path / "VISION.md"
    output_path = hub_path / "status_output.txt"
    output_path.unlink(missing_ok=True)

    specs = sorted((hub_path / "specs").glob("*.md")) if (hub_path / "specs").exists() else []
    specs_note = (f"Also read last 3 specs: {', '.join(str(s) for s in specs[-3:])}"
                  if specs else "")

    git_log = ""
    if proj.get("path") and Path(proj["path"]).exists():
        r = subprocess.run(["git", "-C", proj["path"], "log", "--oneline", "-10"],
                           capture_output=True, text=True)
        git_log = r.stdout.strip()

    plans_info = json.dumps(load_plans(), ensure_ascii=False)

    prompt = (
        f"Generate a status report for project: {proj['name']} (slug: {slug}). "
        f"Read {vision_path} for goal, backlog, confidence scores, and last session summary. "
        f"{specs_note} "
        f"Recent git log:\n{git_log}\n"
        f"Scheduled plans: {plans_info}\n"
        f"Write the report to {output_path} in this exact format:\n"
        f"📊 {proj['name']} — Status {date.today().isoformat()}\n\n"
        f"🎯 Ziel: <one line>\n\n"
        f"✅ Zuletzt implementiert:\n• <bullet>\n\n"
        f"🔲 Nächste Schritte (nach Prio):\n1. <step>\n\n"
        f"❓ Offene Fragen:\n• <question>\n\n"
        f"📅 Letzter Commit: <info>\n"
        f"Write ONLY the report to the file. Then exit."
    )
    cmd = ["claude", "--allowedTools", "Bash,Read,Write", "-p", prompt]
    env = {**os.environ, "CLAUDE_AUTOMATED": "1"}
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", timeout=120, cwd=str(hub_path), env=env)
        if output_path.exists():
            report = output_path.read_text(encoding="utf-8").strip()
            output_path.unlink(missing_ok=True)
            send_message(TOKEN, CHAT_ID, report[:4000])
        else:
            send_message(TOKEN, CHAT_ID, f"❌ Status-Report fehlgeschlagen\n{(result.stderr or '')[-200:]}")
    except subprocess.TimeoutExpired:
        send_message(TOKEN, CHAT_ID, "❌ Status-Timeout (2 Min überschritten)")


def main():
    global _active_question_id

    offset = None
    print(f"Brain Bot gestartet (chat_id={CHAT_ID})")

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

                    if _active_question_id and not data.startswith(("proj_", "npth_")) and data not in ("new_proj",):
                        _write_question_response(_active_question_id, data)
                        _active_question_id = None
                        send_message(TOKEN, CHAT_ID, f"💬 Antwort: {data}")
                        continue

                    if data == "new_proj":
                        _pending_new_project[CHAT_ID] = {"state": "await_name"}
                        send_message(TOKEN, CHAT_ID, "Name des neuen Projekts?")
                    elif data.startswith("proj_sel:"):
                        slug = data[9:]
                        registry = load_registry()
                        proj = next((p for p in registry if p["slug"] == slug), {"name": slug})
                        sub_buttons = [
                            [
                                {"text": "🔭 Vision", "callback_data": f"proj_vis:{slug}"},
                                {"text": "🧠 Brainstorming", "callback_data": f"proj_bs:{slug}"},
                            ],
                            [{"text": "📊 Status", "callback_data": f"proj_status:{slug}"}],
                            [{"text": "← Zurück", "callback_data": "proj_back"}],
                        ]
                        stored_msg_id = _proj_msg_id.get(CHAT_ID)
                        if stored_msg_id:
                            edit_message_keyboard(TOKEN, CHAT_ID, stored_msg_id, sub_buttons)
                        else:
                            mid = send_message(TOKEN, CHAT_ID, f"📁 {proj['name']}",
                                               reply_markup={"inline_keyboard": sub_buttons})
                            if mid:
                                _proj_msg_id[CHAT_ID] = mid
                    elif data == "proj_back":
                        buttons = _project_list_keyboard()
                        stored_msg_id = _proj_msg_id.get(CHAT_ID)
                        if stored_msg_id:
                            edit_message_keyboard(TOKEN, CHAT_ID, stored_msg_id, buttons)
                        else:
                            mid = send_message(TOKEN, CHAT_ID, "📁 Projekte:",
                                               reply_markup={"inline_keyboard": buttons})
                            if mid:
                                _proj_msg_id[CHAT_ID] = mid
                    elif data.startswith("proj_vis:"):
                        slug = data[9:]
                        if session_manager.is_session_active():
                            send_message(TOKEN, CHAT_ID, "⚠️ Session läuft bereits.")
                        else:
                            send_message(TOKEN, CHAT_ID, f"🔭 Vision-Session für {slug} gestartet")
                            threading.Thread(target=_run_vision, args=(slug,), daemon=True).start()
                    elif data.startswith("proj_bs:"):
                        slug = data[8:]
                        features = _parse_backlog(slug)
                        if not features:
                            send_message(TOKEN, CHAT_ID,
                                         f"Kein Backlog für {slug}. Starte zuerst eine Vision-Session.")
                        else:
                            buttons = []
                            for i, feat in enumerate(features[:10]):
                                title = feat["title"]
                                label = (title[:40] + "…") if len(title) > 40 else title
                                buttons.append([{"text": label, "callback_data": f"backlog_feat:{slug}:{i}"}])
                            send_message(TOKEN, CHAT_ID, "Welches Feature brainstormen?",
                                         reply_markup={"inline_keyboard": buttons})
                    elif data.startswith("proj_status:"):
                        slug = data[12:]
                        if session_manager.is_session_active():
                            send_message(TOKEN, CHAT_ID, "⚠️ Session läuft bereits.")
                        else:
                            send_message(TOKEN, CHAT_ID, f"📊 Status-Report für {slug} wird erstellt...")
                            threading.Thread(target=_run_status, args=(slug,), daemon=True).start()
                    elif data.startswith("backlog_feat:"):
                        _, slug, idx_str = data.split(":", 2)
                        features = _parse_backlog(slug)
                        idx = int(idx_str)
                        if idx >= len(features):
                            send_message(TOKEN, CHAT_ID, "⚠️ Feature nicht mehr im Backlog.")
                        elif session_manager.is_session_active():
                            send_message(TOKEN, CHAT_ID, "⚠️ Session läuft bereits. Bitte warten.")
                        else:
                            feature = features[idx]["title"]
                            send_message(TOKEN, CHAT_ID, f"🧠 Brainstorming: {feature}")
                            threading.Thread(target=_run_brainstorming, args=(feature, None, slug), daemon=True).start()
                    elif data.startswith("npth_a:"):
                        slug = data[7:]
                        state_data = _pending_new_project.pop(CHAT_ID, {})
                        _create_project_entry(slug, state_data.get("name", slug), path=f"/root/projekte/{slug}")
                    elif data.startswith("npth_b:"):
                        slug = data[7:]
                        state_data = _pending_new_project.get(CHAT_ID, {})
                        _pending_new_project[CHAT_ID] = {**state_data, "state": "await_custom_path"}
                        send_message(TOKEN, CHAT_ID, "Bitte Pfad eingeben (z.B. /root/projekte/mein-projekt):")
                    elif data.startswith("npth_c:"):
                        slug = data[7:]
                        state_data = _pending_new_project.pop(CHAT_ID, {})
                        _create_project_entry(slug, state_data.get("name", slug), path="")
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

                if chat_id in _pending_new_project:
                    state_data = _pending_new_project[chat_id]
                    state = state_data.get("state")
                    if state == "await_name":
                        proj_name = text.strip()
                        proj_slug = re.sub(r"[^a-z0-9]+", "-", proj_name.lower()).strip("-")
                        if not proj_slug:
                            send_message(TOKEN, CHAT_ID, "❌ Ungültiger Name. Nochmal versuchen.")
                        else:
                            default_path = f"/root/projekte/{proj_slug}"
                            _pending_new_project[chat_id] = {"state": "await_path", "slug": proj_slug, "name": proj_name}
                            buttons = [
                                [{"text": f"A) {default_path}", "callback_data": f"npth_a:{proj_slug}"}],
                                [{"text": "B) Anderen Pfad eingeben", "callback_data": f"npth_b:{proj_slug}"}],
                                [{"text": "C) Noch kein Pfad (nur Planung)", "callback_data": f"npth_c:{proj_slug}"}],
                            ]
                            send_message(TOKEN, CHAT_ID, f"Wo soll {proj_name} angelegt werden?",
                                         reply_markup={"inline_keyboard": buttons})
                    elif state == "await_custom_path":
                        slug = state_data["slug"]
                        name = state_data["name"]
                        del _pending_new_project[chat_id]
                        _create_project_entry(slug, name, path=text.strip())
                    continue

                t = text.lower()

                if t.startswith("brainstorming:"):
                    topic = text[14:].strip()
                    if not topic:
                        send_message(TOKEN, CHAT_ID,
                            "Nutzung: brainstorming: <idee>\n"
                            "oder:    brainstorming: <idee>, basis: <slug>\n"
                            "Specs anzeigen: /specs")
                    elif session_manager.is_session_active():
                        send_message(TOKEN, CHAT_ID, "⚠️ Session läuft bereits. Bitte warten.")
                    else:
                        basis_slug = None
                        if ", basis:" in topic.lower():
                            idx = topic.lower().index(", basis:")
                            basis_slug = topic[idx + 8:].strip()
                            topic = topic[:idx].strip()
                        send_message(TOKEN, CHAT_ID, "🧠 Brainstorming gestartet — Fragen kommen gleich über den Chat")
                        threading.Thread(target=_run_brainstorming, args=(topic, basis_slug), daemon=True).start()
                elif t == "vision:end":
                    if session_manager.is_session_active():
                        (HUB_DIR / ".vision_end").write_text("end")
                        send_message(TOKEN, CHAT_ID, "⏹ vision:end Signal gesendet — Claude schreibt VISION.md")
                    else:
                        send_message(TOKEN, CHAT_ID, "Keine Vision-Session aktiv.")
                elif t.startswith("vision:"):
                    slug = text[7:].strip()
                    if not slug:
                        send_message(TOKEN, CHAT_ID, "Nutzung: vision: <slug>  z.B. vision: dart-app\nProjekte anzeigen: projekte")
                    elif session_manager.is_session_active():
                        send_message(TOKEN, CHAT_ID, "⚠️ Session läuft bereits. Warten bis abgeschlossen.")
                    else:
                        registry = load_registry()
                        proj = next((p for p in registry if p["slug"] == slug or p["name"].lower() == slug.lower()), None)
                        if not proj:
                            send_message(TOKEN, CHAT_ID, f"❌ Projekt '{slug}' nicht gefunden.\nErst anlegen: projekte → ➕ Neues Projekt")
                        else:
                            send_message(TOKEN, CHAT_ID, f"🔭 Vision-Session für {proj['name']} gestartet — Fragen kommen gleich")
                            threading.Thread(target=_run_vision, args=(proj["slug"],), daemon=True).start()
                elif t == "projekte":
                    buttons = _project_list_keyboard()
                    mid = send_message(TOKEN, CHAT_ID, "📁 Projekte:", reply_markup={"inline_keyboard": buttons})
                    if mid:
                        _proj_msg_id[CHAT_ID] = mid
                elif t == "/specs":
                    send_message(TOKEN, CHAT_ID, _format_specs())
                elif t == "hilfe":
                    send_message(TOKEN, CHAT_ID, HILFE_TEXT)
                else:
                    if session_manager.is_session_active():
                        session_manager.write_comment(text)
                        send_message(TOKEN, CHAT_ID, "💬 Kommentar gespeichert — wird bei nächster Frage angehängt")
                    else:
                        send_message(TOKEN, CHAT_ID, "🧠 Brainstorming gestartet — Fragen kommen gleich")
                        threading.Thread(target=_run_brainstorming, args=(text,), daemon=True).start()

            q_path = WORK_DIR / "pending_question.json"
            if not _active_question_id and q_path.exists():
                try:
                    data = json.loads(q_path.read_text())
                    if data.get("target_bot", "permissions") == "brain":
                        q_path.unlink()
                        _active_question_id = data["request_id"]
                        kb = build_inline_keyboard(data["question"])
                        send_message(TOKEN, CHAT_ID, f"❓ {data['question']}",
                                     reply_markup={"inline_keyboard": kb})
                except Exception as e:
                    print(f"question file error: {e}")

            time.sleep(0.3)
        except Exception as e:
            print(f"brain bot error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()

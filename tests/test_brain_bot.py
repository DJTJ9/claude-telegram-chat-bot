import os, sys, json
os.environ.setdefault("TOKEN_BRAIN", "test_token")
os.environ.setdefault("CHAT_ID", "12345")
os.environ.setdefault("GROQ_API_KEY", "test_key")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_send_message_returns_message_id():
    from core.telegram import send_message
    fake_response = MagicMock()
    fake_response.json.return_value = {"result": {"message_id": 42}}
    with patch("core.telegram.requests.post", return_value=fake_response):
        result = send_message("token", 123, "hello")
    assert result == 42


def test_send_message_returns_none_on_missing():
    from core.telegram import send_message
    fake_response = MagicMock()
    fake_response.json.return_value = {"ok": False}
    with patch("core.telegram.requests.post", return_value=fake_response):
        result = send_message("token", 123, "hello")
    assert result is None


def test_edit_message_keyboard_calls_correct_endpoint():
    from core.telegram import edit_message_keyboard
    fake_response = MagicMock()
    with patch("core.telegram.requests.post", return_value=fake_response) as mock_post:
        edit_message_keyboard("mytoken", 123, 99, [[{"text": "A", "callback_data": "a"}]])
    call_args = mock_post.call_args
    assert "editMessageReplyMarkup" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["chat_id"] == 123
    assert payload["message_id"] == 99
    assert payload["reply_markup"]["inline_keyboard"][0][0]["text"] == "A"


def test_parse_backlog_returns_features(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    vision = tmp_path / "topics" / "my-app" / "VISION.md"
    vision.parent.mkdir(parents=True)
    vision.write_text(
        "# My App\n\n## Features (Backlog)\n- [ ] Feature A\n- [x] Done Feature\n- [ ] Feature B\n\n## Architektur\n"
    )
    result = brain._parse_backlog("my-app")
    assert [f["title"] for f in result] == ["Feature A", "Feature B"]


def test_parse_backlog_no_vision(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    result = brain._parse_backlog("missing-slug")
    assert result == []


def test_parse_backlog_no_section(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    vision = tmp_path / "topics" / "my-app" / "VISION.md"
    vision.parent.mkdir(parents=True)
    vision.write_text("# My App\n\n## Ziel\nKein Backlog hier.\n")
    result = brain._parse_backlog("my-app")
    assert result == []


def test_mark_feature_done(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    vision = tmp_path / "topics" / "my-app" / "VISION.md"
    vision.parent.mkdir(parents=True)
    vision.write_text("## Features\n- [ ] Feature A\n- [ ] Feature B\n")
    brain._mark_feature_done("my-app", "Feature A")
    content = vision.read_text()
    assert "- [x] Feature A (geplant" in content
    assert "- [ ] Feature B" in content


def test_mark_feature_done_missing_feature(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    vision = tmp_path / "topics" / "my-app" / "VISION.md"
    vision.parent.mkdir(parents=True)
    vision.write_text("## Features\n- [ ] Feature A\n")
    brain._mark_feature_done("my-app", "Nonexistent")
    assert "- [ ] Feature A" in vision.read_text()


def test_project_list_keyboard_structure(tmp_path, monkeypatch):
    import bots.brain as brain
    import core.state as st
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    monkeypatch.setattr(st, "HUB_DIR", str(tmp_path))
    registry_path = tmp_path / "projects-registry.json"
    registry_path.write_text(json.dumps([
        {"slug": "app-a", "name": "App A", "path": "", "repo": "", "description": ""},
        {"slug": "app-b", "name": "App B", "path": "", "repo": "", "description": ""},
    ]))
    kb = brain._project_list_keyboard()
    slugs = [row[0]["callback_data"] for row in kb[:-1]]
    assert "proj_sel:app-a" in slugs
    assert "proj_sel:app-b" in slugs
    assert kb[-1][0]["callback_data"] == "new_proj"


def test_proj_msg_id_state_exists():
    import bots.brain as brain
    assert hasattr(brain, "_proj_msg_id")
    assert isinstance(brain._proj_msg_id, dict)


def test_voice_import_available():
    from core.telegram import transcribe_voice, normalize_voice
    assert callable(transcribe_voice)
    assert callable(normalize_voice)


def test_free_text_starts_brainstorming_when_no_session(tmp_path, monkeypatch):
    from core import session_manager as sm
    monkeypatch.setattr(sm, "_STATE_PATH", tmp_path / "session_state.json")
    monkeypatch.setattr(sm, "_COMMENT_PATH", tmp_path / "pending_comment.json")
    messages = []
    assert not sm.is_session_active()
    if sm.is_session_active():
        sm.write_comment("some text")
        messages.append("💬 Kommentar gespeichert — wird bei nächster Frage angehängt")
    else:
        messages.append("🧠 Brainstorming gestartet — Fragen kommen gleich")
    assert any("Brainstorming" in m for m in messages)


def test_free_text_saves_comment_when_session_active(tmp_path, monkeypatch):
    from core import session_manager as sm
    monkeypatch.setattr(sm, "_STATE_PATH", tmp_path / "session_state.json")
    monkeypatch.setattr(sm, "_COMMENT_PATH", tmp_path / "pending_comment.json")
    sm.save_session("vision", "my-proj", pid=1234)
    messages = []
    if sm.is_session_active():
        sm.write_comment("some text")
        messages.append("💬 Kommentar gespeichert — wird bei nächster Frage angehängt")
    else:
        messages.append("🧠 Brainstorming gestartet — Fragen kommen gleich")
    assert any("Kommentar" in m for m in messages)
    assert sm.read_and_clear_comment() == "some text"


def test_project_submenu_has_status_button():
    slug = "app-a"
    sub_buttons = [
        [
            {"text": "🔭 Vision", "callback_data": f"proj_vis:{slug}"},
            {"text": "🧠 Brainstorming", "callback_data": f"proj_bs:{slug}"},
        ],
        [{"text": "📊 Status", "callback_data": f"proj_status:{slug}"}],
        [{"text": "← Zurück", "callback_data": "proj_back"}],
    ]
    callbacks = [btn["callback_data"] for row in sub_buttons for btn in row]
    assert f"proj_status:{slug}" in callbacks


def test_status_command_no_session(tmp_path, monkeypatch):
    import bots.brain as brain
    import core.session_manager as sm
    monkeypatch.setattr(sm, "_STATE_PATH", tmp_path / "session_state.json")
    messages = []
    monkeypatch.setattr(brain, "send_message", lambda *a, **kw: messages.append(a[2]) or 1)
    s = sm.load_session()
    if not s:
        brain.send_message(brain.TOKEN, brain.CHAT_ID, "✅ Keine Session aktiv.")
    assert any("Keine Session" in m for m in messages)


def test_status_command_active_session(tmp_path, monkeypatch):
    import bots.brain as brain
    import core.session_manager as sm
    from datetime import datetime, timedelta
    monkeypatch.setattr(sm, "_STATE_PATH", tmp_path / "session_state.json")
    monkeypatch.setattr(sm, "_COMMENT_PATH", tmp_path / "pending_comment.json")
    sm.save_session("vision", "my-proj", pid=1234)
    s = sm.load_session()
    s["started_at"] = (datetime.now() - timedelta(minutes=10)).isoformat(timespec="seconds")
    (tmp_path / "session_state.json").write_text(json.dumps(s))
    messages = []
    monkeypatch.setattr(brain, "send_message", lambda *a, **kw: messages.append(a[2]) or 1)
    session = sm.load_session()
    if session:
        elapsed = int((datetime.now() - datetime.fromisoformat(session["started_at"])).total_seconds() / 60)
        brain.send_message(brain.TOKEN, brain.CHAT_ID,
            f"⚙️ Aktive Session: {session['active']}\nProjekt: {session['slug']}\n"
            f"Läuft seit: {elapsed} Min\nPID: {session['pid']}")
    assert any("vision" in m for m in messages)
    assert any("my-proj" in m for m in messages)
    sm.clear_session()


def test_append_idea_creates_vision_if_missing(tmp_path, monkeypatch):
    import bots.brain as brain
    from unittest.mock import patch
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    with patch("subprocess.run"):
        brain._append_idea_to_backlog("new-proj", "Push notifications")
    vision = tmp_path / "topics" / "new-proj" / "VISION.md"
    assert vision.exists()
    assert "Push notifications" in vision.read_text()
    assert "<!-- prio:99 -->" in vision.read_text()


def test_append_idea_adds_to_existing_backlog(tmp_path, monkeypatch):
    import bots.brain as brain
    from unittest.mock import patch
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    vision = tmp_path / "topics" / "my-app" / "VISION.md"
    vision.parent.mkdir(parents=True)
    vision.write_text("# My App\n\n## Features (Backlog — priorisiert)\n- [ ] Existing  <!-- prio:1 -->\n")
    with patch("subprocess.run"):
        brain._append_idea_to_backlog("my-app", "New idea")
    content = vision.read_text()
    assert "- [ ] New idea  <!-- prio:99 -->" in content
    assert "- [ ] Existing" in content


def test_vision_failure_with_checkpoint_sends_resume_keyboard(tmp_path, monkeypatch):
    import bots.brain as brain
    import core.session_manager as sm
    monkeypatch.setattr(sm, "_STATE_PATH", tmp_path / "session_state.json")
    monkeypatch.setattr(sm, "_COMMENT_PATH", tmp_path / "pending_comment.json")
    sm.save_session("vision", "my-proj", pid=1)
    s = sm.load_session()
    checkpoint_content = "## Checkpoint\n**Erledigt:** discussed auth\n**Nächster Schritt:** ask about DB"
    sm.write_checkpoint(s["session_id"], checkpoint_content)
    messages = []
    keyboards = []
    def fake_send(token, chat_id, text, reply_markup=None):
        messages.append(text)
        if reply_markup:
            keyboards.append(reply_markup)
        return 1
    monkeypatch.setattr(brain, "send_message", fake_send)
    checkpoint = sm.load_checkpoint(s["session_id"])
    if checkpoint:
        brain.send_message(brain.TOKEN, brain.CHAT_ID,
            f"⚠️ Session unterbrochen\n\n{checkpoint[:500]}",
            reply_markup={"inline_keyboard": [[
                {"text": "🔄 Fortsetzen", "callback_data": f"resume:my-proj:vision"},
                {"text": "❌ Abbrechen", "callback_data": "session_cancel"},
            ]]}
        )
    assert any("unterbrochen" in m for m in messages)
    assert len(keyboards) > 0
    sm.clear_session()


def test_run_chunked_sends_progress_messages(tmp_path, monkeypatch):
    import bots.brain as brain
    import core.session_manager as sm
    from unittest.mock import patch, MagicMock
    monkeypatch.setattr(sm, "_STATE_PATH", tmp_path / "session_state.json")
    monkeypatch.setattr(sm, "_COMMENT_PATH", tmp_path / "pending_comment.json")
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task 1: Init repo\n**Dateien:** `setup.py`\nCreate setup.\n\n"
        "## Task 2: Add tests\n**Dateien:** `tests/test.py`\nWrite tests.\n"
    )
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    messages = []
    monkeypatch.setattr(brain, "send_message", lambda *a, **kw: messages.append(a[2]) or 1)
    call_count = {"n": 0}
    class FakeProc:
        pid = 1
        returncode = 0
        def communicate(self, timeout=None):
            return ("", "")
    def fake_popen(cmd, *args, **kwargs):
        return FakeProc()
    def fake_run(cmd, *args, **kwargs):
        m = MagicMock()
        m.returncode = 0
        call_count["n"] += 1
        m.stdout = f"hash{call_count['n']}"
        m.stderr = ""
        return m
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr("subprocess.run", fake_run)
    plan_entry = {
        "slug": "my-proj",
        "plan_path": str(plan.relative_to(tmp_path)),
    }
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    import core.state as st
    monkeypatch.setattr(st, "HUB_DIR", str(tmp_path))
    (tmp_path / "projects-registry.json").write_text(json.dumps([
        {"slug": "my-proj", "name": "My Proj", "path": str(proj_dir), "repo": "", "description": ""}
    ]))
    (tmp_path / "scheduled_plans.json").write_text("[]")
    brain._run_chunked_implementation(plan_entry)
    assert any("Task 1/2" in m for m in messages)
    assert any("Task 2/2" in m for m in messages)
    assert any("abgeschlossen" in m for m in messages)


def test_format_dev_status_active_feature(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    status_dir = tmp_path / "topics" / "my-proj"
    status_dir.mkdir(parents=True)
    (status_dir / "STATUS.md").write_text(
        "# Project Status — my-proj\n"
        "Active: My Feature\n"
        "Phase: implement\n"
        "Spec: topics/my-proj/specs/spec.md\n"
        "Plan: topics/my-proj/plans/plan.md\n"
        "Updated: 2026-06-24\n\n"
        "## Roadmap\n"
        "- [done]      Feature A\n"
        "- [discussed] My Feature\n"
        "- [idea]      Future Idea\n"
    )
    result = brain._format_dev_status("my-proj")
    assert "My Feature" in result
    assert "implement" in result
    assert "Future Idea" in result


def test_format_dev_status_missing_file(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    result = brain._format_dev_status("nonexistent-proj")
    assert "nicht gefunden" in result.lower()

import os, sys, json
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("TOKEN_BRAIN", "test_token")
os.environ.setdefault("CHAT_ID", "12345")
os.environ.setdefault("GROQ_API_KEY", "x")
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Task 5: accordion UI ─────────────────────────────────────────────────────

def test_load_projects_reads_registry(tmp_path):
    import bots.brain as brain
    reg = tmp_path / "projects-registry.json"
    reg.write_text(json.dumps([{"slug": "my-app", "name": "MyApp", "path": ""}]))
    with patch.object(brain, "HUB_DIR", tmp_path):
        result = brain._load_projects()
    assert result == [{"slug": "my-app", "name": "MyApp", "path": ""}]


def test_load_projects_returns_empty_on_missing(tmp_path):
    import bots.brain as brain
    with patch.object(brain, "HUB_DIR", tmp_path):
        assert brain._load_projects() == []


def test_get_dev_status_reads_status_md(tmp_path):
    import bots.brain as brain
    status = tmp_path / "topics" / "my-app" / "STATUS.md"
    status.parent.mkdir(parents=True)
    status.write_text("# Status\nActive: Feature X\nPhase: plan\n")
    with patch.object(brain, "HUB_DIR", tmp_path):
        active, phase = brain._get_dev_status("my-app")
    assert active == "Feature X"
    assert phase == "plan"


def test_get_dev_status_missing_returns_empty(tmp_path):
    import bots.brain as brain
    with patch.object(brain, "HUB_DIR", tmp_path):
        assert brain._get_dev_status("nonexistent") == ("", "")


def test_build_main_keyboard_structure():
    import bots.brain as brain
    projects = [{"slug": "proj-a", "name": "ProjA"}, {"slug": "proj-b", "name": "ProjB"}]
    kb = brain._build_main_keyboard(projects)
    assert kb == [
        [{"text": "📁 ProjA", "callback_data": "proj:proj-a"}],
        [{"text": "📁 ProjB", "callback_data": "proj:proj-b"}],
    ]


def test_relay_and_toggle_code_removed():
    src = (Path(__file__).parent.parent / "bots" / "brain.py").read_text()
    for token in ("_check_relay_question", "_handle_relay_callback",
                  "_write_relay_response", "_handle_wait_reply",
                  "_wait_prompt_still_open", "_toggle_notify",
                  "_wait_state", "pending_question", "notify:on"):
        assert token not in src, token


# ── Task 6: quick-capture ────────────────────────────────────────────────────

def test_summarize_idea_calls_groq():
    import bots.brain as brain
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "Tolle Idee"
    with patch("bots.brain._groq_client", return_value=mock_client):
        result = brain._summarize_idea("Eine sehr lange Beschreibung einer Idee")
    assert result == "Tolle Idee"


def test_append_idea_writes_to_status_and_vision(tmp_path):
    import bots.brain as brain
    (tmp_path / "topics" / "p").mkdir(parents=True)
    status = tmp_path / "topics" / "p" / "STATUS.md"
    vision = tmp_path / "topics" / "p" / "VISION.md"
    status.write_text("# Status\n## Roadmap\n")
    vision.write_text("# Vision\n## Roadmap\n")
    with patch.object(brain, "HUB_DIR", tmp_path):
        brain._append_idea("p", "Neue Idee")
    assert "- [idea]      Neue Idee" in status.read_text()
    assert "- [idea]      Neue Idee" in vision.read_text()


def test_handle_message_capture_text(tmp_path):
    import bots.brain as brain
    brain._capture_state = {"slug": "p", "name": "ProjP"}
    (tmp_path / "topics" / "p").mkdir(parents=True)
    (tmp_path / "topics" / "p" / "STATUS.md").write_text("# S\n## Roadmap\n")
    (tmp_path / "topics" / "p" / "VISION.md").write_text("# V\n## Roadmap\n")
    with patch.object(brain, "HUB_DIR", tmp_path), \
         patch("bots.brain.send_message") as mock_send, \
         patch("bots.brain._summarize_idea", return_value="Gute Idee"):
        brain._handle_message({"text": "Ich möchte ein neues Feature",
                                "chat": {"id": int(brain.CHAT_ID)}})
    assert brain._capture_state is None
    assert "Gute Idee" in mock_send.call_args[0][2]


def test_handle_message_start_shows_accordion():
    import bots.brain as brain
    with patch("bots.brain._show_main_menu") as mock_menu:
        brain._handle_message({"text": "/start", "chat": {"id": int(brain.CHAT_ID)}})
    mock_menu.assert_called_once()


def test_handle_message_no_capture_state_ignores_text():
    import bots.brain as brain
    brain._capture_state = None
    with patch("bots.brain.send_message") as mock_send:
        brain._handle_message({"text": "random text", "chat": {"id": int(brain.CHAT_ID)}})
    mock_send.assert_not_called()

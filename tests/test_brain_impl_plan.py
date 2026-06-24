import os, sys, json
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("TOKEN_BRAIN", "test_token")
os.environ.setdefault("CHAT_ID", "12345")
os.environ.setdefault("GROQ_API_KEY", "x")
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Task 1: Reply-Keyboard ────────────────────────────────────────────────────

def test_reply_keyboard_sent_on_start():
    src = (Path(__file__).parent.parent / "bots" / "brain.py").read_text()
    assert "is_persistent" in src, "ReplyKeyboardMarkup muss is_persistent:True enthalten"
    assert '"🤖"' in src or "'🤖'" in src, "🤖-Button muss in keyboard definiert sein"


def test_robot_emoji_triggers_main_menu():
    import bots.brain as brain
    with patch("bots.brain.send_message", return_value=42) as mock_send, \
         patch("bots.brain.edit_message"), \
         patch.object(brain, "_accordion_msg_id", None):
        brain._handle_message({"text": "🤖", "chat": {"id": 12345}})
    mock_send.assert_called()


# ── Task 2: Implement-Plan State-Machine ──────────────────────────────────────

def test_impl_button_in_sub_keyboard():
    src = (Path(__file__).parent.parent / "bots" / "brain.py").read_text()
    assert "Plan umsetzen" in src, "🚀 Plan umsetzen muss in sub_keyboard erscheinen"
    assert "_impl_state" in src, "_impl_state State-Variable muss existieren"
    assert "_get_planned_items" in src, "Hilfsfunktion für [planned]-Items muss existieren"


def test_get_planned_items_parses_status_md(tmp_path):
    import bots.brain as brain
    topics = tmp_path / "topics" / "myproj"
    topics.mkdir(parents=True)
    (topics / "STATUS.md").write_text(
        "Active: x\nPhase: implement\n\n## Roadmap\n"
        "- [done]       Feature A\n"
        "- [planned]    Feature B\n"
        "- [idea]       Feature C\n"
    )
    (topics / "plans").mkdir()
    (topics / "plans" / "2026-06-24-feature-b.md").write_text("# Plan B")

    with patch.object(brain, "HUB_DIR", tmp_path):
        items = brain._get_planned_items("myproj")

    assert len(items) == 1
    assert items[0]["name"] == "Feature B"
    assert "feature-b" in items[0]["plan_path"]


def test_schedule_plan_writes_to_json(tmp_path):
    import bots.brain as brain
    plans_file = tmp_path / "scheduled_plans.json"
    plans_file.write_text("[]")

    with patch.object(brain, "HUB_DIR", tmp_path), \
         patch("bots.brain.send_message"), \
         patch("bots.brain.subprocess") as mock_sub, \
         patch.object(brain, "_impl_state", {
             "step": "await_time",
             "slug": "myproj",
             "plan_name": "Feature B",
             "plan_path": "topics/myproj/plans/2026-06-24-feature-b.md",
         }):
        brain._handle_impl_time_input("22:00")

    plans = json.loads(plans_file.read_text())
    assert len(plans) == 1
    assert plans[0]["slug"] == "feature-b"
    assert plans[0]["scheduled_time"] == "22:00"
    assert plans[0]["status"] == "pending"

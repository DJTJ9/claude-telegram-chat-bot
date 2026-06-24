import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("TOKEN_BRAIN", "x")
os.environ.setdefault("GROQ_API_KEY", "x")


def test_await_msg_check_precedes_pending_new_project():
    import inspect, bots.brain as brain
    src = inspect.getsource(brain)
    # The await_msg message-handler block must come before "if chat_id in _pending_new_project:"
    await_msg_pos = src.index('_capture_state[chat_id].get("step") == "await_msg"')
    pending_new_pos = src.index("if chat_id in _pending_new_project")
    assert await_msg_pos < pending_new_pos, "await_msg handler must precede _pending_new_project check"


def test_await_dup_step_set_by_message_handler():
    import inspect, bots.brain as brain
    src = inspect.getsource(brain)
    assert '"await_dup"' in src

import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("TOKEN_BRAIN", "x")
os.environ.setdefault("GROQ_API_KEY", "x")


def test_idee_bare_command_handled():
    import inspect, bots.brain as brain
    src = inspect.getsource(brain)
    assert 't == "idee"' in src


def test_proj_sel_has_capture_button():
    import inspect, bots.brain as brain
    src = inspect.getsource(brain)
    assert "Idee erfassen" in src
    assert 'f"cap_proj:{slug}"' in src

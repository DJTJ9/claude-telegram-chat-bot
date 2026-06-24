import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("TOKEN_BRAIN", "x")
os.environ.setdefault("GROQ_API_KEY", "x")


def test_all_cap_prefixes_handled():
    import inspect, bots.brain as brain
    src = inspect.getsource(brain)
    assert 'data.startswith("cap_proj:")' in src
    assert 'data.startswith("cap_type:")' in src
    assert 'data.startswith("cap_feat:")' in src
    assert 'data.startswith("cap_dup:")' in src
    assert '"await_type"' in src
    assert '"await_msg"' in src

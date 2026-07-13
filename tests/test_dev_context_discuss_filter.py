import json
import os
import subprocess
from pathlib import Path

HUB_DIR = os.environ.get("HUB_DIR", "")

STATUS_MD = """# Project Status — testproj
Active: Feature X
Phase: discuss
Spec:
Plan:
Updated: 2026-01-01

## Roadmap
- [vision]     Feature V
- [idea]       Feature Y
- [bug]        Feature Z
- [discussed]  Feature D
- [planned]    Feature P
"""


def _make_hub(tmp_path):
    (tmp_path / "topics" / "testproj").mkdir(parents=True)
    (tmp_path / "topics" / "testproj" / "STATUS.md").write_text(STATUS_MD)
    (tmp_path / "projects-registry.json").write_text("[]")
    return tmp_path


def _run(hub, command):
    env = {**os.environ, "HUB_DIR": str(hub)}
    r = subprocess.run(
        ["python3", f"{HUB_DIR}/scripts/dev_context.py", "--command", command,
         "--slug", "testproj"],
        capture_output=True, text=True, env=env, timeout=5,
    )
    return json.loads(r.stdout)


def test_discuss_includes_bug_status(tmp_path):
    hub = _make_hub(tmp_path / "hub")
    result = _run(hub, "discuss")
    names = {f["name"] for f in result}
    assert "Feature Z" in names
    assert "Feature V" in names
    assert "Feature Y" in names
    assert "Feature D" not in names
    assert "Feature P" not in names


def test_plan_filter_unchanged(tmp_path):
    hub = _make_hub(tmp_path / "hub")
    result = _run(hub, "plan")
    names = {f["name"] for f in result}
    assert names == {"Feature D"}


def test_implement_filter_unchanged(tmp_path):
    hub = _make_hub(tmp_path / "hub")
    result = _run(hub, "implement")
    names = {f["name"] for f in result}
    assert names == {"Feature P"}

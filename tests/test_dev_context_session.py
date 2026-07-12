import json
import os
import subprocess
from pathlib import Path

HUB_DIR = os.environ.get("HUB_DIR", "")

STATUS_MD = """# Project Status — testproj
Active: Feature X
Phase: plan
Spec: topics/testproj/specs/2026-01-01-feature-x.md
Plan:
Updated: 2026-01-01

## Roadmap
- [discussed]  Feature X
- [idea]       Feature Y
"""


def _make_hub(tmp_path):
    (tmp_path / "topics" / "testproj").mkdir(parents=True)
    (tmp_path / "topics" / "testproj" / "STATUS.md").write_text(STATUS_MD)
    (tmp_path / "projects-registry.json").write_text("[]")
    return tmp_path


def _session(hub, work_dir, session_id):
    env = {**os.environ, "HUB_DIR": str(hub), "WORK_DIR": str(work_dir),
           "CLAUDE_CODE_SESSION_ID": session_id}
    r = subprocess.run(
        ["python3", f"{HUB_DIR}/scripts/dev_context.py", "--command", "session"],
        capture_output=True, text=True, env=env, timeout=5,
    )
    return json.loads(r.stdout)


def test_session_includes_spec_plan_features(tmp_path):
    hub = _make_hub(tmp_path / "hub")
    work = tmp_path / "work"
    sessions_dir = work / "dev_sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "sid-1.json").write_text(json.dumps({"active_dev_slug": "testproj"}))

    result = _session(hub, work, "sid-1")

    assert result["slug"] == "testproj"
    assert result["active"] == "Feature X"
    assert result["phase"] == "plan"
    assert result["spec"] == "topics/testproj/specs/2026-01-01-feature-x.md"
    assert result["plan"] == ""
    assert result["features"] == [
        {"name": "Feature X", "status": "discussed"},
        {"name": "Feature Y", "status": "idea"},
    ]

import json
import os
import subprocess

HUB_DIR = os.environ.get("HUB_DIR", "")
SCRIPT = f"{HUB_DIR}/scripts/dev_context.py"

STATUS_MD = """# Project Status — testproj
Active: Feature X
Phase: plan
Spec: topics/testproj/specs/x-design.md
Plan:
Mode: subagent
Schedule: jetzt
Teach: no
Updated: 2026-01-01

## Roadmap
- [idea]      Feature Y
- [discussed] Feature X
- [done]      Feature Z
"""


def _make_hub(tmp_path, status=STATUS_MD):
    hub = tmp_path / "hub"
    (hub / "topics" / "testproj").mkdir(parents=True)
    (hub / "topics" / "testproj" / "STATUS.md").write_text(status)
    (hub / "projects-registry.json").write_text("[]")
    return hub


def _run(hub, *args):
    env = {**os.environ, "HUB_DIR": str(hub)}
    return subprocess.run(["python3", SCRIPT, *args],
                          capture_output=True, text=True, env=env, timeout=5)


def _status(hub):
    return (hub / "topics" / "testproj" / "STATUS.md").read_text()


def test_status_set_sets_field_and_stamps_updated(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "status-set", "--slug", "testproj",
             "--set", "Phase=implement")
    assert r.returncode == 0
    text = _status(hub)
    assert "Phase: implement" in text
    assert "Updated: 2026-01-01" not in text
    assert "Active: Feature X" in text


def test_status_set_clears_field(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "status-set", "--slug", "testproj",
             "--set", "Mode=", "--set", "Schedule=", "--set", "Teach=")
    assert r.returncode == 0
    text = _status(hub)
    assert "Mode:\n" in text
    assert "Schedule:\n" in text
    assert "Teach:\n" in text
    assert "subagent" not in text


def test_status_set_inserts_missing_field_before_updated(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "status-set", "--slug", "testproj",
             "--set", "Type=bug")
    assert r.returncode == 0
    lines = _status(hub).splitlines()
    assert "Type: bug" in lines
    assert lines.index("Type: bug") < next(
        i for i, line in enumerate(lines) if line.startswith("Updated:"))


def test_status_set_explicit_updated_wins(tmp_path):
    hub = _make_hub(tmp_path)
    _run(hub, "--command", "status-set", "--slug", "testproj",
         "--set", "Phase=finish", "--set", "Updated=2026-02-02")
    assert "Updated: 2026-02-02" in _status(hub)


def test_status_set_unknown_field_exits_1(tmp_path):
    hub = _make_hub(tmp_path)
    before = _status(hub)
    r = _run(hub, "--command", "status-set", "--slug", "testproj",
             "--set", "Bogus=x")
    assert r.returncode == 1
    assert "Bogus" in r.stderr
    assert _status(hub) == before


def test_status_set_missing_status_file_exits_1(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "status-set", "--slug", "nope",
             "--set", "Phase=plan")
    assert r.returncode == 1


def test_parse_status_md_knows_new_fields(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "status", "--slug", "testproj")
    assert r.returncode == 0
    import sys
    sys.path.insert(0, f"{HUB_DIR}/scripts")
    from dev_context import parse_status_md
    from pathlib import Path
    parsed = parse_status_md(Path(hub) / "topics" / "testproj" / "STATUS.md")
    assert parsed["mode"] == "subagent"
    assert parsed["schedule"] == "jetzt"
    assert parsed["teach"] == "no"
    assert parsed["type"] == ""
    assert parsed["lesson"] == ""

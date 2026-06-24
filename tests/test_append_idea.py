import sys, os, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("TOKEN_BRAIN", "x")
os.environ.setdefault("GROQ_API_KEY", "x")


def test_append_idea_writes_status_md(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: None)

    status = tmp_path / "topics" / "myproj" / "STATUS.md"
    status.parent.mkdir(parents=True)
    status.write_text(
        "# Project Status\nActive: x\nPhase: plan\n\n## Roadmap\n- [done]      Old thing\n"
    )
    (tmp_path / "topics" / "myproj" / "VISION.md").write_text(
        "# Vision\n\n## Features (Backlog — priorisiert)\n"
    )

    brain._append_idea_to_backlog("myproj", "New test idea")

    content = status.read_text()
    assert "- [idea]      New test idea" in content


def test_append_idea_creates_roadmap_section_if_missing(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: None)

    status = tmp_path / "topics" / "p2" / "STATUS.md"
    status.parent.mkdir(parents=True)
    status.write_text("# Project Status\n\n")
    (tmp_path / "topics" / "p2" / "VISION.md").write_text("# V\n")

    brain._append_idea_to_backlog("p2", "Another idea")

    content = status.read_text()
    assert "## Roadmap" in content
    assert "- [idea]      Another idea" in content

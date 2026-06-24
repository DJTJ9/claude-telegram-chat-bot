import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("TOKEN_BRAIN", "x")
os.environ.setdefault("GROQ_API_KEY", "x")


def test_read_status_ideas_returns_idea_and_discussed(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    status = tmp_path / "topics" / "test-proj" / "STATUS.md"
    status.parent.mkdir(parents=True)
    status.write_text(
        "# Project Status\n\n## Roadmap\n"
        "- [done]      Old thing\n"
        "- [idea]      My idea\n"
        "- [discussed]  Another feature\n"
    )
    result = brain._read_status_ideas("test-proj")
    assert result == ["My idea", "Another feature"]


def test_read_status_ideas_missing_file_returns_empty(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    assert brain._read_status_ideas("no-proj") == []


def test_find_duplicate_detects_overlap(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    status = tmp_path / "topics" / "p" / "STATUS.md"
    status.parent.mkdir(parents=True)
    status.write_text("# S\n\n## Roadmap\n- [idea]      Habit tracking feature for organizer\n")
    result = brain._find_duplicate("p", "Habit tracking for organizer bot")
    assert result == "Habit tracking feature for organizer"


def test_find_duplicate_no_match(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    status = tmp_path / "topics" / "p" / "STATUS.md"
    status.parent.mkdir(parents=True)
    status.write_text("# S\n\n## Roadmap\n- [idea]      Voice support\n")
    result = brain._find_duplicate("p", "Completely unrelated idea about databases")
    assert result is None

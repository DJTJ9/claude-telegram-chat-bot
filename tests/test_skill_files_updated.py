from pathlib import Path

CLAUDE_MD = Path("/root/.claude/CLAUDE.md").read_text()
FINISH_MD = Path("/root/.claude/skills/dev/phases/finish.md").read_text()


def test_claude_md_relay_section_removed():
    assert "Brainstorming via Telegram Relay" not in CLAUDE_MD


def test_claude_md_no_dual_ask_reference():
    assert "dual_ask.py" not in CLAUDE_MD


def test_finish_md_has_no_notifications_enabled_reference():
    assert "notifications_enabled" not in FINISH_MD

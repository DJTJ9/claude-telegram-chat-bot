from pathlib import Path

CLAUDE_MD = Path("/root/.claude/CLAUDE.md").read_text()


def test_claude_md_relay_section_removed():
    assert "Brainstorming via Telegram Relay" not in CLAUDE_MD


def test_claude_md_no_dual_ask_reference():
    assert "dual_ask.py" not in CLAUDE_MD

from pathlib import Path

CLAUDE_MD = Path("/root/.claude/CLAUDE.md").read_text()

def test_claude_md_uses_dual_ask():
    assert "dual_ask.py" in CLAUDE_MD

def test_claude_md_handles_use_cc():
    assert "USE_CC" in CLAUDE_MD

def test_claude_md_no_telegram_ask_in_relay_section():
    idx = CLAUDE_MD.index("Brainstorming via Telegram Relay")
    relay_section = CLAUDE_MD[idx:idx+800]
    assert "telegram_ask.py" not in relay_section

import subprocess
from unittest.mock import patch

def test_run_claude_timeout():
    from core.claude import run_claude
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 1200)):
        result = run_claude("test")
    assert "Timeout" in result

def test_run_claude_parse_returns_empty_on_timeout():
    from core.claude import run_claude_parse
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 30)):
        result = run_claude_parse("test", "sys")
    assert result == "{}"

def test_run_claude_with_history_builds_context():
    from core.claude import run_claude_with_history
    history = {
        123: [
            {"role": "user", "content": "Hallo"},
            {"role": "assistant", "content": "Hi"},
        ]
    }
    with patch("core.claude.run_claude", return_value="Antwort") as mock:
        result, new_history = run_claude_with_history(123, "neue Frage", history)
    call_prompt = mock.call_args[0][0]
    assert "Hallo" in call_prompt
    assert result == "Antwort"
    assert len(new_history[123]) == 4

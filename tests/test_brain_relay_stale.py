from pathlib import Path

src = (Path(__file__).parent.parent / "bots" / "brain.py").read_text()

def test_stale_relay_sends_message():
    """_handle_relay_callback sends user message when _relay_request_id is None."""
    idx = src.index("def _handle_relay_callback(")
    snippet = src[idx:idx+400]
    assert "Wurde bereits in CC beantwortet" in snippet

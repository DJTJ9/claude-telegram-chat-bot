import os, sys, json
os.environ.setdefault("TOKEN_BRAIN", "test_token")
os.environ.setdefault("CHAT_ID", "12345")
os.environ.setdefault("GROQ_API_KEY", "test_key")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_send_message_returns_message_id():
    from core.telegram import send_message
    fake_response = MagicMock()
    fake_response.json.return_value = {"result": {"message_id": 42}}
    with patch("core.telegram.requests.post", return_value=fake_response):
        result = send_message("token", 123, "hello")
    assert result == 42


def test_send_message_returns_none_on_missing():
    from core.telegram import send_message
    fake_response = MagicMock()
    fake_response.json.return_value = {"ok": False}
    with patch("core.telegram.requests.post", return_value=fake_response):
        result = send_message("token", 123, "hello")
    assert result is None


def test_edit_message_keyboard_calls_correct_endpoint():
    from core.telegram import edit_message_keyboard
    fake_response = MagicMock()
    with patch("core.telegram.requests.post", return_value=fake_response) as mock_post:
        edit_message_keyboard("mytoken", 123, 99, [[{"text": "A", "callback_data": "a"}]])
    call_args = mock_post.call_args
    assert "editMessageReplyMarkup" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["chat_id"] == 123
    assert payload["message_id"] == 99
    assert payload["reply_markup"]["inline_keyboard"][0][0]["text"] == "A"


def test_parse_backlog_returns_features(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    vision = tmp_path / "topics" / "my-app" / "VISION.md"
    vision.parent.mkdir(parents=True)
    vision.write_text(
        "# My App\n\n## Features (Backlog)\n- [ ] Feature A\n- [x] Done Feature\n- [ ] Feature B\n\n## Architektur\n"
    )
    result = brain._parse_backlog("my-app")
    assert result == ["Feature A", "Feature B"]


def test_parse_backlog_no_vision(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    result = brain._parse_backlog("missing-slug")
    assert result == []


def test_parse_backlog_no_section(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    vision = tmp_path / "topics" / "my-app" / "VISION.md"
    vision.parent.mkdir(parents=True)
    vision.write_text("# My App\n\n## Ziel\nKein Backlog hier.\n")
    result = brain._parse_backlog("my-app")
    assert result == []


def test_mark_feature_done(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    vision = tmp_path / "topics" / "my-app" / "VISION.md"
    vision.parent.mkdir(parents=True)
    vision.write_text("## Features\n- [ ] Feature A\n- [ ] Feature B\n")
    brain._mark_feature_done("my-app", "Feature A")
    content = vision.read_text()
    assert "- [x] Feature A (geplant" in content
    assert "- [ ] Feature B" in content


def test_mark_feature_done_missing_feature(tmp_path, monkeypatch):
    import bots.brain as brain
    monkeypatch.setattr(brain, "HUB_DIR", tmp_path)
    vision = tmp_path / "topics" / "my-app" / "VISION.md"
    vision.parent.mkdir(parents=True)
    vision.write_text("## Features\n- [ ] Feature A\n")
    brain._mark_feature_done("my-app", "Nonexistent")
    assert "- [ ] Feature A" in vision.read_text()

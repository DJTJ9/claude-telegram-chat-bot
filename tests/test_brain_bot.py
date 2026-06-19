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

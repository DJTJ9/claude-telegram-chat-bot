import os

SESSION_BOT_MAP = {
    "brainstorming": "brain",
    "vision":        "brain",
    "teach":         "teach",
}

def _get_target_bot_name(active_session):
    return SESSION_BOT_MAP.get(active_session, "permissions")

def get_active_token(settings):
    bot_name = _get_target_bot_name(settings.get("active_session"))
    token_key = f"TOKEN_{bot_name.upper()}"
    return os.environ[token_key]

def get_chat_id():
    return int(os.environ.get("CHAT_ID", "8896609541"))

import os

SESSION_BOT_MAP = {
    "brainstorming": "brain",
    "vision":        "brain",
    "teach":         "teach",
    "organizer":     "organizer",
    "dev":           "brain",
}


def _get_target_bot_name(active_session):
    return SESSION_BOT_MAP.get(active_session, "brain")


def get_active_token(settings):
    bot_name = _get_target_bot_name(settings.get("active_session"))
    token_key = f"TOKEN_{bot_name.upper()}"
    return os.environ[token_key]


def get_notify_token(settings, env=None):
    if env is None:
        env = os.environ
    bot_name = _get_target_bot_name(settings.get("active_session"))
    token_key = f"TOKEN_{bot_name.upper()}"
    return env.get(token_key)


def get_chat_id():
    return int(os.environ.get("CHAT_ID", "8896609541"))

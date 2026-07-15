from core.routing import _get_target_bot_name, get_notify_token

def test_brainstorming_routes_to_brain():
    assert _get_target_bot_name("brainstorming") == "brain"

def test_vision_routes_to_brain():
    assert _get_target_bot_name("vision") == "brain"

def test_teach_routes_to_teach():
    assert _get_target_bot_name("teach") == "teach"

def test_none_routes_to_brain():
    assert _get_target_bot_name(None) == "brain"

def test_unknown_routes_to_brain():
    assert _get_target_bot_name("unknown") == "brain"


def test_organizer_routes_to_organizer():
    assert _get_target_bot_name("organizer") == "organizer"


def test_dev_routes_to_brain():
    assert _get_target_bot_name("dev") == "brain"


def test_get_notify_token_uses_active_session():
    env = {"TOKEN_BRAIN": "tok-brain", "TOKEN_PERMISSIONS": "tok-perm"}
    settings = {"active_session": "brainstorming"}
    assert get_notify_token(settings, env) == "tok-brain"


def test_get_notify_token_falls_back_to_brain():
    env = {"TOKEN_BRAIN": "tok-brain"}
    settings = {"active_session": None}
    assert get_notify_token(settings, env) == "tok-brain"


def test_get_notify_token_returns_none_if_no_token():
    env = {}
    settings = {"active_session": None}
    assert get_notify_token(settings, env) is None

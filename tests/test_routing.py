from core.routing import _get_target_bot_name

def test_brainstorming_routes_to_brain():
    assert _get_target_bot_name("brainstorming") == "brain"

def test_vision_routes_to_brain():
    assert _get_target_bot_name("vision") == "brain"

def test_teach_routes_to_teach():
    assert _get_target_bot_name("teach") == "teach"

def test_none_routes_to_permissions():
    assert _get_target_bot_name(None) == "permissions"

def test_unknown_routes_to_permissions():
    assert _get_target_bot_name("unknown") == "permissions"

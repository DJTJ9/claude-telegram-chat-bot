import json, os
from pathlib import Path
from core.atomic_json import atomic_update, atomic_write

WORK_DIR = os.environ.get("WORK_DIR", "/root/projekte/telegram-bot-army")

_DEFAULTS = {
    "implementation_mode": False,
    "implementation_mode_until": None,
    "active_session": None,
    "active_session_bot": None,
    "energie_level": None,
    "energie_updated": None,
}

def load_settings(work_dir=None):
    p = Path(work_dir or WORK_DIR) / "settings.json"
    if p.exists():
        try:
            data = json.loads(p.read_text())
            return {**_DEFAULTS, **data}
        except json.JSONDecodeError:
            pass
    return dict(_DEFAULTS)

def save_settings(s, work_dir=None):
    atomic_write(Path(work_dir or WORK_DIR) / "settings.json", s)


def update_settings(mutate, work_dir=None):
    """Atomic read-modify-write of settings.json under flock. The callback
    receives settings already merged with _DEFAULTS; it may mutate in place
    (return None) or return a new dict."""
    p = Path(work_dir or WORK_DIR) / "settings.json"

    def _apply(data):
        merged = {**_DEFAULTS, **data}
        result = mutate(merged)
        return result if result is not None else merged

    return atomic_update(p, _apply)

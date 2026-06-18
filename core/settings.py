import json, os
from pathlib import Path

WORK_DIR = os.environ.get("WORK_DIR", "/root/projekte/telegram-bot-army")

_DEFAULTS = {
    "notifications_enabled": True,
    "implementation_mode": False,
    "implementation_mode_until": None,
    "active_session": None,
    "active_session_bot": None,
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
    (Path(work_dir or WORK_DIR) / "settings.json").write_text(
        json.dumps(s, indent=2)
    )

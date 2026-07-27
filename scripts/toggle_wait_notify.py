#!/usr/bin/env python3
import os, sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(PROJECT_DIR))
from core.settings import update_settings


def set_wait_notify(value=None, work_dir=None) -> bool:
    """value=None → flip; True/False → set explicit. Returns new state."""
    def _mutate(s):
        cur = s.get("wait_notify_enabled", True)
        s["wait_notify_enabled"] = (not cur) if value is None else bool(value)
    return update_settings(_mutate, work_dir)["wait_notify_enabled"]


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    value = {"--on": True, "--off": False}.get(arg, None)
    state = set_wait_notify(value)
    print(f"Wait-Reminder: {'An' if state else 'Aus'}")

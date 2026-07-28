import json, os
from pathlib import Path

WORK_DIR = os.environ.get("WORK_DIR", "/root/projekte/telegram-bot-army")
HUB_DIR = os.environ.get("HUB_DIR", WORK_DIR)

def load_reminders(work_dir=None):
    p = Path(work_dir or WORK_DIR) / "reminders.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []

def save_reminders(reminders, work_dir=None):
    p = Path(work_dir or WORK_DIR) / "reminders.json"
    p.write_text(json.dumps(reminders, indent=2, ensure_ascii=False), encoding="utf-8")

def load_registry(hub_dir=None):
    p = Path(hub_dir or HUB_DIR) / "projects-registry.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []

def save_registry(registry, hub_dir=None):
    p = Path(hub_dir or HUB_DIR) / "projects-registry.json"
    p.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")

import json, os, subprocess
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

def load_plans(hub_dir=None):
    p = Path(hub_dir or HUB_DIR) / "scheduled_plans.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []

def save_plans(plans, hub_dir=None):
    p = Path(hub_dir or HUB_DIR) / "scheduled_plans.json"
    p.write_text(json.dumps(plans, indent=2, ensure_ascii=False), encoding="utf-8")

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

def set_plan_status(slug, status, hub_dir=None):
    plans = load_plans(hub_dir)
    for p in plans:
        if p["slug"] == slug:
            p["status"] = status
            break
    save_plans(plans, hub_dir)
    _hub = hub_dir or HUB_DIR
    subprocess.run(["git", "-C", _hub, "add", "scheduled_plans.json"], capture_output=True)
    subprocess.run(["git", "-C", _hub, "commit", "-m", f"chore: plan {slug} -> {status}"], capture_output=True)

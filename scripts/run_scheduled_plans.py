#!/usr/bin/env python3
import json, os, subprocess, sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
HUB_DIR = Path(os.environ.get("HUB_DIR", str(WORK_DIR)))
PLANS_FILE = HUB_DIR / "scheduled_plans.json"


def now_hhmm() -> str:
    return datetime.now().strftime("%H:%M")


def _notify_failure(slug: str) -> None:
    notify = WORK_DIR / "scripts" / "telegram_notify.py"
    subprocess.run(
        [sys.executable, str(notify), "--bot", "brain", f"❌ Plan {slug} fehlgeschlagen"],
        timeout=10,
        capture_output=True,
    )


def _notify_start(slug: str) -> None:
    notify = WORK_DIR / "scripts" / "telegram_notify.py"
    subprocess.run(
        [sys.executable, str(notify), "--bot", "brain", f"🚀 Starte Implementierung: {slug}"],
        timeout=10,
        capture_output=True,
    )


def _notify_success(slug: str) -> None:
    notify = WORK_DIR / "scripts" / "telegram_notify.py"
    subprocess.run(
        [sys.executable, str(notify), "--bot", "brain", f"✅ Implementierung abgeschlossen: {slug}"],
        timeout=10,
        capture_output=True,
    )


def main() -> None:
    try:
        plans: list = json.loads(PLANS_FILE.read_text())
    except Exception:
        return

    now = now_hhmm()

    for entry in plans:
        if entry.get("status") != "pending":
            continue
        scheduled = entry.get("scheduled_time")
        if not scheduled or scheduled > now:
            continue

        entry["status"] = "running"
        PLANS_FILE.write_text(json.dumps(plans, indent=2))

        plan_path = HUB_DIR / entry.get("plan_path", "")
        slug = entry.get("slug", str(plan_path))
        _notify_start(slug)
        try:
            result = subprocess.run(
                [
                    "claude",
                    "--allowedTools", "Bash,Read,Write,Edit,Grep,Glob",
                    "-p", f"@{plan_path}",
                ],
                cwd=str(HUB_DIR),
                timeout=3600,
            )
            entry["status"] = "done" if result.returncode == 0 else "failed"
            if entry["status"] == "done":
                _notify_success(slug)
            else:
                _notify_failure(entry.get("slug", str(plan_path)))
        except Exception:
            entry["status"] = "failed"
            _notify_failure(entry.get("slug", str(plan_path)))

        PLANS_FILE.write_text(json.dumps(plans, indent=2))


if __name__ == "__main__":
    main()

import os, sys, json
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
SETTINGS_PATH = WORK_DIR / "settings.json"
SESSIONS_DIR = WORK_DIR / "dev_sessions"

sys.path.insert(0, str(PROJECT_DIR))
from core.atomic_json import atomic_update, atomic_write


def require_session_id():
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid:
        print("ERROR: CLAUDE_CODE_SESSION_ID not set", file=sys.stderr)
        sys.exit(1)
    return sid


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: set_session.py dev <slug> | set_session.py clear", file=sys.stderr)
        sys.exit(1)

    sid = require_session_id()
    session_path = SESSIONS_DIR / f"{sid}.json"

    if args[0] == "clear":
        atomic_update(SETTINGS_PATH, lambda s: {**s, "active_session": None})
        session_path.unlink(missing_ok=True)
    elif args[0] == "dev":
        if len(args) < 2:
            print("Usage: set_session.py dev <slug>", file=sys.stderr)
            sys.exit(1)
        atomic_update(SETTINGS_PATH, lambda s: {**s, "active_session": "dev"})
        # Read-merge: preserve worktree bookkeeping + implementation_mode that
        # implement.md wrote via Edit tool (LEARNINGS 2026-07-07). session_path
        # is per-sid unique -> atomic_write (no lock needed).
        data = {}
        if session_path.exists():
            try:
                data = json.loads(session_path.read_text())
            except Exception:
                data = {}
        data["active_dev_slug"] = args[1]
        data.setdefault("implementation_mode", False)
        data.setdefault("implementation_mode_until", None)
        data.setdefault("worktree_path", None)
        data.setdefault("branch", None)
        data.setdefault("worktree_base_dir", None)
        atomic_write(session_path, data)
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        sys.exit(1)

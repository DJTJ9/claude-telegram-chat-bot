import os, sys, json
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
SETTINGS_PATH = WORK_DIR / "settings.json"
SESSIONS_DIR = WORK_DIR / "dev_sessions"


def load_settings():
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text())
        except Exception:
            pass
    return {}


def save_settings(data):
    SETTINGS_PATH.write_text(json.dumps(data, indent=2))


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
        s = load_settings()
        s["active_session"] = None
        save_settings(s)
        session_path.unlink(missing_ok=True)
    elif args[0] == "dev":
        if len(args) < 2:
            print("Usage: set_session.py dev <slug>", file=sys.stderr)
            sys.exit(1)
        s = load_settings()
        s["active_session"] = "dev"
        save_settings(s)
        SESSIONS_DIR.mkdir(exist_ok=True)
        # Read-merge: preserve worktree bookkeeping + implementation_mode that
        # implement.md wrote via Edit tool. Overwriting them here wiped the
        # worktree fields finish.md's merge/cleanup relies on and silently
        # killed implementation_mode mid-run (LEARNINGS 2026-07-07).
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
        session_path.write_text(json.dumps(data, indent=2))
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        sys.exit(1)

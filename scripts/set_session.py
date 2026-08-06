import os, sys, json
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
SESSIONS_DIR = WORK_DIR / "dev_sessions"

sys.path.insert(0, str(PROJECT_DIR))
from core.atomic_json import atomic_write


def require_session_id():
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid:
        print("ERROR: CLAUDE_CODE_SESSION_ID not set", file=sys.stderr)
        sys.exit(1)
    return sid


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: set_session.py dev <slug> [<feature-kebab>] | set_session.py clear",
              file=sys.stderr)
        sys.exit(1)

    sid = require_session_id()
    session_path = SESSIONS_DIR / f"{sid}.json"

    if args[0] == "clear":
        # K4: nur die EIGENE Session-Bindung löschen — settings.json (und damit
        # das Routing fremder Sessions) bleibt unberührt.
        session_path.unlink(missing_ok=True)
    elif args[0] == "dev":
        if len(args) < 2:
            print("Usage: set_session.py dev <slug> [<feature-kebab>]", file=sys.stderr)
            sys.exit(1)
        # Read-merge: preserve worktree bookkeeping + implementation_mode that
        # implement.md wrote via Edit tool (LEARNINGS 2026-07-07). session_path
        # is per-sid unique -> atomic_write (no lock needed).
        data = {}
        if session_path.exists():
            try:
                data = json.loads(session_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["active_dev_slug"] = args[1]
        if len(args) >= 3:
            data["active_dev_feature"] = args[2]
        else:
            data.setdefault("active_dev_feature", None)
        data.setdefault("implementation_mode", False)
        data.setdefault("implementation_mode_until", None)
        data.setdefault("worktree_path", None)
        data.setdefault("branch", None)
        data.setdefault("worktree_base_dir", None)
        atomic_write(session_path, data)
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        sys.exit(1)

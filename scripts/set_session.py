import os, sys, json
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
WORK_DIR = Path(os.environ.get("WORK_DIR", str(PROJECT_DIR)))
SETTINGS_PATH = WORK_DIR / "settings.json"


def load():
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text())
        except Exception:
            pass
    return {}


def save(data):
    SETTINGS_PATH.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: set_session.py dev <slug> | set_session.py clear", file=sys.stderr)
        sys.exit(1)

    s = load()

    if args[0] == "clear":
        s["active_session"] = None
        s["active_dev_slug"] = None
        save(s)
    elif args[0] == "dev":
        if len(args) < 2:
            print("Usage: set_session.py dev <slug>", file=sys.stderr)
            sys.exit(1)
        s["active_session"] = "dev"
        s["active_dev_slug"] = args[1]
        save(s)
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        sys.exit(1)

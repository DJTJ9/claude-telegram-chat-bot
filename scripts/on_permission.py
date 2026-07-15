import os, sys, json
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

# Load .env manually
env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
if session_id:
    session_path = PROJECT_DIR / "dev_sessions" / f"{session_id}.json"
    if session_path.exists():
        try:
            sdata = json.loads(session_path.read_text())
            impl_mode = sdata.get("implementation_mode", False)
            impl_until = sdata.get("implementation_mode_until")
            if impl_mode and impl_until:
                try:
                    if datetime.now() < datetime.fromisoformat(impl_until):
                        print(json.dumps({"decision": "approve"}))
                        sys.exit(0)
                except (ValueError, TypeError):
                    pass  # malformed timestamp → fall through
        except Exception:
            pass

try:
    data = json.loads(sys.stdin.read())
except Exception:
    print(json.dumps({"decision": "block", "reason": "Hook received unparseable input"}))
    sys.exit(2)

tool_name = data.get("tool_name", "Unknown")
tool_input = data.get("tool_input", {})

# Auto-approve Edit/Write for files inside the project directory
if tool_name in ("Edit", "Write"):
    file_path_str = tool_input.get("file_path", "")
    try:
        Path(file_path_str).resolve().relative_to(PROJECT_DIR.resolve())
        print(json.dumps({"decision": "approve"}))
        sys.exit(0)
    except ValueError:
        pass

# Kein Auto-Approve-Treffer: keine Ausgabe → Claude Code fragt im Terminal.
sys.exit(0)

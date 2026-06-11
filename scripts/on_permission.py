import os, sys, json, time, uuid
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

settings_path = PROJECT_DIR / "settings.json"
if settings_path.exists():
    try:
        settings = json.loads(settings_path.read_text())
        if not settings.get("notifications_enabled", True):
            print(json.dumps({"decision": "approve"}))
            sys.exit(0)
    except Exception:
        pass

try:
    data = json.loads(sys.stdin.read())
except Exception:
    print(json.dumps({"decision": "approve"}))
    sys.exit(0)

request_id = str(uuid.uuid4())[:8]
tool_name = data.get("tool_name", "Unknown")
tool_input = data.get("tool_input", {})

pending_path = PROJECT_DIR / "pending_permission.json"
pending_path.write_text(json.dumps({
    "tool": tool_name,
    "input": tool_input,
    "request_id": request_id,
}))

response_path = PROJECT_DIR / f"permission_response_{request_id}.json"
timeout = 300
start = time.time()

while time.time() - start < timeout:
    if response_path.exists():
        try:
            resp = json.loads(response_path.read_text())
            response_path.unlink()
        except Exception:
            time.sleep(0.1)
            continue
        if resp.get("approved"):
            print(json.dumps({"decision": "approve"}))
            sys.exit(0)
        else:
            print(json.dumps({"decision": "block", "reason": "Denied via Telegram"}))
            sys.exit(2)
    time.sleep(0.5)

# Timeout — auto-approve, clean up
pending_path.unlink(missing_ok=True)
print(json.dumps({"decision": "approve"}))
sys.exit(0)

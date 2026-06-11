import os, sys, json, time, uuid
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

settings_path = PROJECT_DIR / "settings.json"
try:
    settings = json.loads(settings_path.read_text())
except Exception:
    settings = {}

if not settings.get("notifications_enabled", True):
    print("telegram_ask: notifications_enabled is false — relay not active", file=sys.stderr)
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: telegram_ask.py <question>", file=sys.stderr)
    sys.exit(1)

question = sys.argv[1]
request_id = str(uuid.uuid4())[:8]

pending_path = PROJECT_DIR / "pending_question.json"
pending_path.write_text(json.dumps({
    "question": question,
    "request_id": request_id,
}))

response_path = PROJECT_DIR / f"question_response_{request_id}.json"
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
        print(resp.get("answer", "A"))
        sys.exit(0)
    time.sleep(0.5)

pending_path.unlink(missing_ok=True)
print("A")
sys.exit(0)

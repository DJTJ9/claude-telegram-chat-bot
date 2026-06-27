#!/usr/bin/env python3
import json, os, sys, time, uuid, re
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(PROJECT_DIR))
from core.settings import load_settings

TIMEOUT = 900

settings = load_settings()
if not settings.get("notifications_enabled", True):
    print("A")
    sys.exit(0)

if len(sys.argv) < 2:
    print("Usage: telegram_ask.py <question>", file=sys.stderr)
    sys.exit(1)

question = sys.argv[1]
request_id = str(uuid.uuid4())[:8]
pending_path = PROJECT_DIR / "pending_question.json"
response_path = PROJECT_DIR / f"question_response_{request_id}.json"

_options = []
_opt_matches = re.findall(r'\b([A-D])\)\s*(.+?)(?=\s*\b[A-D]\)|\s*$)', question, re.DOTALL)
if _opt_matches:
    _options = [f"{letter}) {text.strip()}" for letter, text in _opt_matches]

pending_path.write_text(json.dumps({
    "question": question,
    "text": question,
    "options": _options,
    "request_id": request_id,
    "target_bot": "brain",
}))

deadline = time.time() + TIMEOUT
while time.time() < deadline:
    if response_path.exists():
        try:
            resp = json.loads(response_path.read_text())
            response_path.unlink(missing_ok=True)
        except Exception:
            time.sleep(0.1)
            continue
        pending_path.unlink(missing_ok=True)
        print(resp.get("answer", "A"))
        sys.exit(0)
    time.sleep(1)

pending_path.unlink(missing_ok=True)
sys.exit(1)

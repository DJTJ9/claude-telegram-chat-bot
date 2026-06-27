#!/usr/bin/env python3
import json, os, re, sys, time, uuid
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
TIMEOUT = float(os.environ.get("_DUAL_ASK_TIMEOUT", "60"))
POLL_INTERVAL = 0.2

if len(sys.argv) < 2:
    print("USE_CC")
    sys.exit(0)

question = sys.argv[1]
request_id = str(uuid.uuid4())[:8]
pending_path = WORK_DIR / "pending_question.json"
response_path = WORK_DIR / f"question_response_{request_id}.json"

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
        print(resp.get("answer", "USE_CC"))
        sys.exit(0)
    time.sleep(POLL_INTERVAL)

pending_path.unlink(missing_ok=True)
print("USE_CC")
sys.exit(0)

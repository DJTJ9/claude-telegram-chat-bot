import os, sys, json, time, uuid, requests
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
from core.telegram import build_inline_keyboard
from core.routing import _get_target_bot_name, get_chat_id

settings = load_settings()

if not settings.get("notifications_enabled", True):
    print("telegram_ask: notifications_enabled is false", file=sys.stderr)
    sys.exit(1)

_HUB_DIR = os.environ.get("HUB_DIR", "")
_signal_path = Path(_HUB_DIR) / ".vision_end" if _HUB_DIR else None

def _check_signal():
    if _signal_path and _signal_path.exists():
        _signal_path.unlink()
        print("vision:end")
        sys.exit(0)

_check_signal()

if len(sys.argv) < 2:
    print("Usage: telegram_ask.py <question>", file=sys.stderr)
    sys.exit(1)

question = sys.argv[1]
request_id = str(uuid.uuid4())[:8]
chat_id = get_chat_id()

active_session = settings.get("active_session")
bot_name = _get_target_bot_name(active_session)
token_key = f"TOKEN_{bot_name.upper()}"
token = os.environ.get(token_key)
if not token:
    print(f"telegram_ask: token {token_key} not set", file=sys.stderr)
    sys.exit(1)

pending_path = PROJECT_DIR / "pending_question.json"
pending_path.write_text(json.dumps({
    "question": question,
    "request_id": request_id,
    "target_bot": bot_name,
}))

keyboard = build_inline_keyboard(question)
requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json={"chat_id": chat_id, "text": f"❓ {question}",
          "reply_markup": {"inline_keyboard": keyboard}},
)

response_path = PROJECT_DIR / f"question_response_{request_id}.json"
timeout = 300
start = time.time()
_last_signal_check = time.time()

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
    if time.time() - _last_signal_check >= 5:
        _check_signal()
        _last_signal_check = time.time()
    time.sleep(0.5)

pending_path.unlink(missing_ok=True)
print("A")
sys.exit(0)

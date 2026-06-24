import os, sys, json, time, threading
from pathlib import Path

os.environ.setdefault("TOKEN_BRAIN", "test_token")
os.environ.setdefault("CHAT_ID", "12345")
sys.path.insert(0, str(Path(__file__).parent.parent))

PROJECT_DIR = Path(__file__).parent.parent


def _run_and_answer(question, answer="B", answer_delay=0.5):
    import subprocess
    def write_answer():
        pq = PROJECT_DIR / "pending_question.json"
        deadline = time.time() + 5
        while time.time() < deadline:
            if pq.exists():
                data = json.loads(pq.read_text())
                req_id = data["request_id"]
                time.sleep(answer_delay)
                (PROJECT_DIR / f"question_response_{req_id}.json").write_text(
                    json.dumps({"answer": answer})
                )
                return
            time.sleep(0.05)
    threading.Thread(target=write_answer, daemon=True).start()
    return subprocess.run(
        [sys.executable, str(PROJECT_DIR / "scripts" / "telegram_ask.py"), question],
        capture_output=True, text=True, timeout=15,
    )


def test_telegram_ask_returns_answer():
    result = _run_and_answer("Frage?\nA) Eins\nB) Zwei", answer="A")
    assert result.returncode == 0
    assert result.stdout.strip() == "A"

def test_telegram_ask_cleans_up_files():
    _run_and_answer("Test?\nA) Ja\nB) Nein", answer="B")
    assert not (PROJECT_DIR / "pending_question.json").exists()

def test_telegram_ask_no_session_manager_import():
    src = (PROJECT_DIR / "scripts" / "telegram_ask.py").read_text()
    assert "session_manager" not in src

def test_telegram_ask_no_direct_sendmessage():
    src = (PROJECT_DIR / "scripts" / "telegram_ask.py").read_text()
    assert "sendMessage" not in src

def test_telegram_ask_timeout_is_900():
    src = (PROJECT_DIR / "scripts" / "telegram_ask.py").read_text()
    assert "900" in src

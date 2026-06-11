import sys, os, json, subprocess, threading, time
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "telegram_ask.py"


def test_notifications_off_exits_1():
    settings_path = PROJECT_DIR / "settings.json"
    original = settings_path.read_text()
    settings_path.write_text(json.dumps({"notifications_enabled": False}))
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "Test question?"],
            capture_output=True, text=True, timeout=5
        )
        assert result.returncode == 1
    finally:
        settings_path.write_text(original)


def test_returns_answer_from_response_file():
    settings_path = PROJECT_DIR / "settings.json"
    original = settings_path.read_text()
    settings_path.write_text(json.dumps({"notifications_enabled": True}))

    def write_response():
        for _ in range(40):
            pq = PROJECT_DIR / "pending_question.json"
            if pq.exists():
                req_id = json.loads(pq.read_text())["request_id"]
                (PROJECT_DIR / f"question_response_{req_id}.json").write_text(
                    json.dumps({"answer": "B"})
                )
                return
            time.sleep(0.1)

    t = threading.Thread(target=write_response)
    t.start()

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "A) opt1 B) opt2?"],
            capture_output=True, text=True, timeout=10
        )
        assert result.stdout.strip() == "B"
        assert result.returncode == 0
    finally:
        settings_path.write_text(original)
        t.join(timeout=2)

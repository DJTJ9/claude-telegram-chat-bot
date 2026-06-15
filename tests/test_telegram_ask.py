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
    # Clean up any stale files from previous runs
    stale_pq = PROJECT_DIR / "pending_question.json"
    if stale_pq.exists():
        stale_pq.unlink()
    settings_path.write_text(json.dumps({"notifications_enabled": True}))

    def write_response():
        for _ in range(200):  # 20s window — handles slow Python startup under full suite load
            pq = PROJECT_DIR / "pending_question.json"
            if pq.exists():
                try:
                    req_id = json.loads(pq.read_text())["request_id"]
                    (PROJECT_DIR / f"question_response_{req_id}.json").write_text(
                        json.dumps({"answer": "B"})
                    )
                    return
                except Exception:
                    pass
            time.sleep(0.1)

    t = threading.Thread(target=write_response)
    t.start()

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "A) opt1 B) opt2?"],
            capture_output=True, text=True, timeout=25
        )
        assert result.stdout.strip() == "B"
        assert result.returncode == 0
    finally:
        settings_path.write_text(original)
        t.join(timeout=3)


def test_signal_file_triggers_vision_end(tmp_path):
    """Signal file causes telegram_ask to print 'vision:end' and exit 0."""
    signal_file = tmp_path / ".vision_end"
    signal_file.write_text("end")

    settings_path = PROJECT_DIR / "settings.json"
    original = settings_path.read_text()
    settings_path.write_text(json.dumps({"notifications_enabled": True}))

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "Irgendeine Frage?"],
            capture_output=True, text=True, timeout=5,
            env={**os.environ, "HUB_DIR": str(tmp_path)},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "vision:end"
        assert not signal_file.exists()
    finally:
        settings_path.write_text(original)

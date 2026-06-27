import sys, json, os, subprocess, time
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
SCRIPT = PROJECT_DIR / "scripts" / "dual_ask.py"
WORK_DIR = Path(os.environ["WORK_DIR"])


def test_outputs_answer_when_response_written():
    """Outputs answer letter when response file appears within timeout."""
    pending_path = WORK_DIR / "pending_question.json"
    pending_path.unlink(missing_ok=True)

    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "Test? A) Ja B) Nein"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={**os.environ, "_DUAL_ASK_TIMEOUT": "10"},
    )

    deadline = time.time() + 5
    while time.time() < deadline and not pending_path.exists():
        time.sleep(0.05)
    assert pending_path.exists(), "pending_question.json not written"

    data = json.loads(pending_path.read_text())
    request_id = data["request_id"]
    response_path = WORK_DIR / f"question_response_{request_id}.json"
    response_path.write_text(json.dumps({"answer": "B"}))

    stdout, _ = proc.communicate(timeout=5)
    assert stdout.strip() == "B"


def test_outputs_use_cc_on_timeout():
    """Outputs USE_CC when no response arrives within timeout."""
    pending_path = WORK_DIR / "pending_question.json"
    pending_path.unlink(missing_ok=True)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "Test? A) Ja B) Nein"],
        capture_output=True, text=True, timeout=5,
        env={**os.environ, "_DUAL_ASK_TIMEOUT": "0.3"},
    )
    assert result.stdout.strip() == "USE_CC"
    assert not pending_path.exists()


def test_writes_parsed_options():
    """pending_question.json contains parsed options list."""
    pending_path = WORK_DIR / "pending_question.json"
    pending_path.unlink(missing_ok=True)

    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "Wähle? A) Alpha B) Beta C) Gamma"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={**os.environ, "_DUAL_ASK_TIMEOUT": "10"},
    )

    deadline = time.time() + 5
    while time.time() < deadline and not pending_path.exists():
        time.sleep(0.05)
    assert pending_path.exists()

    data = json.loads(pending_path.read_text())
    assert len(data["options"]) == 3
    assert data["options"][0].startswith("A)")

    proc.terminate()
    proc.wait(timeout=2)
    pending_path.unlink(missing_ok=True)

import os, sys
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("TOKEN_BRAIN", "test_token")
os.environ.setdefault("CHAT_ID", "12345")
os.environ.setdefault("GROQ_API_KEY", "x")
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_get_dev_status_full_parses_epics_and_counts(tmp_path):
    import bots.brain as brain
    status_md = tmp_path / "topics" / "proj" / "STATUS.md"
    status_md.parent.mkdir(parents=True)
    status_md.write_text(
        "# Project Status\n"
        "Active: Brain Bot: Fix X\n"
        "Phase: plan\n"
        "## Roadmap\n"
        "- [idea]      Brain Bot: Feature A\n"
        "- [idea]      NocoDB: Feature B\n"
        "- [done]       Brain Bot: Feature C\n"
    )
    with patch.object(brain, "HUB_DIR", tmp_path):
        result = brain._get_dev_status_full("proj")
    assert "Brain Bot: Fix X" in result
    assert "Brain Bot" in result
    assert "NocoDB" in result
    assert "1 offen" in result
    assert "1 done" in result


def test_get_dev_status_full_next_5_in_order(tmp_path):
    import bots.brain as brain
    status_md = tmp_path / "topics" / "proj" / "STATUS.md"
    status_md.parent.mkdir(parents=True)
    lines = ["# Project Status\nActive: X\nPhase: plan\n## Roadmap\n"]
    for i in range(7):
        lines.append(f"- [idea]      Feature {i}\n")
    lines.append("- [done]       Done Feature\n")
    status_md.write_text("".join(lines))
    with patch.object(brain, "HUB_DIR", tmp_path):
        result = brain._get_dev_status_full("proj")
    assert "Feature 4" in result
    assert "Feature 5" not in result


def test_get_dev_status_full_no_status_md(tmp_path):
    import bots.brain as brain
    (tmp_path / "topics" / "proj").mkdir(parents=True)
    with patch.object(brain, "HUB_DIR", tmp_path):
        result = brain._get_dev_status_full("proj")
    assert "nicht gefunden" in result


def test_status_callback_sends_message(tmp_path):
    import bots.brain as brain
    status_md = tmp_path / "topics" / "myslug" / "STATUS.md"
    status_md.parent.mkdir(parents=True)
    status_md.write_text("# P\nActive: X\nPhase: plan\n## Roadmap\n")
    with patch.object(brain, "HUB_DIR", tmp_path), \
         patch("bots.brain.send_message") as mock_send, \
         patch("bots.brain.answer_callback_query") as mock_ack:
        brain._handle_callback({"id": "cq1", "data": "status:myslug"})
    mock_send.assert_called_once()
    sent_text = mock_send.call_args[0][2]
    assert "Dev Status" in sent_text
    mock_ack.assert_called_once()


def test_run_bug_summary_parses_groq_response():
    import bots.brain as brain
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = (
        "TITEL: chunk_retry Handler fehlt\n"
        "BESCHREIBUNG: Der Button wird gesendet aber kein Handler existiert."
    )
    with patch.object(brain, "_groq_client") as mock_groq:
        mock_groq.return_value.chat.completions.create.return_value = mock_resp
        result = brain._run_bug_summary("chunk_retry callback missing")
    assert result["title"] == "Bug: chunk_retry Handler fehlt"
    assert "Handler" in result["summary"]


def test_run_bug_summary_fallback_on_bad_format():
    import bots.brain as brain
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "Some unstructured text"
    with patch.object(brain, "_groq_client") as mock_groq:
        mock_groq.return_value.chat.completions.create.return_value = mock_resp
        result = brain._run_bug_summary("something broke")
    assert result["title"].startswith("Bug: ")
    assert isinstance(result["summary"], str)

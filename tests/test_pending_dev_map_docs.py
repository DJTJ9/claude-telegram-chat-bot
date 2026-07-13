"""Nagelt fest, dass die dev-Skill-Handoff-Docs das pending_dev-MAP-Format schreiben
(Bug: pending_dev nicht multi-session-fähig, 2026-07-13). Reine String-Assertions auf
den Dateiinhalt — konsistent mit test_skill_files_updated.py."""
from pathlib import Path

CLAUDE = Path("/root/.claude")
PHASES = CLAUDE / "skills/dev/phases"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_continuation_uses_slug_keyed_map():
    txt = _read(PHASES / "_continuation.md")
    # Map-Format: pending_dev enthält einen <slug>-Key, unter dem command liegt.
    assert '"pending_dev": {' in txt
    assert '"<SLUG>": {' in txt
    # Anweisung, nur den eigenen Slug-Key zu setzen.
    assert "nur den eigenen Slug-Key" in txt or "nur den eigenen slug-key" in txt.lower()


def test_plan_autopilot_payload_is_map():
    txt = _read(PHASES / "plan.md")
    assert '"<SLUG>": {' in txt
    assert '"command": "/dev implement"' in txt


def test_implement_payload_is_map():
    txt = _read(PHASES / "implement.md")
    assert '"<SLUG>": {' in txt
    assert '"command": "/dev finish"' in txt


def test_finish_payload_is_map():
    txt = _read(PHASES / "finish.md")
    assert '"<SLUG>": {' in txt
    assert '"command": "/dev active <SLUG>"' in txt


def test_claude_md_describes_hook_side_consume():
    txt = _read(CLAUDE / "CLAUDE.md")
    # Delete-Schritt: Hook konsumiert im Normalfall selbst, Session nur im LIST-/Legacy-Fall.
    assert "Hook" in txt and "pending_dev" in txt
    assert "LIST" in txt or "list-mode" in txt.lower() or "Mehrfach" in txt

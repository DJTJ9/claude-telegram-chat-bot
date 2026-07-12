from pathlib import Path

SKILL_MD = Path("/root/.claude/skills/dev/SKILL.md").read_text()


def test_skill_md_step1_keeps_full_session_object():
    assert '"spec": ..., "plan": ..., "features"' in SKILL_MD
    assert "<SESSION_DATA>" in SKILL_MD

from pathlib import Path

SKILL_MD = Path("/root/.claude/skills/dev/SKILL.md").read_text()


def test_skill_md_step1_keeps_full_session_object():
    assert '"spec": ..., "plan": ..., "features"' in SKILL_MD
    assert "<SESSION_DATA>" in SKILL_MD


PLAN_MD = Path("/root/.claude/skills/dev/phases/plan.md").read_text()


def test_plan_md_shortcut_reuses_session_data():
    assert "Wenn Step 1 `<SESSION_DATA>` geliefert hat" in PLAN_MD
    assert "kein erneutes `Read STATUS.md`" in PLAN_MD
    assert "If Phase=`plan` and Spec field is set" in PLAN_MD


IMPLEMENT_MD = Path("/root/.claude/skills/dev/phases/implement.md").read_text()


def test_implement_md_shortcut_reuses_session_data():
    assert "Wenn Step 1 `<SESSION_DATA>` geliefert hat" in IMPLEMENT_MD
    assert "kein erneutes `Read STATUS.md`" in IMPLEMENT_MD
    assert "If Phase=`implement` and Plan field is set" in IMPLEMENT_MD

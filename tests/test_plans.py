import sys, os, json, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pathlib import Path
from unittest.mock import patch

def test_load_plans_missing_file(tmp_path):
    with patch("bot.PLANS_PATH", tmp_path / "scheduled_plans.json"):
        from bot import _load_plans
        assert _load_plans() == []

def test_load_plans_existing(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([{"slug": "test", "plan_path": "docs/test.md", "scheduled_time": "02:00", "status": "pending"}]))
    with patch("bot.PLANS_PATH", p):
        from bot import _load_plans
        result = _load_plans()
        assert len(result) == 1
        assert result[0]["slug"] == "test"

def test_save_and_reload_plans(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text("[]")
    plans = [{"slug": "x", "plan_path": "docs/x.md", "scheduled_time": None, "status": "pending"}]
    with patch("bot.PLANS_PATH", p):
        from bot import _save_plans, _load_plans
        _save_plans(plans)
        assert _load_plans() == plans

def test_set_plan_status(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "alpha", "plan_path": "docs/alpha.md", "scheduled_time": "02:00", "status": "pending"}
    ]))
    with patch("bot.PLANS_PATH", p), patch("subprocess.run"):
        from bot import _set_plan_status, _load_plans
        _set_plan_status("alpha", "running")
        result = _load_plans()
        assert result[0]["status"] == "running"

def test_run_plan_success(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "alpha", "plan_path": "docs/superpowers/plans/alpha.md", "scheduled_time": "02:00", "status": "pending"}
    ]))
    sent = []
    with patch("bot.PLANS_PATH", p), \
         patch("subprocess.run") as mock_run, \
         patch("bot.send_message", lambda chat_id, text, **kw: sent.append(text)):
        mock_run.return_value = type("R", (), {"returncode": 0, "stderr": ""})()
        from bot import _run_plan
        _run_plan("docs/superpowers/plans/alpha.md", slug="alpha")
    assert any("abgeschlossen" in m for m in sent)

def test_run_plan_failure_retries(tmp_path):
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "beta", "plan_path": "docs/superpowers/plans/beta.md", "scheduled_time": "02:00", "status": "pending"}
    ]))
    sent = []
    call_count = {"n": 0}
    def mock_run(cmd, **kw):
        if isinstance(cmd, list) and cmd and cmd[0] == "claude":
            call_count["n"] += 1
            return type("R", (), {"returncode": 1, "stderr": "error msg"})()
        return type("R", (), {"returncode": 0, "stderr": ""})()
    with patch("bot.PLANS_PATH", p), \
         patch("subprocess.run", mock_run), \
         patch("bot.send_message", lambda chat_id, text, **kw: sent.append(text)):
        from bot import _run_plan
        _run_plan("docs/superpowers/plans/beta.md", slug="beta")
    assert call_count["n"] == 2
    assert any("fehlgeschlagen" in m for m in sent)

def test_plan_loop_fires_on_matching_time(tmp_path):
    import bot
    p = tmp_path / "scheduled_plans.json"
    p.write_text(json.dumps([
        {"slug": "gamma", "plan_path": "docs/gamma.md", "scheduled_time": "03:00", "status": "pending"}
    ]))
    triggered = []
    with patch("bot.PLANS_PATH", p), \
         patch("bot.send_message"), \
         patch("bot._run_plan", lambda path, slug: triggered.append(slug)):
        plans = bot._load_plans()
        now = "03:00"
        for plan in plans:
            if plan["status"] == "pending" and plan.get("scheduled_time") == now:
                bot._run_plan(plan["plan_path"], slug=plan["slug"])
    assert "gamma" in triggered

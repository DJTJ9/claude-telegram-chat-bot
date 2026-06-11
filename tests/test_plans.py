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

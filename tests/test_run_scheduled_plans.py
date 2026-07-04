import os, sys, json
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("WORK_DIR", str(Path(__file__).parent.parent))
os.environ.setdefault("HUB_DIR", "/root/projects-hub")
sys.path.insert(0, str(Path(__file__).parent.parent))


def make_plans_file(tmp_path, entries):
    f = tmp_path / "scheduled_plans.json"
    f.write_text(json.dumps(entries))
    return f


def test_skips_non_pending_entries(tmp_path):
    plans_file = make_plans_file(tmp_path, [
        {"slug": "x", "plan_path": "p.md", "scheduled_time": "00:01", "status": "done"},
        {"slug": "y", "plan_path": "p.md", "scheduled_time": "00:01", "status": "running"},
    ])
    import scripts.run_scheduled_plans as rsp
    with patch.object(rsp, "PLANS_FILE", plans_file), \
         patch("scripts.run_scheduled_plans.subprocess") as mock_sub:
        rsp.main()
    mock_sub.run.assert_not_called()


def test_skips_future_scheduled_time(tmp_path):
    plans_file = make_plans_file(tmp_path, [
        {"slug": "x", "plan_path": "p.md", "scheduled_time": "23:59", "status": "pending"},
    ])
    import scripts.run_scheduled_plans as rsp
    with patch.object(rsp, "PLANS_FILE", plans_file), \
         patch("scripts.run_scheduled_plans.now_hhmm", return_value="00:01"), \
         patch("scripts.run_scheduled_plans.subprocess") as mock_sub:
        rsp.main()
    mock_sub.run.assert_not_called()


def test_executes_pending_past_time(tmp_path):
    hub = tmp_path / "hub"
    hub.mkdir()
    plans_file = make_plans_file(tmp_path, [
        {"slug": "myplan", "plan_path": "topics/proj/plans/plan.md",
         "scheduled_time": "10:00", "status": "pending"},
    ])
    import scripts.run_scheduled_plans as rsp
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch.object(rsp, "PLANS_FILE", plans_file), \
         patch.object(rsp, "HUB_DIR", hub), \
         patch("scripts.run_scheduled_plans.now_hhmm", return_value="10:01"), \
         patch("scripts.run_scheduled_plans.subprocess") as mock_sub:
        mock_sub.run.return_value = mock_result
        rsp.main()
    claude_calls = [c for c in mock_sub.run.call_args_list if "claude" in c[0][0]]
    assert len(claude_calls) == 1
    plans = json.loads(plans_file.read_text())
    assert plans[0]["status"] == "done"


def test_sets_failed_and_notifies_on_nonzero_returncode(tmp_path):
    hub = tmp_path / "hub"
    hub.mkdir()
    plans_file = make_plans_file(tmp_path, [
        {"slug": "myplan", "plan_path": "topics/proj/plans/plan.md",
         "scheduled_time": "10:00", "status": "pending"},
    ])
    import scripts.run_scheduled_plans as rsp
    mock_result = MagicMock()
    mock_result.returncode = 1
    with patch.object(rsp, "PLANS_FILE", plans_file), \
         patch.object(rsp, "HUB_DIR", hub), \
         patch("scripts.run_scheduled_plans.now_hhmm", return_value="10:01"), \
         patch("scripts.run_scheduled_plans.subprocess") as mock_sub:
        mock_sub.run.return_value = mock_result
        rsp.main()
    plans = json.loads(plans_file.read_text())
    assert plans[0]["status"] == "failed"
    notify_calls = [str(c) for c in mock_sub.run.call_args_list]
    assert any("telegram_notify" in c for c in notify_calls)


def test_notifies_start_and_success(tmp_path):
    hub = tmp_path / "hub"
    hub.mkdir()
    plans_file = make_plans_file(tmp_path, [
        {"slug": "myplan", "plan_path": "topics/proj/plans/plan.md",
         "scheduled_time": "10:00", "status": "pending"},
    ])
    import scripts.run_scheduled_plans as rsp
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch.object(rsp, "PLANS_FILE", plans_file), \
         patch.object(rsp, "HUB_DIR", hub), \
         patch("scripts.run_scheduled_plans.now_hhmm", return_value="10:01"), \
         patch("scripts.run_scheduled_plans.subprocess") as mock_sub:
        mock_sub.run.return_value = mock_result
        rsp.main()
    notify_calls = [str(c) for c in mock_sub.run.call_args_list]
    assert sum("telegram_notify" in c for c in notify_calls) == 2
    assert any("Starte" in c for c in notify_calls)
    assert any("abgeschlossen" in c for c in notify_calls)

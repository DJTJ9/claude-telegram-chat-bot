import json
import os
import subprocess
from pathlib import Path

HUB_DIR = os.environ.get("HUB_DIR", "")
SCRIPT = f"{HUB_DIR}/scripts/dev_context.py"


def _run(hub, *args, env_extra=None):
    env = {**os.environ, "HUB_DIR": str(hub), **(env_extra or {})}
    return subprocess.run(
        ["python3", SCRIPT, *args],
        capture_output=True, text=True, env=env, timeout=5,
    )


def _make_hub(tmp_path):
    (tmp_path / "topics" / "proj").mkdir(parents=True)
    (tmp_path / "projects-registry.json").write_text("[]", encoding="utf-8")
    return tmp_path


class TestFeatureSet:
    def test_create_writes_skeleton_with_name_and_fields(self, tmp_path):
        hub = _make_hub(tmp_path)
        r = _run(hub, "--command", "feature-set", "--slug", "proj",
                 "--feature-key", "email-auth", "--name", "E-Mail Auth",
                 "--set", "Phase=discuss", "--set", "Type=feature")
        assert r.returncode == 0, r.stderr
        text = (hub / "topics" / "proj" / "features" / "email-auth.md").read_text(encoding="utf-8")
        assert text.splitlines()[0] == "# E-Mail Auth"
        assert "Phase: discuss" in text
        assert "Type: feature" in text
        for field in ("Spec", "Plan", "Mode", "Schedule", "Teach",
                      "Lesson", "Worktree", "Branch", "Session"):
            assert f"{field}:" in text
        assert "Updated: " in text  # auto-heute

    def test_update_existing_preserves_other_fields(self, tmp_path):
        hub = _make_hub(tmp_path)
        _run(hub, "--command", "feature-set", "--slug", "proj",
             "--feature-key", "email-auth", "--name", "E-Mail Auth",
             "--set", "Phase=discuss", "--set", "Spec=topics/proj/specs/x.md")
        r = _run(hub, "--command", "feature-set", "--slug", "proj",
                 "--feature-key", "email-auth", "--set", "Phase=plan")
        assert r.returncode == 0, r.stderr
        text = (hub / "topics" / "proj" / "features" / "email-auth.md").read_text(encoding="utf-8")
        assert "Phase: plan" in text
        assert "Spec: topics/proj/specs/x.md" in text
        assert text.splitlines()[0] == "# E-Mail Auth"

    def test_create_without_name_fails(self, tmp_path):
        hub = _make_hub(tmp_path)
        r = _run(hub, "--command", "feature-set", "--slug", "proj",
                 "--feature-key", "neu", "--set", "Phase=discuss")
        assert r.returncode == 1
        assert "--name" in r.stderr

    def test_unknown_field_fails(self, tmp_path):
        hub = _make_hub(tmp_path)
        r = _run(hub, "--command", "feature-set", "--slug", "proj",
                 "--feature-key", "x", "--name", "X", "--set", "Bogus=1")
        assert r.returncode == 1
        assert "Bogus" in r.stderr


class TestFeatureGet:
    def test_get_returns_parsed_json(self, tmp_path):
        hub = _make_hub(tmp_path)
        _run(hub, "--command", "feature-set", "--slug", "proj",
             "--feature-key", "email-auth", "--name", "E-Mail Auth",
             "--set", "Phase=implement", "--set", "Session=sid-1")
        r = _run(hub, "--command", "feature-get", "--slug", "proj",
                 "--feature-key", "email-auth")
        data = json.loads(r.stdout)
        assert data["key"] == "email-auth"
        assert data["name"] == "E-Mail Auth"
        assert data["phase"] == "implement"
        assert data["session"] == "sid-1"

    def test_get_missing_fails_hard(self, tmp_path):
        hub = _make_hub(tmp_path)
        r = _run(hub, "--command", "feature-get", "--slug", "proj",
                 "--feature-key", "nope")
        assert r.returncode == 1


class TestFeatureList:
    def test_list_returns_open_features_newest_first(self, tmp_path):
        hub = _make_hub(tmp_path)
        _run(hub, "--command", "feature-set", "--slug", "proj",
             "--feature-key", "alt", "--name", "Alt", "--set", "Phase=plan")
        _run(hub, "--command", "feature-set", "--slug", "proj",
             "--feature-key", "neu", "--name", "Neu", "--set", "Phase=discuss")
        os.utime(hub / "topics" / "proj" / "features" / "alt.md", (1, 1))
        r = _run(hub, "--command", "feature-list", "--slug", "proj")
        data = json.loads(r.stdout)
        assert [f["key"] for f in data] == ["neu", "alt"]

    def test_list_empty_dir_returns_empty_array(self, tmp_path):
        hub = _make_hub(tmp_path)
        r = _run(hub, "--command", "feature-list", "--slug", "proj")
        assert json.loads(r.stdout) == []

    def test_list_ignores_done_subdir(self, tmp_path):
        hub = _make_hub(tmp_path)
        _run(hub, "--command", "feature-set", "--slug", "proj",
             "--feature-key", "offen", "--name", "Offen", "--set", "Phase=plan")
        done = hub / "topics" / "proj" / "features" / "done"
        done.mkdir()
        (done / "fertig.md").write_text("# Fertig\nPhase: finish\n", encoding="utf-8")
        r = _run(hub, "--command", "feature-list", "--slug", "proj")
        assert [f["key"] for f in json.loads(r.stdout)] == ["offen"]


class TestSessionFeatureBinding:
    def _bound_session(self, tmp_path, feature_key):
        hub = _make_hub(tmp_path)
        (hub / "topics" / "proj" / "STATUS.md").write_text(
            "# Project Status — proj\nUpdated: 2026-08-05\n\n## Roadmap\n- [planned]   E-Mail Auth\n", encoding="utf-8")
        _run(hub, "--command", "feature-set", "--slug", "proj",
             "--feature-key", "email-auth", "--name", "E-Mail Auth",
             "--set", "Phase=implement", "--set", "Plan=topics/proj/plans/p.md")
        work = tmp_path / "work"
        (work / "dev_sessions").mkdir(parents=True)
        (work / "dev_sessions" / "sid-1.json").write_text(json.dumps(
            {"active_dev_slug": "proj", "active_dev_feature": feature_key}), encoding="utf-8")
        r = _run(hub, "--command", "session",
                 env_extra={"WORK_DIR": str(work), "CLAUDE_CODE_SESSION_ID": "sid-1"})
        return json.loads(r.stdout)

    def test_session_overrides_from_feature_file(self, tmp_path):
        data = self._bound_session(tmp_path, "email-auth")
        assert data["feature_key"] == "email-auth"
        assert data["active"] == "E-Mail Auth"
        assert data["phase"] == "implement"
        assert data["plan"] == "topics/proj/plans/p.md"
        assert data["features"] == [{"name": "E-Mail Auth", "status": "planned"}]

    def test_session_without_feature_binding_keeps_old_shape(self, tmp_path):
        data = self._bound_session(tmp_path, None)
        assert data["slug"] == "proj"
        assert "feature_key" not in data or not data["feature_key"]


class TestGoFeatureEnrichment:
    def test_go_reads_spec_plan_phase_from_feature_file(self, tmp_path):
        hub = _make_hub(tmp_path)
        (hub / "projects-registry.json").write_text(
            json.dumps([{"slug": "proj", "name": "Proj", "path": ""}]), encoding="utf-8")
        (hub / "topics" / "proj" / "STATUS.md").write_text(
            "# Project Status — proj\nUpdated: 2026-08-05\n\n## Roadmap\n- [discussed]  E-Mail Auth\n", encoding="utf-8")
        _run(hub, "--command", "feature-set", "--slug", "proj",
             "--feature-key", "email-auth", "--name", "E-Mail Auth",
             "--set", "Phase=plan", "--set", "Spec=topics/proj/specs/s.md")
        r = _run(hub, "--command", "go", "--query", "proj e-mail auth")
        data = json.loads(r.stdout)
        assert data["feature_key"] == "email-auth"
        assert data["spec"] == "topics/proj/specs/s.md"
        assert data["phase"] == "plan"


class TestProjekteFeatureFallback:
    def test_projekte_active_from_feature_file_when_no_singleton(self, tmp_path):
        hub = _make_hub(tmp_path)
        (hub / "projects-registry.json").write_text(
            json.dumps([{"slug": "proj", "name": "Proj", "path": ""}]), encoding="utf-8")
        (hub / "topics" / "proj" / "STATUS.md").write_text(
            "# Project Status — proj\nUpdated: 2026-08-05\n\n## Roadmap\n- [planned]   E-Mail Auth\n", encoding="utf-8")
        _run(hub, "--command", "feature-set", "--slug", "proj",
             "--feature-key", "email-auth", "--name", "E-Mail Auth",
             "--set", "Phase=implement")
        r = _run(hub, "--command", "projekte")
        data = json.loads(r.stdout)
        assert data[0]["active"] == "E-Mail Auth"
        assert data[0]["phase"] == "implement"

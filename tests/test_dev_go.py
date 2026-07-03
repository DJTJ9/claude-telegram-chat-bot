import json
import os
import subprocess

HUB_DIR = os.environ.get("HUB_DIR", "")

REGISTRY = [
    {"slug": "shopping-navigator", "name": "Shopping Navigator", "path": "", "path_windows": "", "repo": "", "description": ""},
    {"slug": "dev-skill", "name": "Dev Skill", "path": "", "path_windows": "", "repo": "", "description": ""},
    {"slug": "dart-app", "name": "DartApp", "path": "", "path_windows": "", "repo": "", "description": ""},
]

STATUS_SHOPPING = """# Project Status — shopping-navigator
Active: A*-Routenplanung
Phase: implement
Spec: topics/shopping-navigator/specs/2026-01-01-route-design.md
Plan: topics/shopping-navigator/plans/2026-01-01-route.md
Updated: 2026-01-01

## Roadmap
- [planned]    A*-Routenplanung
- [idea]       Barcode-Scanner
- [done]       Setup
"""

STATUS_DART = """# Project Status — dart-app
Active: (none)
Phase: (none)
Updated: 2026-01-01

## Roadmap
- [idea]       Wurf-Statistik
"""

STATUS_DEVSKILL = """# Project Status — dev-skill
Active: (none)
Phase: (none)
Updated: 2026-01-01

## Roadmap
- [discussed]  Irgendein Feature
"""


def _make_hub(tmp_path):
    (tmp_path / "projects-registry.json").write_text(json.dumps(REGISTRY))
    for slug, status in [
        ("shopping-navigator", STATUS_SHOPPING),
        ("dart-app", STATUS_DART),
        ("dev-skill", STATUS_DEVSKILL),
    ]:
        d = tmp_path / "topics" / slug
        d.mkdir(parents=True)
        (d / "STATUS.md").write_text(status)
    return tmp_path


def _go(hub, query):
    r = subprocess.run(
        ["python3", f"{HUB_DIR}/scripts/dev_context.py", "--command", "go",
         "--query", query, "--hub-dir", str(hub)],
        capture_output=True, text=True, env=os.environ,
    )
    return json.loads(r.stdout)


def test_full_query_project_feature_phase(tmp_path):
    hub = _make_hub(tmp_path)
    r = _go(hub, "shop route p")
    assert r["slug"] == "shopping-navigator"
    assert r["feature"] == "A*-Routenplanung"
    assert r["phase"] == "plan"
    assert r["feature_explicit"] is True
    assert r["spec"] == "topics/shopping-navigator/specs/2026-01-01-route-design.md"


def test_project_and_phase_uses_top_feature(tmp_path):
    hub = _make_hub(tmp_path)
    r = _go(hub, "shop p")
    assert r["feature"] == "A*-Routenplanung"
    assert r["phase"] == "plan"
    assert r["feature_explicit"] is False


def test_project_only_derives_phase_from_status(tmp_path):
    hub = _make_hub(tmp_path)
    r = _go(hub, "shop")
    assert r["feature"] == "A*-Routenplanung"
    assert r["phase"] == "implement"


def test_idea_feature_defaults_to_discuss(tmp_path):
    hub = _make_hub(tmp_path)
    r = _go(hub, "shop bar")
    assert r["feature"] == "Barcode-Scanner"
    assert r["phase"] == "discuss"


def test_ambiguous_project_returns_candidates(tmp_path):
    hub = _make_hub(tmp_path)
    r = _go(hub, "d")
    assert "candidates" in r
    slugs = {c["slug"] for c in r["candidates"]}
    assert slugs == {"dev-skill", "dart-app"}


def test_no_match_returns_error(tmp_path):
    hub = _make_hub(tmp_path)
    r = _go(hub, "zzz")
    assert "error" in r


def test_done_features_excluded(tmp_path):
    hub = _make_hub(tmp_path)
    r = _go(hub, "shop setup")
    assert "error" in r


def test_feature_miss_returns_project_matches(tmp_path):
    hub = _make_hub(tmp_path)
    r = _go(hub, "shop zzz")
    assert "error" in r
    assert r["project_matches"] == ["shopping-navigator"]


def test_no_project_match_has_no_project_matches(tmp_path):
    hub = _make_hub(tmp_path)
    r = _go(hub, "zzz")
    assert "error" in r
    assert "project_matches" not in r


def test_project_matches_skips_missing_status_md(tmp_path):
    registry = REGISTRY + [{"slug": "ghost", "name": "Ghost", "path": "",
                            "path_windows": "", "repo": "", "description": ""}]
    (tmp_path / "projects-registry.json").write_text(json.dumps(registry))
    for slug, status in [
        ("shopping-navigator", STATUS_SHOPPING),
        ("dart-app", STATUS_DART),
        ("dev-skill", STATUS_DEVSKILL),
    ]:
        d = tmp_path / "topics" / slug
        d.mkdir(parents=True)
        (d / "STATUS.md").write_text(status)
    r = _go(tmp_path, "ghost zzz")
    assert "error" in r
    assert "project_matches" not in r

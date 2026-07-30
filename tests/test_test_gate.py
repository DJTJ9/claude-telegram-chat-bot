import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import test_gate as tg


def make_hub(tmp_path, slug="proj-a", test_cmd="pytest -q",
             staging_url="https://staging.proj-a.de"):
    hub = tmp_path / "hub"
    (hub / "topics" / slug / "patches").mkdir(parents=True)
    registry = [{"slug": slug, "name": "Projekt A", "version": "0.1.0",
                 "release_mode": "live", "test_cmd": test_cmd,
                 "staging_url": staging_url, "staging_deploy_cmd": ""}]
    (hub / "projects-registry.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    return hub


def log_file(hub, slug, version):
    return hub / "topics" / slug / "patches" / f"test-v{version}.md"


def test_init_generates_log_with_registry_fields(tmp_path):
    hub = make_hub(tmp_path)
    tg.generate_log(hub, "proj-a", "0.2.0",
                    ["Login — GET /login → 200"], ["Login — sieht das Formular gut aus?"])
    text = log_file(hub, "proj-a", "0.2.0").read_text(encoding="utf-8")
    assert "version: 0.2.0" in text
    assert "slug: proj-a" in text
    assert "status: pending" in text
    assert "staging_url: https://staging.proj-a.de" in text
    assert "## Auto" in text
    assert "- [ ] Suite: pytest -q" in text
    assert "- [ ] Smoke: Login — GET /login → 200" in text
    assert "## Manuell" in text
    assert "- [ ] Login — sieht das Formular gut aus?" in text


def test_init_omits_suite_when_test_cmd_empty(tmp_path):
    hub = make_hub(tmp_path, test_cmd="")
    tg.generate_log(hub, "proj-a", "0.2.0", [], ["X — ok?"])
    text = log_file(hub, "proj-a", "0.2.0").read_text(encoding="utf-8")
    assert "Suite:" not in text
    assert "- [ ] X — ok?" in text


def test_init_fails_on_bad_semver(tmp_path):
    hub = make_hub(tmp_path)
    with pytest.raises(SystemExit) as e:
        tg.generate_log(hub, "proj-a", "v2", [], [])
    assert e.value.code == 1


def test_init_fails_when_slug_missing(tmp_path):
    hub = make_hub(tmp_path)
    with pytest.raises(SystemExit) as e:
        tg.generate_log(hub, "ghost", "0.2.0", [], [])
    assert e.value.code == 1


def test_init_fails_when_log_exists(tmp_path):
    hub = make_hub(tmp_path)
    tg.generate_log(hub, "proj-a", "0.2.0", [], ["X — ok?"])
    with pytest.raises(SystemExit) as e:
        tg.generate_log(hub, "proj-a", "0.2.0", [], ["X — ok?"])
    assert e.value.code == 1


def test_check_fails_when_log_missing(tmp_path):
    hub = make_hub(tmp_path)
    with pytest.raises(SystemExit) as e:
        tg.check_gate(hub, "proj-a", "0.2.0")
    assert e.value.code == 1


def test_check_red_when_open_lines(tmp_path):
    hub = make_hub(tmp_path)
    tg.generate_log(hub, "proj-a", "0.2.0", ["A — 200"], ["B — ok?"])
    with pytest.raises(SystemExit) as e:
        tg.check_gate(hub, "proj-a", "0.2.0")
    assert e.value.code == 1


def test_check_red_when_fail_marker(tmp_path):
    hub = make_hub(tmp_path)
    p = log_file(hub, "proj-a", "0.2.0")
    p.write_text(
        "---\nversion: 0.2.0\nslug: proj-a\nstatus: passed\n"
        "staging_url: \ngenerated: 2026-07-30\n---\n\n"
        "## Auto\n- [x] Suite: pytest -q\n"
        "## Manuell\n- [x] B — ok? — fail: Button kaputt\n",
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        tg.check_gate(hub, "proj-a", "0.2.0")
    assert e.value.code == 1


def test_check_red_when_status_not_passed(tmp_path):
    hub = make_hub(tmp_path)
    p = log_file(hub, "proj-a", "0.2.0")
    p.write_text(
        "---\nversion: 0.2.0\nslug: proj-a\nstatus: pending\n"
        "staging_url: \ngenerated: 2026-07-30\n---\n\n"
        "## Auto\n- [x] Suite: pytest -q\n"
        "## Manuell\n- [x] B — ok?\n",
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        tg.check_gate(hub, "proj-a", "0.2.0")
    assert e.value.code == 1


def test_check_green_when_all_checked_and_passed(tmp_path, capsys):
    hub = make_hub(tmp_path)
    p = log_file(hub, "proj-a", "0.2.0")
    p.write_text(
        "---\nversion: 0.2.0\nslug: proj-a\nstatus: passed\n"
        "staging_url: \ngenerated: 2026-07-30\n---\n\n"
        "## Auto\n- [x] Suite: pytest -q\n- [x] Smoke: A — 200\n"
        "## Manuell\n- [x] B — ok?\n",
        encoding="utf-8")
    tg.check_gate(hub, "proj-a", "0.2.0")  # kein SystemExit
    assert "grün" in capsys.readouterr().out


def test_init_then_check_red_then_green_integration(tmp_path):
    hub = make_hub(tmp_path)
    tg.generate_log(hub, "proj-a", "0.2.0", ["A — 200"], ["B — ok?"])
    p = log_file(hub, "proj-a", "0.2.0")
    with pytest.raises(SystemExit):
        tg.check_gate(hub, "proj-a", "0.2.0")  # rot: offen + pending
    text = p.read_text(encoding="utf-8")
    text = text.replace("- [ ]", "- [x]").replace("status: pending", "status: passed")
    p.write_text(text, encoding="utf-8")
    tg.check_gate(hub, "proj-a", "0.2.0")  # grün

# tests/test_playtest_gate.py
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import playtest_gate as pg


def make_hub(tmp_path, slug="game-a", engine="unity"):
    hub = tmp_path / "hub"
    (hub / "topics" / slug / "playtests").mkdir(parents=True)
    registry = [{"slug": slug, "name": "Game A", "engine": engine,
                 "version": "0.1.0", "release_mode": "live"}]
    (hub / "projects-registry.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    return hub


def log_file(hub, slug, feature):
    return (hub / "topics" / slug / "playtests"
            / f"playtest-{pg.feature_kebab(feature)}.md")


def test_kebab_lowercases_and_dashes():
    assert pg.feature_kebab("Double Jump (Coyote)") == "double-jump-coyote"


def test_init_generates_log_with_fixed_dimensions(tmp_path):
    hub = make_hub(tmp_path)
    pg.generate_log(hub, "game-a", "Double Jump", "EditMode grün", "unity")
    text = log_file(hub, "game-a", "Double Jump").read_text(encoding="utf-8")
    assert "feature: Double Jump" in text
    assert "slug: game-a" in text
    assert "engine: unity" in text
    assert "status: pending" in text
    assert "## Auto-Logik" in text
    assert "- [ ] EditMode grün" in text
    assert "## Playtest" in text
    for dim in ("Feel", "Balance", "Fun", "Optik", "Bug"):
        assert f"- [ ] {dim} — " in text
    assert "## Tuning-Diffs" in text


def test_init_fails_when_slug_missing(tmp_path):
    hub = make_hub(tmp_path)
    with pytest.raises(SystemExit) as e:
        pg.generate_log(hub, "ghost", "X", "N/A", "unity")
    assert e.value.code == 1


def test_init_fails_when_log_exists(tmp_path):
    hub = make_hub(tmp_path)
    pg.generate_log(hub, "game-a", "Double Jump", "N/A", "unity")
    with pytest.raises(SystemExit) as e:
        pg.generate_log(hub, "game-a", "Double Jump", "N/A", "unity")
    assert e.value.code == 1


def test_check_fails_when_log_missing(tmp_path):
    hub = make_hub(tmp_path)
    with pytest.raises(SystemExit) as e:
        pg.check_gate(hub, "game-a", "Double Jump")
    assert e.value.code == 1


def test_check_red_when_open_playtest_line(tmp_path):
    hub = make_hub(tmp_path)
    pg.generate_log(hub, "game-a", "Double Jump", "EditMode grün", "unity")
    p = log_file(hub, "game-a", "Double Jump")
    p.write_text(p.read_text().replace("status: pending", "status: passed"),
                 encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        pg.check_gate(hub, "game-a", "Double Jump")
    assert e.value.code == 1


def test_check_red_when_fail_marker_even_if_checked(tmp_path):
    hub = make_hub(tmp_path)
    p = log_file(hub, "game-a", "Double Jump")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\nfeature: Double Jump\nslug: game-a\nengine: unity\n"
        "status: passed\ngenerated: 2026-08-04\n---\n\n"
        "## Auto-Logik\n- [x] EditMode grün\n\n"
        "## Playtest\n- [x] Feel — gut\n- [x] Balance — ok\n- [x] Fun — ok\n"
        "- [x] Optik — ok\n- [x] Bug — ok — fail: clippt durch Boden\n",
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        pg.check_gate(hub, "game-a", "Double Jump")
    assert e.value.code == 1


def test_check_red_when_status_not_passed(tmp_path):
    hub = make_hub(tmp_path)
    p = log_file(hub, "game-a", "Double Jump")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\nfeature: Double Jump\nslug: game-a\nengine: unity\n"
        "status: pending\ngenerated: 2026-08-04\n---\n\n"
        "## Auto-Logik\n- [x] EditMode grün\n\n"
        "## Playtest\n- [x] Feel — gut\n- [x] Balance — ok\n- [x] Fun — ok\n"
        "- [x] Optik — ok\n- [x] Bug — ok\n",
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        pg.check_gate(hub, "game-a", "Double Jump")
    assert e.value.code == 1


def test_check_green_when_all_checked_and_passed(tmp_path, capsys):
    hub = make_hub(tmp_path)
    p = log_file(hub, "game-a", "Double Jump")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\nfeature: Double Jump\nslug: game-a\nengine: unity\n"
        "status: passed\ngenerated: 2026-08-04\n---\n\n"
        "## Auto-Logik\n- [x] EditMode grün\n\n"
        "## Playtest\n- [x] Feel — gut\n- [x] Balance — ok\n- [x] Fun — ok\n"
        "- [x] Optik — ok\n- [x] Bug — ok\n",
        encoding="utf-8")
    pg.check_gate(hub, "game-a", "Double Jump")  # kein SystemExit
    assert "grün" in capsys.readouterr().out


def test_check_green_with_na_autologic_open_line(tmp_path, capsys):
    hub = make_hub(tmp_path)
    p = log_file(hub, "game-a", "Camera Shake")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\nfeature: Camera Shake\nslug: game-a\nengine: unity\n"
        "status: passed\ngenerated: 2026-08-04\n---\n\n"
        "## Auto-Logik\n- [ ] N/A — reines [feel]-Feature\n\n"
        "## Playtest\n- [x] Feel — knackig\n- [x] Balance — ok\n- [x] Fun — ok\n"
        "- [x] Optik — ok\n- [x] Bug — keine\n",
        encoding="utf-8")
    pg.check_gate(hub, "game-a", "Camera Shake")  # N/A trotz offener Box grün
    assert "grün" in capsys.readouterr().out


def test_init_then_check_red_then_green_integration(tmp_path):
    hub = make_hub(tmp_path)
    pg.generate_log(hub, "game-a", "Double Jump", "EditMode grün", "unity")
    p = log_file(hub, "game-a", "Double Jump")
    with pytest.raises(SystemExit):
        pg.check_gate(hub, "game-a", "Double Jump")  # rot: offen + pending
    text = p.read_text(encoding="utf-8")
    text = text.replace("- [ ]", "- [x]").replace("status: pending", "status: passed")
    p.write_text(text, encoding="utf-8")
    pg.check_gate(hub, "game-a", "Double Jump")  # grün

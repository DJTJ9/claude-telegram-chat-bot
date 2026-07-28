import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import toggle_release_mode as trm


def make_hub(tmp_path, slug="proj-a", release_mode="live"):
    hub = tmp_path / "hub"
    hub.mkdir()
    registry = [{"slug": slug, "name": "Projekt A", "version": "0.1.0",
                 "release_mode": release_mode}]
    (hub / "projects-registry.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    return hub


def test_toggle_live_to_patch(tmp_path):
    hub = make_hub(tmp_path, release_mode="live")
    result = trm.toggle_release_mode(hub, "proj-a")
    assert result == "patch"
    registry = json.loads((hub / "projects-registry.json").read_text(encoding="utf-8"))
    assert registry[0]["release_mode"] == "patch"


def test_toggle_patch_to_live(tmp_path):
    hub = make_hub(tmp_path, release_mode="patch")
    result = trm.toggle_release_mode(hub, "proj-a")
    assert result == "live"


def test_toggle_unknown_slug_exits(tmp_path):
    hub = make_hub(tmp_path)
    with pytest.raises(SystemExit):
        trm.toggle_release_mode(hub, "gibts-nicht")


def test_toggle_missing_field_exits(tmp_path):
    hub = tmp_path / "hub"
    hub.mkdir()
    registry = [{"slug": "proj-a", "name": "Projekt A", "version": "0.1.0"}]
    (hub / "projects-registry.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit):
        trm.toggle_release_mode(hub, "proj-a")


def test_main_prints_new_mode(tmp_path, monkeypatch, capsys):
    hub = make_hub(tmp_path, release_mode="live")
    monkeypatch.setattr(sys, "argv",
                         ["toggle_release_mode.py", "--slug", "proj-a",
                          "--hub-dir", str(hub)])
    trm.main()
    out = capsys.readouterr().out
    assert "Deploy-Modus proj-a: patch" in out

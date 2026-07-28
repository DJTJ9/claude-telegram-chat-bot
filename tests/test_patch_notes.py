import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.patch_notes import (collect_patches, parse_patch_file,
                                 remove_released, semver_tuple)
from scripts import patch_notes

PATCH_MD = """---
version: 1.2.0
date: 2026-07-28
---
# Projekt A v1.2.0

## Features
- Favoriten-Badge in der Übersicht

## Fixes
- Fehlerseiten bei CSRF-Sites

## Member-Hinweise
- Re-Login nötig nach Update
"""

PATCH_MD_NO_MEMBER = """---
version: 0.2.0
date: 2026-07-20
---
# Projekt B v0.2.0

## Fixes
- Routenberechnung repariert
"""


def make_hub(tmp_path, slug="proj-a", version="0.1.0", name="Projekt A"):
    hub = tmp_path / "hub"
    (hub / "topics" / slug / "patches").mkdir(parents=True)
    registry = [{"slug": slug, "name": name, "version": version,
                 "release_mode": "patch"}]
    (hub / "projects-registry.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    return hub


def test_parse_patch_file_extracts_frontmatter_and_sections(tmp_path):
    f = tmp_path / "v1.2.0.md"
    f.write_text(PATCH_MD, encoding="utf-8")
    p = parse_patch_file(f)
    assert p["version"] == "1.2.0"
    assert p["date"] == "2026-07-28"
    assert p["features"] == ["Favoriten-Badge in der Übersicht"]
    assert p["fixes"] == ["Fehlerseiten bei CSRF-Sites"]
    assert p["member_notes"] == ["Re-Login nötig nach Update"]


def test_parse_patch_file_missing_section_defaults_empty(tmp_path):
    f = tmp_path / "v0.2.0.md"
    f.write_text(PATCH_MD_NO_MEMBER, encoding="utf-8")
    p = parse_patch_file(f)
    assert p["features"] == []
    assert p["member_notes"] == []


def test_parse_patch_file_without_frontmatter_exits(tmp_path):
    f = tmp_path / "v1.0.0.md"
    f.write_text("# kein Frontmatter\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        parse_patch_file(f)


def test_parse_patch_file_invalid_semver_exits(tmp_path):
    f = tmp_path / "v1.md"
    f.write_text("---\nversion: 1.x\ndate: 2026-07-28\n---\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        parse_patch_file(f)


def test_collect_patches_sorted_newest_first(tmp_path):
    hub = make_hub(tmp_path)
    (hub / "topics" / "proj-a" / "patches" / "v1.2.0.md").write_text(
        PATCH_MD, encoding="utf-8")
    (hub / "topics" / "proj-b" / "patches").mkdir(parents=True)
    (hub / "topics" / "proj-b" / "patches" / "v0.2.0.md").write_text(
        PATCH_MD_NO_MEMBER, encoding="utf-8")
    registry = json.loads(
        (hub / "projects-registry.json").read_text(encoding="utf-8"))
    patches = collect_patches(hub, registry)
    assert [p["version"] for p in patches] == ["1.2.0", "0.2.0"]
    assert patches[0]["project"] == "proj-a"
    assert patches[0]["name"] == "Projekt A"
    assert patches[1]["name"] == "proj-b"  # nicht in Registry -> slug als Name


def test_remove_released_exact_line_keeps_rest(tmp_path):
    f = tmp_path / "unreleased.md"
    f.write_text("# Unreleased — proj-a\n"
                 "- [feature] A (2026-07-28)\n"
                 "- [fix] B (2026-07-28)\n", encoding="utf-8")
    remove_released(f, ["- [feature] A (2026-07-28)"])
    text = f.read_text(encoding="utf-8")
    assert "- [feature] A" not in text
    assert "- [fix] B (2026-07-28)" in text
    assert text.startswith("# Unreleased — proj-a")


def test_remove_released_missing_line_exits(tmp_path):
    f = tmp_path / "unreleased.md"
    f.write_text("- [fix] B (2026-07-28)\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        remove_released(f, ["- [feature] A (2026-07-28)"])


def _run_main(monkeypatch, hub, website, slug, released=()):
    argv = ["patch_notes.py", "--slug", slug,
            "--hub-dir", str(hub), "--website-dir", str(website)]
    for r in released:
        argv += ["--released", r]
    monkeypatch.setattr(sys, "argv", argv)
    patch_notes.main()


def test_main_bumps_registry_and_writes_patches_json(tmp_path, monkeypatch):
    hub = make_hub(tmp_path)
    website = tmp_path / "website"
    website.mkdir()
    patches_dir = hub / "topics" / "proj-a" / "patches"
    (patches_dir / "v1.2.0.md").write_text(PATCH_MD, encoding="utf-8")
    (patches_dir / "unreleased.md").write_text(
        "# Unreleased — proj-a\n- [feature] A (2026-07-28)\n", encoding="utf-8")
    _run_main(monkeypatch, hub, website, "proj-a",
              released=["- [feature] A (2026-07-28)"])
    registry = json.loads(
        (hub / "projects-registry.json").read_text(encoding="utf-8"))
    assert registry[0]["version"] == "1.2.0"
    data = json.loads((website / "patches.json").read_text(encoding="utf-8"))
    assert data["patches"][0]["version"] == "1.2.0"
    assert data["patches"][0]["member_notes"] == ["Re-Login nötig nach Update"]
    assert "generated" in data
    unreleased = (patches_dir / "unreleased.md").read_text(encoding="utf-8")
    assert "- [feature] A" not in unreleased


def test_main_version_not_greater_exits(tmp_path, monkeypatch):
    hub = make_hub(tmp_path, version="1.2.0")
    website = tmp_path / "website"
    website.mkdir()
    (hub / "topics" / "proj-a" / "patches" / "v1.2.0.md").write_text(
        PATCH_MD, encoding="utf-8")
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, hub, website, "proj-a")


def test_main_unknown_slug_exits(tmp_path, monkeypatch):
    hub = make_hub(tmp_path)
    website = tmp_path / "website"
    website.mkdir()
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, hub, website, "gibts-nicht")


def test_main_without_vfiles_exits(tmp_path, monkeypatch):
    hub = make_hub(tmp_path)
    website = tmp_path / "website"
    website.mkdir()
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, hub, website, "proj-a")

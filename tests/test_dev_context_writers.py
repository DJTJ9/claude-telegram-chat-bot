import importlib.util
import json
import os
import subprocess

HUB_DIR = os.environ.get("HUB_DIR", "")
SCRIPT = f"{HUB_DIR}/scripts/dev_context.py"

STATUS_MD = """# Project Status — testproj
Active: Feature X
Phase: plan
Spec: topics/testproj/specs/x-design.md
Plan:
Mode: subagent
Schedule: jetzt
Teach: no
Updated: 2026-01-01

## Roadmap
- [idea]      Feature Y
- [discussed] Feature X
- [done]      Feature Z
"""


def _make_hub(tmp_path, status=STATUS_MD):
    hub = tmp_path / "hub"
    (hub / "topics" / "testproj").mkdir(parents=True)
    (hub / "topics" / "testproj" / "STATUS.md").write_text(status, encoding="utf-8")
    (hub / "projects-registry.json").write_text("[]", encoding="utf-8")
    return hub


def _run(hub, *args):
    env = {**os.environ, "HUB_DIR": str(hub)}
    return subprocess.run(["python3", SCRIPT, *args],
                          capture_output=True, text=True, env=env, timeout=5)


def _status(hub):
    return (hub / "topics" / "testproj" / "STATUS.md").read_text(encoding="utf-8")


def test_status_set_sets_field_and_stamps_updated(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "status-set", "--slug", "testproj",
             "--set", "Phase=implement")
    assert r.returncode == 0
    text = _status(hub)
    assert "Phase: implement" in text
    assert "Updated: 2026-01-01" not in text
    assert "Active: Feature X" in text


def test_status_set_clears_field(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "status-set", "--slug", "testproj",
             "--set", "Mode=", "--set", "Schedule=", "--set", "Teach=")
    assert r.returncode == 0
    text = _status(hub)
    assert "Mode:\n" in text
    assert "Schedule:\n" in text
    assert "Teach:\n" in text
    assert "subagent" not in text


def test_status_set_inserts_missing_field_before_updated(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "status-set", "--slug", "testproj",
             "--set", "Type=bug")
    assert r.returncode == 0
    lines = _status(hub).splitlines()
    assert "Type: bug" in lines
    assert lines.index("Type: bug") < next(
        i for i, line in enumerate(lines) if line.startswith("Updated:"))


def test_status_set_explicit_updated_wins(tmp_path):
    hub = _make_hub(tmp_path)
    _run(hub, "--command", "status-set", "--slug", "testproj",
         "--set", "Phase=finish", "--set", "Updated=2026-02-02")
    assert "Updated: 2026-02-02" in _status(hub)


def test_status_set_unknown_field_exits_1(tmp_path):
    hub = _make_hub(tmp_path)
    before = _status(hub)
    r = _run(hub, "--command", "status-set", "--slug", "testproj",
             "--set", "Bogus=x")
    assert r.returncode == 1
    assert "Bogus" in r.stderr
    assert _status(hub) == before


def test_status_set_missing_status_file_exits_1(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "status-set", "--slug", "nope",
             "--set", "Phase=plan")
    assert r.returncode == 1


def test_parse_status_md_knows_new_fields(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "status", "--slug", "testproj")
    assert r.returncode == 0
    import sys
    sys.path.insert(0, f"{HUB_DIR}/scripts")
    from dev_context import parse_status_md
    from pathlib import Path
    parsed = parse_status_md(Path(hub) / "topics" / "testproj" / "STATUS.md")
    assert parsed["mode"] == "subagent"
    assert parsed["schedule"] == "jetzt"
    assert parsed["teach"] == "no"
    assert parsed["type"] == ""
    assert parsed["lesson"] == ""


VISION_MD = """# Vision — testproj

## Roadmap
- [idea]      Feature Y
- [discussed] Feature X
- ✅ Feature Z   ← implementiert 2026-01-01
"""


def _make_vision(hub, text=VISION_MD):
    (hub / "topics" / "testproj" / "VISION.md").write_text(text, encoding="utf-8")


def test_roadmap_set_changes_status_keeping_alignment(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "roadmap-set", "--slug", "testproj",
             "--feature", "Feature X", "--status", "planned")
    assert r.returncode == 0
    lines = [l for l in _status(hub).splitlines() if l.startswith("- [")]
    assert lines == [
        "- [idea]      Feature Y",
        "- [planned]   Feature X",
        "- [done]      Feature Z",
    ]


def test_roadmap_set_move_to_end(tmp_path):
    hub = _make_hub(tmp_path)
    r = _run(hub, "--command", "roadmap-set", "--slug", "testproj",
             "--feature", "Feature Y", "--status", "done", "--move-to-end")
    assert r.returncode == 0
    lines = [l for l in _status(hub).splitlines() if l.startswith("- [")]
    assert lines == [
        "- [discussed] Feature X",
        "- [done]      Feature Z",
        "- [done]      Feature Y",
    ]


def test_roadmap_set_not_found_exits_1(tmp_path):
    hub = _make_hub(tmp_path)
    before = _status(hub)
    r = _run(hub, "--command", "roadmap-set", "--slug", "testproj",
             "--feature", "Nicht da", "--status", "done")
    assert r.returncode == 1
    assert _status(hub) == before


def test_roadmap_set_ambiguous_exits_1(tmp_path):
    hub = _make_hub(tmp_path, status=STATUS_MD + "- [idea]      Feature X\n")
    before = _status(hub)
    r = _run(hub, "--command", "roadmap-set", "--slug", "testproj",
             "--feature", "Feature X", "--status", "done")
    assert r.returncode == 1
    assert "ambiguous" in r.stderr.lower()
    assert _status(hub) == before


def test_finish_vision_marks_line(tmp_path):
    hub = _make_hub(tmp_path)
    _make_vision(hub)
    r = _run(hub, "--command", "finish-vision", "--slug", "testproj",
             "--feature", "Feature X")
    assert r.returncode == 0
    text = (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8")
    assert "- [discussed] Feature X" not in text
    assert "- ✅ Feature X   ← implementiert " in text
    assert "- [idea]      Feature Y" in text


def test_finish_vision_not_found_exits_1(tmp_path):
    hub = _make_hub(tmp_path)
    _make_vision(hub)
    before = (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8")
    r = _run(hub, "--command", "finish-vision", "--slug", "testproj",
             "--feature", "Nicht da")
    assert r.returncode == 1
    assert (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8") == before


def _load_dev_context():
    spec = importlib.util.spec_from_file_location("dev_context", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Realer Hub-Korpus: alle Roadmap-Zeilen mit "#" (Grep 2026-08-05).
CORPUS = [
    ("- [idea]      dev-patch: tote H1-Überschrift in patch.md entfernen — "
     "patch_notes.py parst nur Frontmatter + ##-Sektionen, Member-Name kommt aus "
     "Registry-name, die H1-Titelzeile ist wirkungslos (führte bei der Marken-Wahl "
     "in die Irre)",
     "idea",
     "dev-patch: tote H1-Überschrift in patch.md entfernen — patch_notes.py parst "
     "nur Frontmatter + ##-Sektionen, Member-Name kommt aus Registry-name, die "
     "H1-Titelzeile ist wirkungslos (führte bei der Marken-Wahl in die Irre)",
     ""),
    ("- [done]      Task 7: references/unity.md — 7 C#-Vorlagen "
     "(Harness/Debug/Capture/Seed/Tuning/Build/Test)",
     "done",
     "Task 7: references/unity.md — 7 C#-Vorlagen "
     "(Harness/Debug/Capture/Seed/Tuning/Build/Test)",
     ""),
    ("- [done]      Unity-Compile-Verifikation: C#-Vorlagen gegen "
     "Scratch-Unity-Projekt kompilieren + Toolbar-Menüpunkte (Tools/Playtest, "
     "Tools/Build) prüfen",
     "done",
     "Unity-Compile-Verifikation: C#-Vorlagen gegen Scratch-Unity-Projekt "
     "kompilieren + Toolbar-Menüpunkte (Tools/Playtest, Tools/Build) prüfen",
     ""),
    ("- [done]      Firmen-Watchlist (Career-Pages kleiner Studios)  "
     "# erweitert Job-Ingestion, nach MVP",
     "done",
     "Firmen-Watchlist (Career-Pages kleiner Studios)",
     "  # erweitert Job-Ingestion, nach MVP"),
    ("- [vision] Server-Unity headless (GameCI-Docker): Features serverseitig "
     "fertigstellen (PlayMode-Tests + Builds), Workstation führt nur noch Script "
     "aus + testet — Playtest bleibt Workstation  # Priorität: Hoch",
     "vision",
     "Server-Unity headless (GameCI-Docker): Features serverseitig fertigstellen "
     "(PlayMode-Tests + Builds), Workstation führt nur noch Script aus + testet — "
     "Playtest bleibt Workstation",
     "  # Priorität: Hoch"),
    ("- [done]      NocoDB: Positionierung via # statt Position-Property",
     "done",
     "NocoDB: Positionierung via # statt Position-Property",
     ""),
]


def test_split_roadmap_line_real_corpus():
    dc = _load_dev_context()
    for line, status, name, comment in CORPUS:
        assert dc._split_roadmap_line(line) == (status, name, comment), line


def test_roadmap_name_keeps_hash_in_name():
    dc = _load_dev_context()
    for line, _status, name, _comment in CORPUS:
        assert dc._roadmap_name(line) == name


def test_roadmap_key_reads_anchor():
    dc = _load_dev_context()
    assert dc._roadmap_key("- [idea]      Feature X  #key:feature-x") == "feature-x"


def test_roadmap_key_coexists_with_priority_comment():
    dc = _load_dev_context()
    line = "- [vision] Feature X  # Priorität: Hoch #key:feature-x"
    assert dc._roadmap_key(line) == "feature-x"
    assert dc._roadmap_name(line) == "Feature X"


def test_roadmap_key_empty_without_anchor():
    dc = _load_dev_context()
    assert dc._roadmap_key("- [idea]      Feature X") == ""
    assert dc._roadmap_key("- [done]      NocoDB: via # statt Position") == ""


def test_parse_status_md_keeps_hash_in_feature_name(tmp_path):
    status = ("# Project Status — testproj\nUpdated: 2026-01-01\n\n## Roadmap\n"
              "- [done]      Task 7: 7 C#-Vorlagen (Harness/Debug)\n"
              "- [idea]      Firmen-Watchlist  # erweitert Job-Ingestion\n")
    hub = _make_hub(tmp_path, status=status)
    r = _run(hub, "--command", "status", "--slug", "testproj")
    assert r.returncode == 0
    names = [f["name"] for f in json.loads(r.stdout)]
    assert names == ["Task 7: 7 C#-Vorlagen (Harness/Debug)", "Firmen-Watchlist"]


STATUS_HASH_MD = """# Project Status — testproj
Updated: 2026-01-01

## Roadmap
- [idea]      Feature Y
- [discussed] Task 7: 7 C#-Vorlagen (Harness/Debug)  #key:unity-vorlagen
- [done]      Feature Z
"""

VISION_HASH_MD = """# Vision — testproj

## Roadmap
- [idea]      Feature Y
- [discussed] Task 7: 7 C#-Vorlagen (Harness/Debug)  # Priorität: Hoch #key:unity-vorlagen
"""


def test_roadmap_set_keeps_full_hash_name_and_comment(tmp_path):
    hub = _make_hub(tmp_path, status=STATUS_HASH_MD)
    r = _run(hub, "--command", "roadmap-set", "--slug", "testproj",
             "--feature", "Task 7: 7 C#-Vorlagen (Harness/Debug)", "--status", "planned")
    assert r.returncode == 0
    assert ("- [planned]   Task 7: 7 C#-Vorlagen (Harness/Debug)  #key:unity-vorlagen"
            in _status(hub))


def test_roadmap_set_matches_by_key(tmp_path):
    hub = _make_hub(tmp_path, status=STATUS_HASH_MD)
    r = _run(hub, "--command", "roadmap-set", "--slug", "testproj",
             "--feature", "Voellig anderer Name", "--feature-key", "unity-vorlagen",
             "--status", "done")
    assert r.returncode == 0
    assert ("- [done]      Task 7: 7 C#-Vorlagen (Harness/Debug)  #key:unity-vorlagen"
            in _status(hub))


def test_roadmap_set_unknown_key_falls_back_to_name(tmp_path):
    hub = _make_hub(tmp_path, status=STATUS_HASH_MD)
    r = _run(hub, "--command", "roadmap-set", "--slug", "testproj",
             "--feature", "Feature Y", "--feature-key", "gibt-es-nicht",
             "--status", "planned")
    assert r.returncode == 0
    assert "- [planned]   Feature Y" in _status(hub)


def test_finish_vision_keeps_hash_name_and_comment(tmp_path):
    hub = _make_hub(tmp_path)
    _make_vision(hub, text=VISION_HASH_MD)
    r = _run(hub, "--command", "finish-vision", "--slug", "testproj",
             "--feature", "Task 7: 7 C#-Vorlagen (Harness/Debug)")
    assert r.returncode == 0
    text = (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8")
    assert ("- ✅ Task 7: 7 C#-Vorlagen (Harness/Debug)  # Priorität: Hoch "
            "#key:unity-vorlagen   ← implementiert " in text)


def test_finish_vision_matches_by_key(tmp_path):
    hub = _make_hub(tmp_path)
    _make_vision(hub, text=VISION_HASH_MD)
    r = _run(hub, "--command", "finish-vision", "--slug", "testproj",
             "--feature", "Umformulierter Name", "--feature-key", "unity-vorlagen")
    assert r.returncode == 0
    text = (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8")
    assert "- ✅ Task 7: 7 C#-Vorlagen (Harness/Debug)" in text
    assert "Umformulierter Name" not in text
    assert json.loads(r.stdout)["feature"] == "Task 7: 7 C#-Vorlagen (Harness/Debug)"


def test_finish_vision_unknown_key_and_name_exits_1(tmp_path):
    hub = _make_hub(tmp_path)
    _make_vision(hub, text=VISION_HASH_MD)
    before = (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8")
    r = _run(hub, "--command", "finish-vision", "--slug", "testproj",
             "--feature", "Nicht da", "--feature-key", "auch-nicht-da")
    assert r.returncode == 1
    assert (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8") == before


def test_vision_key_anchors_existing_line(tmp_path):
    hub = _make_hub(tmp_path)
    _make_vision(hub)
    r = _run(hub, "--command", "vision-key", "--slug", "testproj",
             "--feature-key", "feature-x", "--feature", "Feature X")
    assert r.returncode == 0
    assert json.loads(r.stdout)["action"] == "anchored"
    text = (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8")
    assert "- [discussed] Feature X  #key:feature-x" in text


def test_vision_key_is_idempotent(tmp_path):
    hub = _make_hub(tmp_path)
    _make_vision(hub)
    _run(hub, "--command", "vision-key", "--slug", "testproj",
         "--feature-key", "feature-x", "--feature", "Feature X")
    first = (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8")
    r = _run(hub, "--command", "vision-key", "--slug", "testproj",
             "--feature-key", "feature-x", "--feature", "Ganz anderer Name")
    assert r.returncode == 0
    assert json.loads(r.stdout)["action"] == "unchanged"
    assert (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8") == first


def test_vision_key_creates_missing_line(tmp_path):
    hub = _make_hub(tmp_path)
    _make_vision(hub)
    r = _run(hub, "--command", "vision-key", "--slug", "testproj",
             "--feature-key", "neues-feature", "--feature", "Neues Feature",
             "--status", "discussed")
    assert r.returncode == 0
    assert json.loads(r.stdout)["action"] == "created"
    lines = [l for l in (hub / "topics" / "testproj" / "VISION.md")
             .read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    assert lines[-1] == "- [discussed] Neues Feature  #key:neues-feature"


def test_vision_key_keeps_existing_comment(tmp_path):
    hub = _make_hub(tmp_path)
    _make_vision(hub, text=("# Vision — testproj\n\n## Roadmap\n"
                            "- [idea]      Feature X  # Priorität: Hoch\n"))
    r = _run(hub, "--command", "vision-key", "--slug", "testproj",
             "--feature-key", "feature-x", "--feature", "Feature X")
    assert r.returncode == 0
    text = (hub / "topics" / "testproj" / "VISION.md").read_text(encoding="utf-8")
    assert "- [idea]      Feature X  # Priorität: Hoch  #key:feature-x" in text


def test_vision_key_missing_args_exits_1(tmp_path):
    hub = _make_hub(tmp_path)
    _make_vision(hub)
    r = _run(hub, "--command", "vision-key", "--slug", "testproj",
             "--feature-key", "feature-x")
    assert r.returncode == 1

import json
import os
import subprocess
from pathlib import Path

HUB_DIR = os.environ.get("HUB_DIR", "")
SCRIPT = f"{HUB_DIR}/scripts/rotate_knowledge.py"

HEADER = "# Decisions — Dev Skill\n"


def _entry(n):
    return f"## [2026-07-{n:02d}] Entscheidung {n}\n- **Grund:** Grund {n}\n"


def _write(path, count):
    body = "\n".join(_entry(n) for n in range(count, 0, -1))
    path.write_text(HEADER + "\n" + body, encoding="utf-8")


def _run(path, keep=None):
    cmd = ["python3", SCRIPT, "--file", str(path)]
    if keep is not None:
        cmd += ["--keep", str(keep)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=5)


def test_exactly_keep_does_not_rotate(tmp_path):
    p = tmp_path / "DECISIONS.md"
    _write(p, 8)
    before = p.read_text(encoding="utf-8")
    r = _run(p)
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"rotated": 0}
    assert p.read_text(encoding="utf-8") == before
    assert not (tmp_path / "DECISIONS_ARCHIVE.md").exists()


def test_keep_plus_one_rotates_oldest(tmp_path):
    p = tmp_path / "DECISIONS.md"
    _write(p, 9)
    r = _run(p)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["rotated"] == 1
    src = p.read_text(encoding="utf-8")
    assert src.count("## [") == 8
    assert "Entscheidung 1" not in src
    assert "Entscheidung 9" in src
    arc = (tmp_path / "DECISIONS_ARCHIVE.md").read_text(encoding="utf-8")
    assert arc.startswith("# Decisions Archive — Dev Skill")
    assert "Entscheidung 1" in arc


def test_far_over_keep_moves_all_older_in_order(tmp_path):
    p = tmp_path / "DECISIONS.md"
    _write(p, 12)
    r = _run(p)
    assert json.loads(r.stdout)["rotated"] == 4
    arc = (tmp_path / "DECISIONS_ARCHIVE.md").read_text(encoding="utf-8")
    assert arc.count("## [") == 4
    assert arc.index("Entscheidung 4") < arc.index("Entscheidung 1")
    assert p.read_text(encoding="utf-8").count("## [") == 8


def test_appends_to_existing_archive_keeping_order(tmp_path):
    p = tmp_path / "LEARNINGS.md"
    p.write_text("# Learnings — Dev Skill\n\n"
                 + "\n".join(_entry(n) for n in range(3, 0, -1)), encoding="utf-8")
    arc = tmp_path / "LEARNINGS_ARCHIVE.md"
    arc.write_text("# Learnings Archive — Dev Skill\n\n## [2026-01-01] Alt\n- **Grund:** alt\n", encoding="utf-8")
    r = _run(p, keep=1)
    assert r.returncode == 0
    text = arc.read_text(encoding="utf-8")
    assert text.count("# Learnings Archive") == 1
    assert text.index("Alt") < text.index("Entscheidung 2")
    assert text.index("Entscheidung 2") < text.index("Entscheidung 1")
    assert p.read_text(encoding="utf-8").count("## [") == 1


def test_custom_keep(tmp_path):
    p = tmp_path / "DECISIONS.md"
    _write(p, 5)
    assert json.loads(_run(p, keep=2).stdout)["rotated"] == 3
    assert p.read_text(encoding="utf-8").count("## [") == 2


def test_missing_file_exits_1(tmp_path):
    r = _run(tmp_path / "NOPE.md")
    assert r.returncode == 1
    assert "not found" in r.stderr


def test_unparsable_title_exits_1(tmp_path):
    p = tmp_path / "DECISIONS.md"
    p.write_text("Kein Titel hier\n\n" + "\n".join(_entry(n) for n in range(9, 0, -1)), encoding="utf-8")
    r = _run(p)
    assert r.returncode == 1
    assert "title" in r.stderr.lower()
    assert not (tmp_path / "DECISIONS_ARCHIVE.md").exists()

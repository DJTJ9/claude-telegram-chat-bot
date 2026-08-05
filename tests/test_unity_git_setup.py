# tests/test_unity_git_setup.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import unity_git_setup as ug


def test_gitattributes_lines_have_lfs_and_merge():
    lines = ug.gitattributes_lines()
    assert "*.png filter=lfs diff=lfs merge=lfs -text" in lines
    assert "*.fbx filter=lfs diff=lfs merge=lfs -text" in lines
    assert "*.unity merge=unityyamlmerge eol=lf" in lines
    assert "*.prefab merge=unityyamlmerge eol=lf" in lines
    assert "*.asset merge=unityyamlmerge eol=lf" in lines


def test_write_hygiene_files_creates_both_with_sentinels(tmp_path):
    ug.write_hygiene_files(tmp_path)
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    ga = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
    assert ug.BEGIN in gi and ug.END in gi
    assert "Library/" in gi
    assert ug.BEGIN in ga and ug.END in ga
    assert "filter=lfs" in ga and "merge=unityyamlmerge" in ga


def test_ensure_block_idempotent(tmp_path):
    p = tmp_path / ".gitignore"
    ug.ensure_block(p, ug.GITIGNORE_LINES)
    first = p.read_text(encoding="utf-8")
    ug.ensure_block(p, ug.GITIGNORE_LINES)
    assert p.read_text(encoding="utf-8") == first
    assert first.count(ug.BEGIN) == 1
    assert first.count("Library/") == 1


def test_ensure_block_preserves_user_lines_outside(tmp_path):
    p = tmp_path / ".gitignore"
    p.write_text("# meine eigenen Regeln\nsecrets.env\n", encoding="utf-8")
    ug.ensure_block(p, ug.GITIGNORE_LINES)
    text = p.read_text(encoding="utf-8")
    assert "secrets.env" in text
    assert "# meine eigenen Regeln" in text
    assert ug.BEGIN in text and "Library/" in text


def test_ensure_block_adds_missing_line_inside_existing_block(tmp_path):
    p = tmp_path / ".gitignore"
    p.write_text(f"{ug.BEGIN}\nTemp/\n{ug.END}\n", encoding="utf-8")
    ug.ensure_block(p, ug.GITIGNORE_LINES)
    text = p.read_text(encoding="utf-8")
    assert "Library/" in text
    assert text.count("Temp/") == 1
    assert text.count(ug.BEGIN) == 1


def test_check_green_after_write(tmp_path, capsys):
    ug.write_hygiene_files(tmp_path)
    ug.check_repo(tmp_path)
    assert "grün" in capsys.readouterr().out


def test_check_red_when_gitignore_missing(tmp_path):
    ug.write_hygiene_files(tmp_path)
    (tmp_path / ".gitignore").unlink()
    with pytest.raises(SystemExit) as e:
        ug.check_repo(tmp_path)
    assert e.value.code == 1


def test_check_red_when_merge_line_missing(tmp_path):
    ug.write_hygiene_files(tmp_path)
    ga = tmp_path / ".gitattributes"
    ga.write_text(ga.read_text(encoding="utf-8").replace(
        "merge=unityyamlmerge", "merge=none"), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        ug.check_repo(tmp_path)
    assert e.value.code == 1


def test_init_repo_fails_on_missing_dir(tmp_path):
    with pytest.raises(SystemExit) as e:
        ug.init_repo(tmp_path / "does-not-exist")
    assert e.value.code == 1

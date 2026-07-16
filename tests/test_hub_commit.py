import os, subprocess, sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "hub_commit.py"


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t.t")
    _git(path, "config", "user.name", "t")
    return path


def _run(repo, *args):
    env = dict(os.environ, HUB_DIR=str(repo))
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env)


def _log_files(repo):
    """Paths touched by HEAD commit."""
    r = _git(repo, "show", "--name-only", "--pretty=format:", "HEAD")
    return set(f for f in r.stdout.split() if f)


def _staged(repo):
    r = _git(repo, "diff", "--cached", "--name-only")
    return set(f for f in r.stdout.split() if f)


def test_bleed_two_sessions(tmp_path):
    """Session A commits only its path; Session B's staged file stays uncommitted."""
    repo = _init_repo(tmp_path / "hub")
    (repo / "seed").write_text("x")
    _git(repo, "add", "seed"); _git(repo, "commit", "-qm", "seed")
    # both sessions stage their own file into the shared index
    (repo / "A").write_text("a"); (repo / "B").write_text("b")
    _git(repo, "add", "A"); _git(repo, "add", "B")
    r = _run(repo, "A", "-m", "commit A")
    assert r.returncode == 0, r.stderr
    assert _log_files(repo) == {"A"}          # only A committed
    assert "B" in _staged(repo)               # B NOT bled into the commit


def test_pathspec_only_named(tmp_path):
    repo = _init_repo(tmp_path / "hub")
    (repo / "seed").write_text("x")
    _git(repo, "add", "seed"); _git(repo, "commit", "-qm", "seed")
    (repo / "x").write_text("1"); (repo / "y").write_text("2")
    r = _run(repo, "x", "-m", "only x")
    assert r.returncode == 0, r.stderr
    assert _log_files(repo) == {"x"}


def test_new_untracked_file_gets_added(tmp_path):
    repo = _init_repo(tmp_path / "hub")
    (repo / "seed").write_text("x")
    _git(repo, "add", "seed"); _git(repo, "commit", "-qm", "seed")
    (repo / "fresh").write_text("new")        # never git-add'd by caller
    r = _run(repo, "fresh", "-m", "add fresh")
    assert r.returncode == 0, r.stderr
    assert _log_files(repo) == {"fresh"}


def test_nothing_to_commit_is_success(tmp_path):
    repo = _init_repo(tmp_path / "hub")
    (repo / "seed").write_text("x")
    _git(repo, "add", "seed"); _git(repo, "commit", "-qm", "seed")
    r = _run(repo, "seed", "-m", "noop")      # seed unchanged
    assert r.returncode == 0, r.stdout + r.stderr


def test_push_to_bare_remote(tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    repo = _init_repo(tmp_path / "work")
    _git(repo, "remote", "add", "origin", str(bare))
    (repo / "f").write_text("1")
    _git(repo, "add", "f"); _git(repo, "commit", "-qm", "init")
    _git(repo, "push", "-q", "-u", "origin", "HEAD")
    (repo / "g").write_text("2"); _git(repo, "add", "g")
    r = _run(repo, "g", "-m", "with push", "--push")
    assert r.returncode == 0, r.stdout + r.stderr
    rl = subprocess.run(["git", "-C", str(bare), "log", "--oneline"],
                        capture_output=True, text=True)
    assert "with push" in rl.stdout

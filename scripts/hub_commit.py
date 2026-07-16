#!/usr/bin/env python3
"""Serialized, pathspec-scoped commit for the shared $HUB_DIR checkout.

Parallel dev-sessions share one working tree + one index. A pathless
`git commit` would sweep the whole index (bleed). This helper commits ONLY
the named paths via a temp index (`git commit -- <paths>`), under an flock
so concurrent add/commit never race on .git/index.lock. Optional --push does
pull --rebase --autostash + push with retry.
"""
import argparse
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path


def _git(hub, *args):
    return subprocess.run(["git", "-C", hub, *args],
                          capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="paths to add + commit")
    ap.add_argument("-m", "--message", required=True)
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    hub = os.environ["HUB_DIR"]
    lock_path = Path(hub) / ".git" / "hub_commit.lock"
    lock = open(lock_path, "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        _git(hub, "add", "--", *a.paths)
        r = _git(hub, "commit", "-m", a.message, "--", *a.paths)
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
            sys.stderr.write(r.stdout + r.stderr)
            sys.exit(1)
        if a.push:
            for _ in range(3):
                _git(hub, "pull", "--rebase", "--autostash")
                if _git(hub, "push").returncode == 0:
                    break
                time.sleep(1)
            else:
                sys.stderr.write("hub_commit: push failed after 3 attempts\n")
                sys.exit(1)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


if __name__ == "__main__":
    main()

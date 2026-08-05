#!/usr/bin/env python3
"""Unity-Git-Hygiene für den game-Skill: init (.gitignore/.gitattributes idempotent
zwischen Sentinels generieren, Git-LFS + UnityYAMLMerge einrichten) + check
(Struktur-Gate, reine Datei-I/O, fail-hard). Modell: scripts/playtest_gate.py."""
import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

BEGIN = "# >>> game-skill unity hygiene >>>"
END = "# <<< game-skill unity hygiene <<<"

GITIGNORE_LINES = [
    "Library/", "Temp/", "Obj/", "Build/", "Builds/", "Logs/",
    "UserSettings/", ".vs/", "*.csproj", "*.sln", "*.pidb", "*.booproj",
    "*.svd", "*.pdb", "*.mdb", "*.apk", "*.aab", ".gradle/",
]

LFS_EXTS = [
    "png", "jpg", "jpeg", "gif", "psd", "tga", "tiff", "bmp", "exr",
    "wav", "mp3", "ogg", "aif", "aiff", "fbx", "blend",
    "mp4", "mov", "webm", "ttf", "otf", "zip", "unitypackage",
]
YAML_MERGE_EXTS = ["unity", "prefab", "asset"]


def fail(msg):
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(1)


def gitattributes_lines():
    lines = [f"*.{ext} filter=lfs diff=lfs merge=lfs -text" for ext in LFS_EXTS]
    lines += [f"*.{ext} merge=unityyamlmerge eol=lf" for ext in YAML_MERGE_EXTS]
    return lines


def ensure_block(path, desired):
    """Idempotent: fehlende Zeilen NUR innerhalb des Sentinel-Blocks ergänzen,
    User-Zeilen außerhalb unangetastet. Fehlt der Block → anhängen."""
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    if BEGIN in lines and END in lines:
        b, e = lines.index(BEGIN), lines.index(END)
        block = lines[b + 1:e]
        for d in desired:
            if d not in block:
                block.append(d)
        new_lines = lines[:b + 1] + block + lines[e:]
        path.write_text("\n".join(new_lines).rstrip("\n") + "\n", encoding="utf-8")
        return
    block_text = "\n".join([BEGIN] + desired + [END]) + "\n"
    if existing.strip():
        path.write_text(existing.rstrip("\n") + "\n\n" + block_text, encoding="utf-8")
    else:
        path.write_text(block_text, encoding="utf-8")


def write_hygiene_files(repo):
    repo = Path(repo)
    ensure_block(repo / ".gitignore", GITIGNORE_LINES)
    ensure_block(repo / ".gitattributes", gitattributes_lines())
    print(f"OK: .gitignore + .gitattributes (Sentinel-Block) in {repo} geschrieben")


def init_repo(repo):
    repo = Path(repo)
    if not repo.is_dir():
        fail(f"Repo-Pfad {repo} existiert nicht")
    write_hygiene_files(repo)
    setup_lfs(repo)
    setup_mergetool(repo)


def check_repo(repo):
    repo = Path(repo)
    problems = []
    gi = repo / ".gitignore"
    if not gi.exists():
        problems.append(".gitignore fehlt")
    else:
        t = gi.read_text(encoding="utf-8")
        if BEGIN not in t:
            problems.append(".gitignore: Sentinel-Block fehlt")
        if "Library/" not in t:
            problems.append(".gitignore: 'Library/' fehlt")
    ga = repo / ".gitattributes"
    if not ga.exists():
        problems.append(".gitattributes fehlt")
    else:
        t = ga.read_text(encoding="utf-8")
        if BEGIN not in t:
            problems.append(".gitattributes: Sentinel-Block fehlt")
        if "filter=lfs" not in t:
            problems.append(".gitattributes: keine LFS-Tracking-Zeile")
        if "merge=unityyamlmerge" not in t:
            problems.append(".gitattributes: keine unityyamlmerge-Merge-Zeile")
    if problems:
        print(f"FEHLER: Git-Hygiene-Check für {repo} ROT:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: Git-Hygiene-Check für {repo} grün")


def _git(repo, args):
    try:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True)
        return r.returncode, r.stderr
    except FileNotFoundError:
        return None, "git nicht gefunden"


def setup_lfs(repo):
    try:
        probe = subprocess.run(["git", "lfs", "version"],
                               capture_output=True, text=True)
        available = probe.returncode == 0
    except FileNotFoundError:
        available = False
    if not available:
        print("WARN: git-lfs nicht installiert — LFS-Filter nicht aktiviert. "
              "Install: https://git-lfs.com , dann `git lfs install` im Repo. "
              "Die .gitattributes-Tracking-Zeilen sind bereits geschrieben.",
              file=sys.stderr)
        return False
    rc, err = _git(repo, ["lfs", "install", "--local"])
    if rc != 0:
        print(f"WARN: `git lfs install --local` fehlgeschlagen "
              f"({(err or '').strip()}) — kein Git-Repo? LFS-Hooks nicht gesetzt, "
              ".gitattributes-Zeilen bleiben.", file=sys.stderr)
        return False
    print("OK: git lfs install --local")
    return True


MERGE_GLOBS = [
    os.path.expanduser("~/Unity/Hub/Editor/*/Editor/Data/Tools/UnityYAMLMerge"),
    os.path.expanduser("~/Unity/Hub/Editor/*/Editor/Data/Tools/UnityYAMLMerge.exe"),
    "/Applications/Unity/Hub/Editor/*/Unity.app/Contents/Tools/UnityYAMLMerge",
    os.path.expanduser(
        "~/Applications/Unity/Hub/Editor/*/Unity.app/Contents/Tools/UnityYAMLMerge"),
    "C:/Program Files/Unity/Hub/Editor/*/Editor/Data/Tools/UnityYAMLMerge.exe",
]


def find_yaml_merge():
    for pattern in MERGE_GLOBS:
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


def setup_mergetool(repo):
    tool = find_yaml_merge()
    if tool is None:
        print("WARN: UnityYAMLMerge nicht gefunden — Smart-Merge nicht konfiguriert.\n"
              "  Manuell (UnityYAMLMerge-Pfad des Editors einsetzen):\n"
              "    git config merge.unityyamlmerge.name \"Unity SmartMerge\"\n"
              "    git config merge.unityyamlmerge.driver "
              "'<UnityYAMLMerge> merge -h -p --force --fallback none %O %B %A %A'\n"
              "    git config mergetool.unityyamlmerge.trustExitCode false\n"
              "  Die .gitattributes-Merge-Zeilen sind bereits gesetzt.",
              file=sys.stderr)
        return False
    driver = f'{tool} merge -h -p --force --fallback none %O %B %A %A'
    cmd = f'{tool} merge -p "$BASE" "$REMOTE" "$LOCAL" "$MERGED"'
    calls = [
        ["config", "merge.unityyamlmerge.name", "Unity SmartMerge"],
        ["config", "merge.unityyamlmerge.driver", driver],
        ["config", "mergetool.unityyamlmerge.cmd", cmd],
        ["config", "mergetool.unityyamlmerge.trustExitCode", "false"],
    ]
    ok = True
    for c in calls:
        rc, err = _git(repo, c)
        if rc != 0:
            ok = False
            print(f"WARN: `git {' '.join(c)}` fehlgeschlagen ({(err or '').strip()})",
                  file=sys.stderr)
    if ok:
        print(f"OK: UnityYAMLMerge konfiguriert ({tool})")
    return ok


def main():
    parser = argparse.ArgumentParser(description="Unity-Git-Hygiene (fail-hard)")
    sub = parser.add_subparsers(dest="mode", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--repo", required=True)
    p_check = sub.add_parser("check")
    p_check.add_argument("--repo", required=True)
    args = parser.parse_args()
    if args.mode == "init":
        init_repo(args.repo)
    else:
        check_repo(args.repo)


if __name__ == "__main__":
    main()

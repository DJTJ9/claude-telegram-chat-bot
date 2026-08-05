#!/usr/bin/env python3
"""Compile-Verifikation der game-Skill-C#-Vorlagen (references/unity.md):
extrahiert alle csharp-Blocks, platziert sie regelbasiert im Scratch-Unity-
Projekt (Assets/Skill/, wipe + rewrite nach den Unity-Konventionen via
unity_scaffold.scaffold) und kompiliert headless im unityci/editor-Container.
SkillCheck.Run prüft danach per TypeCache die
Toolbar-Menüpunkte. Fail-hard Exit 0/1.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from scripts.unity_scaffold import scaffold  # Test-Kontext (Repo-Root auf sys.path)
except ImportError:
    from unity_scaffold import scaffold  # Script-Kontext (scripts/ ist sys.path[0])

FENCE_RE = re.compile(r"```csharp\n(.*?)```", re.DOTALL)
CLASS_RE = re.compile(r"(?:class|struct|interface)\s+([A-Za-z_]\w*)")
ERROR_RE = re.compile(r"error CS\d+[^\n]*")
VERSION_RE = re.compile(r"m_EditorVersion:\s*(\S+)")

# Scratch-Projekt spiegelt die Konventionen 1:1 (references/unity-conventions.md):
# Assembly-Ordner aus dem Block-Inhalt, darunter der Feature-Ordner.
PREFIX = "Skill"
FEATURE = "Templates"


def extract_blocks(md_text: str) -> list:
    """Alle ```csharp-Fences -> Block-Inhalte (bash-Fences fallen raus)."""
    return FENCE_RE.findall(md_text)


def class_name(block: str):
    """Erster class/struct/interface-Name im Block, sonst None."""
    m = CLASS_RE.search(block)
    return m.group(1) if m else None


def placement(block: str) -> str:
    """Zielordner unter Assets/<PREFIX>/ — erste Regel gewinnt.
    Assembly-Ordner nach Block-Inhalt, darunter der Feature-Ordner."""
    if "[UnityTest]" in block:
        return f"Tests/PlayMode/{FEATURE}"
    if "using NUnit.Framework" in block:
        return f"Tests/EditMode/{FEATURE}"
    depth = 0
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("#if") and "UNITY_EDITOR" in s:
            depth += 1
        elif s.startswith("#endif") and depth:
            depth -= 1
        elif s.startswith("using UnityEditor") and depth == 0:
            return f"Editor/{FEATURE}"
    return f"Runtime/{FEATURE}"


def write_project_files(blocks: list, scratch: Path) -> list:
    """Wipe + Rewrite von Assets/<PREFIX>/ (Konventions-Skelett + asmdefs via
    unity_scaffold.scaffold, dann die .cs-Blocks). -> relative Pfade."""
    skill = scratch / "Assets" / PREFIX
    if skill.exists():
        shutil.rmtree(skill)
    scaffold(scratch, PREFIX)
    written = []
    for block in blocks:
        name = class_name(block)
        if name is None:
            print(f"BLOCKED: kein Klassenname im Block:\n{block[:120]}",
                  file=sys.stderr)
            sys.exit(1)
        rel = f"{placement(block)}/{name}.cs"
        p = skill / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(block, encoding="utf-8")
        written.append(rel)
    return written


def image_tag(scratch: Path) -> str:
    """unityci/editor-Tag aus ProjectSettings/ProjectVersion.txt."""
    pv = scratch / "ProjectSettings" / "ProjectVersion.txt"
    if not pv.exists():
        print(f"BLOCKED: {pv} fehlt — Scratch-Projekt nicht aufgesetzt "
              "(Setup siehe Plan Task 2)", file=sys.stderr)
        sys.exit(1)
    m = VERSION_RE.search(pv.read_text(encoding="utf-8"))
    if not m:
        print(f"BLOCKED: kein m_EditorVersion in {pv}", file=sys.stderr)
        sys.exit(1)
    return f"unityci/editor:ubuntu-{m.group(1)}-base-3"


def docker_cmd(scratch: Path, license_path: Path, tag: str) -> list:
    """docker-run-Kommando. Kein -quit: SkillCheck.Run exitet selbst;
    bei Compile-Fehlern bricht -batchmode von allein mit Exit != 0 ab."""
    return [
        "docker", "run", "--rm",
        "-v", f"{scratch}:/project",
        "-v", f"{license_path}:/root/.local/share/unity3d/Unity/Unity_lic.ulf",
        tag,
        "unity-editor", "-batchmode", "-nographics",
        "-projectPath", "/project",
        "-executeMethod", "SkillCheck.Run",
        "-logFile", "-",
    ]


def parse_log(log: str) -> dict:
    """error-CS-Zeilen (dedupliziert) + SkillCheck-Marker aus dem Unity-Log."""
    return {
        "errors": list(dict.fromkeys(ERROR_RE.findall(log))),
        "menu_ok": re.findall(r"\[SkillCheck\] MENUITEM OK: ([^\n]+)", log),
        "menu_missing": re.findall(r"\[SkillCheck\] MENUITEM MISSING: ([^\n]+)",
                                   log),
        "result_pass": "[SkillCheck] RESULT PASS" in log,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--md",
                    default="/root/.claude/skills/game/references/unity.md")
    ap.add_argument("--scratch", default="/root/unity-scratch")
    ap.add_argument("--license", default="/root/secrets/unity/Unity_lic.ulf")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()

    md, scratch, lic = Path(args.md), Path(args.scratch), Path(args.license)
    for p, hint in ((md, "Vorlagen-Doc"),
                    (lic, "Unity-Lizenz (.ulf) — Setup siehe Plan Task 2")):
        if not p.exists():
            print(f"BLOCKED: {p} fehlt ({hint})", file=sys.stderr)
            return 1
    if not shutil.which("docker"):
        print("BLOCKED: docker nicht auf PATH", file=sys.stderr)
        return 1

    blocks = extract_blocks(md.read_text(encoding="utf-8"))
    if not blocks:
        print(f"BLOCKED: keine csharp-Blocks in {md}", file=sys.stderr)
        return 1
    tag = image_tag(scratch)
    written = write_project_files(blocks, scratch)
    print(f"{len(blocks)} csharp-Blocks -> {scratch}/Assets/{PREFIX}/:")
    for rel in written:
        print(f"  {rel}")
    print(f"Image: {tag}")

    proc = subprocess.run(docker_cmd(scratch, lic, tag),
                          capture_output=True, text=True,
                          timeout=args.timeout)
    res = parse_log(proc.stdout + proc.stderr)

    if res["errors"]:
        print("\nCOMPILE-FEHLER:")
        for e in res["errors"]:
            print(f"  {e}")
        return 1
    if proc.returncode != 0 and not res["result_pass"]:
        log = proc.stdout + proc.stderr
        print(f"\nBLOCKED: Unity-Exit {proc.returncode} ohne Compile-Fehler "
              f"— Log-Ende:\n{log[-2000:]}", file=sys.stderr)
        return 1

    print("\nCompile: OK")
    for item in res["menu_ok"]:
        print(f"  MenuItem OK: {item}")
    for item in res["menu_missing"]:
        print(f"  MenuItem FEHLT: {item}")
    if not res["result_pass"]:
        return 1
    print("\nPASS — alle Vorlagen kompilieren, Menüpunkte registriert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

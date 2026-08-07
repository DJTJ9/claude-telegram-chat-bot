#!/usr/bin/env python3
"""Legt das Konventions-Ordnerskelett + die vier asmdefs eines Unity-Projekts an
(Regelwerk: /root/.claude/skills/game/references/unity-conventions.md).

LAYOUT/ASMDEFS sind Single Source of Truth — unity_compile_check.py ruft
scaffold() statt eigene Konstanten zu führen. Idempotent: vorhandene Ordner und
asmdefs bleiben unangetastet, .cs-Dateien werden nie angefasst oder verschoben.
Fail-hard Exit 0/1.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.console import enable_safe_console

enable_safe_console()


LAYOUT = [
    "Runtime",
    "Runtime/Shared",
    "Editor",
    "Editor/Shared",
    "Tests/EditMode",
    "Tests/PlayMode",
]

ASMDEFS = {
    "Runtime/{prefix}.Runtime.asmdef": {"name": "{prefix}.Runtime"},
    "Editor/{prefix}.Editor.asmdef": {
        "name": "{prefix}.Editor",
        "references": ["{prefix}.Runtime"],
        "includePlatforms": ["Editor"],
    },
    "Tests/EditMode/{prefix}.Tests.EditMode.asmdef": {
        "name": "{prefix}.Tests.EditMode",
        "references": ["UnityEngine.TestRunner", "UnityEditor.TestRunner",
                       "{prefix}.Runtime"],
        "includePlatforms": ["Editor"],
        "overrideReferences": True,
        "precompiledReferences": ["nunit.framework.dll"],
        "autoReferenced": False,
        "defineConstraints": ["UNITY_INCLUDE_TESTS"],
    },
    "Tests/PlayMode/{prefix}.Tests.PlayMode.asmdef": {
        "name": "{prefix}.Tests.PlayMode",
        "references": ["UnityEngine.TestRunner", "UnityEditor.TestRunner",
                       "{prefix}.Runtime"],
        "overrideReferences": True,
        "precompiledReferences": ["nunit.framework.dll"],
        "autoReferenced": False,
        "defineConstraints": ["UNITY_INCLUDE_TESTS"],
    },
}


def _fill(value, prefix):
    """Ersetzt {prefix} rekursiv in str/list/dict."""
    if isinstance(value, str):
        return value.replace("{prefix}", prefix)
    if isinstance(value, list):
        return [_fill(v, prefix) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, prefix) for k, v in value.items()}
    return value


def asmdefs_for(prefix: str) -> dict:
    """ASMDEFS mit eingesetztem Prefix -> {relativer Pfad: asmdef-dict}."""
    return {_fill(rel, prefix): _fill(content, prefix)
            for rel, content in ASMDEFS.items()}


def scaffold(project, prefix: str) -> list:
    """Legt Assets/<prefix>/ mit LAYOUT + asmdefs an. Idempotent.
    -> Liste der NEU erzeugten relativen Pfade (leer beim Zweitlauf)."""
    root = Path(project) / "Assets" / prefix
    created = []
    for rel in LAYOUT:
        d = root / rel
        if not d.is_dir():
            d.mkdir(parents=True)
            created.append(rel)
    for rel, content in asmdefs_for(prefix).items():
        p = root / rel
        if p.exists():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(content, indent=4) + "\n", encoding="utf-8")
        created.append(rel)
    return created


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True, help="Unity-Projektwurzel")
    ap.add_argument("--prefix", required=True,
                    help="Assembly-/Ordner-Prefix, PascalCase (z.B. BowlingBattle)")
    args = ap.parse_args()

    project = Path(args.project)
    if not (project / "Assets").is_dir():
        print(f"BLOCKED: {project}/Assets fehlt — kein Unity-Projekt",
              file=sys.stderr)
        return 1

    created = scaffold(project, args.prefix)
    print(f"Assets/{args.prefix}/ — {len(created)} neu angelegt:")
    for rel in created or ["(nichts — Layout bereits vollständig)"]:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Toggle release_mode (live<->patch) für ein Projekt in projects-registry.json. Fail-hard."""
import argparse
import json
import os
import sys
from pathlib import Path


def fail(msg: str) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(1)


def toggle_release_mode(hub_dir: Path, slug: str) -> str:
    registry_path = hub_dir / "projects-registry.json"
    if not registry_path.exists():
        fail(f"{registry_path} fehlt")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entry = next((e for e in registry if e.get("slug") == slug), None)
    if entry is None:
        fail(f"Slug '{slug}' nicht in Registry")
    if "release_mode" not in entry:
        fail(f"Registry-Eintrag '{slug}' hat kein release_mode-Feld")

    entry["release_mode"] = "live" if entry["release_mode"] == "patch" else "patch"
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry["release_mode"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Toggle release_mode live<->patch für ein Projekt")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--hub-dir", default=os.environ.get("HUB_DIR", ""))
    args = parser.parse_args()

    hub_dir = Path(args.hub_dir)
    if not args.hub_dir or not hub_dir.is_dir():
        fail("HUB_DIR nicht gesetzt oder kein Verzeichnis")

    new_mode = toggle_release_mode(hub_dir, args.slug)
    print(f"Deploy-Modus {args.slug}: {new_mode}")


if __name__ == "__main__":
    main()

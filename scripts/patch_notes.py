#!/usr/bin/env python3
"""Patch-Schnitt: aggregiert topics/*/patches/v*.md -> patches.json (Website),
validiert + setzt Registry-Version, bereinigt unreleased.md. Fail-hard."""
import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SECTIONS = {"Features": "features", "Fixes": "fixes",
            "Member-Hinweise": "member_notes"}


def fail(msg: str) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(1)


def semver_tuple(version: str) -> tuple:
    m = SEMVER_RE.match(version)
    if not m:
        fail(f"ungültige SemVer-Version: '{version}'")
    return tuple(int(x) for x in m.groups())


def parse_patch_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        fail(f"{path}: Frontmatter fehlt")
    fm = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    version = fm.get("version", "")
    semver_tuple(version)
    if not DATE_RE.match(fm.get("date", "")):
        fail(f"{path}: ungültiges oder fehlendes date-Feld")
    result = {"version": version, "date": fm["date"],
              "features": [], "fixes": [], "member_notes": []}
    current = None
    for line in text[m.end():].splitlines():
        heading = re.match(r"^## (.+)$", line)
        if heading:
            current = SECTIONS.get(heading.group(1).strip())
            continue
        item = re.match(r"^- (.+)$", line)
        if item and current:
            result[current].append(item.group(1).strip())
    return result


def collect_patches(hub_dir: Path, registry: list) -> list:
    names = {e["slug"]: e.get("name", e["slug"]) for e in registry}
    patches = []
    for f in sorted(hub_dir.glob("topics/*/patches/v*.md")):
        slug = f.parent.parent.name
        p = parse_patch_file(f)
        p["project"] = slug
        p["name"] = names.get(slug, slug)
        patches.append(p)
    patches.sort(key=lambda p: (p["date"], semver_tuple(p["version"])),
                 reverse=True)
    return patches


def remove_released(unreleased_path: Path, released: list) -> None:
    if not released:
        return
    if not unreleased_path.exists():
        fail(f"{unreleased_path} fehlt, aber --released übergeben")
    lines = unreleased_path.read_text(encoding="utf-8").splitlines()
    for item in released:
        if item not in lines:
            fail(f"released-Zeile nicht in unreleased.md gefunden: '{item}'")
        lines.remove(item)
    unreleased_path.write_text("\n".join(lines).rstrip("\n") + "\n",
                               encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Patch-Schnitt: patches.json + Registry-Bump + unreleased-Bereinigung")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--released", action="append", default=[],
                        help="exakte unreleased.md-Zeile (wiederholbar)")
    parser.add_argument("--hub-dir", default=os.environ.get("HUB_DIR", ""))
    parser.add_argument("--website-dir", default="/root/projekte/website")
    args = parser.parse_args()

    hub_dir = Path(args.hub_dir)
    if not args.hub_dir or not hub_dir.is_dir():
        fail("HUB_DIR nicht gesetzt oder kein Verzeichnis")
    website_dir = Path(args.website_dir)
    if not website_dir.is_dir():
        fail(f"Website-Verzeichnis fehlt: {website_dir}")

    registry_path = hub_dir / "projects-registry.json"
    if not registry_path.exists():
        fail(f"{registry_path} fehlt")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entry = next((e for e in registry if e.get("slug") == args.slug), None)
    if entry is None:
        fail(f"Slug '{args.slug}' nicht in Registry")
    if "version" not in entry:
        fail(f"Registry-Eintrag '{args.slug}' hat kein version-Feld")

    patches_dir = hub_dir / "topics" / args.slug / "patches"
    v_files = sorted(patches_dir.glob("v*.md")) if patches_dir.is_dir() else []
    if not v_files:
        fail(f"keine v*.md unter {patches_dir}")
    newest = max((parse_patch_file(f)["version"] for f in v_files),
                 key=semver_tuple)
    if semver_tuple(newest) <= semver_tuple(entry["version"]):
        fail(f"neueste Patch-Version {newest} ist nicht größer als "
             f"Registry-Version {entry['version']}")

    remove_released(patches_dir / "unreleased.md", args.released)

    entry["version"] = newest
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")

    payload = {"generated": date.today().isoformat(),
               "patches": collect_patches(hub_dir, registry)}
    out = website_dir / "patches.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"OK: {args.slug} -> v{newest}, "
          f"{len(payload['patches'])} Patches in {out}")


if __name__ == "__main__":
    main()

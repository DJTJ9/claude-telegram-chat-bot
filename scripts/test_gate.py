#!/usr/bin/env python3
"""Post-Patch-Test-Gate: init (Test-Log generieren) + check (Deploy-Gate).
Reine Datei-I/O — runt keine Tests, flippt keine Checkboxen. Fail-hard."""
import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
FAIL_MARKER = " — fail:"


def fail(msg: str) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(1)


def load_entry(hub_dir: Path, slug: str) -> dict:
    registry_path = hub_dir / "projects-registry.json"
    if not registry_path.exists():
        fail(f"{registry_path} fehlt")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entry = next((e for e in registry if e.get("slug") == slug), None)
    if entry is None:
        fail(f"Slug '{slug}' nicht in Registry")
    return entry


def log_path(hub_dir: Path, slug: str, version: str) -> Path:
    return hub_dir / "topics" / slug / "patches" / f"test-v{version}.md"


def generate_log(hub_dir: Path, slug: str, version: str,
                 auto: list, manual: list) -> Path:
    if not SEMVER_RE.match(version):
        fail(f"ungültige SemVer-Version: '{version}'")
    entry = load_entry(hub_dir, slug)
    test_cmd = entry.get("test_cmd", "")
    staging_url = entry.get("staging_url", "")
    path = log_path(hub_dir, slug, version)
    if path.exists():
        fail(f"{path} existiert bereits — vorhandenes Test-Log nicht überschreiben")
    lines = ["---",
             f"version: {version}",
             f"slug: {slug}",
             "status: pending",
             f"staging_url: {staging_url}",
             f"generated: {date.today().isoformat()}",
             "---",
             "",
             "## Auto"]
    if test_cmd:
        lines.append(f"- [ ] Suite: {test_cmd}")
    for smoke in auto:
        lines.append(f"- [ ] Smoke: {smoke}")
    lines.append("")
    lines.append("## Manuell")
    for man in manual:
        lines.append(f"- [ ] {man}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"OK: Test-Log {path} generiert "
          f"({'1' if test_cmd else '0'} Suite + {len(auto)} Smoke + "
          f"{len(manual)} Manuell)")
    return path


def parse_log(path: Path) -> tuple:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        fail(f"{path}: Frontmatter fehlt")
    fm = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    section = None
    checks = []  # (section, line)
    for line in text[m.end():].splitlines():
        h = re.match(r"^## (.+)$", line)
        if h:
            section = h.group(1).strip()
            continue
        if re.match(r"^- \[.\]", line) and section in ("Auto", "Manuell"):
            checks.append((section, line))
    return fm, checks


def check_gate(hub_dir: Path, slug: str, version: str) -> None:
    path = log_path(hub_dir, slug, version)
    if not path.exists():
        fail(f"kein Test-Log: {path} — erst `/dev test {slug}` ausführen")
    fm, checks = parse_log(path)
    if not checks:
        fail(f"{path}: keine Checkpunkte in ## Auto / ## Manuell")
    problems = []
    for section, line in checks:
        if FAIL_MARKER in line:
            problems.append(f"FEHLGESCHLAGEN [{section}]: {line}")
        elif line.startswith("- [ ]"):
            problems.append(f"OFFEN [{section}]: {line}")
    status = fm.get("status", "")
    if status != "passed":
        problems.append(f"Frontmatter status ist '{status}', erwartet 'passed'")
    if problems:
        print(f"FEHLER: Gate für {slug} v{version} ROT:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: Gate für {slug} v{version} grün — "
          f"{len(checks)} Punkte alle [x], status: passed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post-Patch-Test-Gate (fail-hard)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--slug", required=True)
    common.add_argument("--version", required=True)
    common.add_argument("--hub-dir", default=os.environ.get("HUB_DIR", ""))
    sub = parser.add_subparsers(dest="mode", required=True)
    p_init = sub.add_parser("init", parents=[common])
    p_init.add_argument("--auto", action="append", default=[],
                        help="Smoke-Zeile '<feature> — <check>' (wiederholbar)")
    p_init.add_argument("--manual", action="append", default=[],
                        help="Manuelle Zeile '<feature> — <frage>' (wiederholbar)")
    sub.add_parser("check", parents=[common])
    args = parser.parse_args()

    hub_dir = Path(args.hub_dir)
    if not args.hub_dir or not hub_dir.is_dir():
        fail("HUB_DIR nicht gesetzt oder kein Verzeichnis")

    if args.mode == "init":
        generate_log(hub_dir, args.slug, args.version, args.auto, args.manual)
    else:
        check_gate(hub_dir, args.slug, args.version)


if __name__ == "__main__":
    main()

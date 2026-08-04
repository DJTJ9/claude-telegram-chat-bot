#!/usr/bin/env python3
"""Playtest-Gate für den game-Skill: init (Log generieren) + check (Done-Gate).
Reine Datei-I/O — runt keine Tests, flippt keine Checkboxen. Fail-hard.
Modell: scripts/test_gate.py."""
import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

FAIL_MARKER = " — fail:"
DIMENSIONS = ("Feel", "Balance", "Fun", "Optik", "Bug")


def fail(msg: str) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(1)


def feature_kebab(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def load_entry(hub_dir: Path, slug: str) -> dict:
    registry_path = hub_dir / "projects-registry.json"
    if not registry_path.exists():
        fail(f"{registry_path} fehlt")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entry = next((e for e in registry if e.get("slug") == slug), None)
    if entry is None:
        fail(f"Slug '{slug}' nicht in Registry")
    return entry


def log_path(hub_dir: Path, slug: str, feature: str) -> Path:
    return (hub_dir / "topics" / slug / "playtests"
            / f"playtest-{feature_kebab(feature)}.md")


def generate_log(hub_dir: Path, slug: str, feature: str,
                 auto: str, engine: str = "") -> Path:
    entry = load_entry(hub_dir, slug)
    if not engine:
        engine = entry.get("engine", "")
    path = log_path(hub_dir, slug, feature)
    if path.exists():
        fail(f"{path} existiert bereits — vorhandenes Playtest-Log nicht überschreiben")
    lines = ["---",
             f"feature: {feature}",
             f"slug: {slug}",
             f"engine: {engine}",
             "status: pending",
             f"generated: {date.today().isoformat()}",
             "---",
             "",
             "## Auto-Logik",
             f"- [ ] {auto}",
             "",
             "## Playtest"]
    for dim in DIMENSIONS:
        lines.append(f"- [ ] {dim} — ")
    lines += ["", "## Tuning-Diffs", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"OK: Playtest-Log {path} generiert (Auto-Logik: {auto})")
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
        if re.match(r"^- \[.\]", line) and section in ("Auto-Logik", "Playtest"):
            checks.append((section, line))
    return fm, checks


def check_gate(hub_dir: Path, slug: str, feature: str) -> None:
    path = log_path(hub_dir, slug, feature)
    if not path.exists():
        fail(f"kein Playtest-Log: {path} — erst `/game playtest` ausführen")
    fm, checks = parse_log(path)
    if not checks:
        fail(f"{path}: keine Checkpunkte in ## Auto-Logik / ## Playtest")
    problems = []
    for section, line in checks:
        if FAIL_MARKER in line:
            problems.append(f"FEHLGESCHLAGEN [{section}]: {line}")
        elif line.startswith("- [ ]"):
            if section == "Auto-Logik" and "N/A" in line:
                continue  # explizit N/A für reine [feel]-Features
            problems.append(f"OFFEN [{section}]: {line}")
    status = fm.get("status", "")
    if status != "passed":
        problems.append(f"Frontmatter status ist '{status}', erwartet 'passed'")
    if problems:
        print(f"FEHLER: Playtest-Gate für {slug}/{feature} ROT:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: Playtest-Gate für {slug}/{feature} grün — "
          f"{len(checks)} Punkte, status: passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Playtest-Gate (fail-hard)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--slug", required=True)
    common.add_argument("--feature", required=True)
    common.add_argument("--hub-dir", default=os.environ.get("HUB_DIR", ""))
    sub = parser.add_subparsers(dest="mode", required=True)
    p_init = sub.add_parser("init", parents=[common])
    p_init.add_argument("--auto", default="N/A — reines [feel]-Feature",
                        help="Auto-Logik-Zeile (Test-Ergebnis oder 'N/A')")
    sub.add_parser("check", parents=[common])
    args = parser.parse_args()

    hub_dir = Path(args.hub_dir)
    if not args.hub_dir or not hub_dir.is_dir():
        fail("HUB_DIR nicht gesetzt oder kein Verzeichnis")

    if args.mode == "init":
        generate_log(hub_dir, args.slug, args.feature, args.auto)
    else:
        check_gate(hub_dir, args.slug, args.feature)


if __name__ == "__main__":
    main()

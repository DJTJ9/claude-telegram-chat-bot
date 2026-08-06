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

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.console import enable_safe_console

# Feature-Namen enthalten regelmäßig Zeichen außerhalb von cp1252 (→, –, …).
# Ohne das hier wirft print() auf der Windows-Konsole UnicodeEncodeError und ein
# grüner Gate endet mit Exit 1 — ein falsches Rot, das wie ein echtes aussieht.
enable_safe_console()

FAIL_MARKER = " — fail:"
DIMENSIONS = ("Feel", "Balance", "Fun", "Optik", "Bug")
UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
MAX_KEBAB = 60


def fail(msg: str) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(1)


def feature_kebab(name: str) -> str:
    """Feature-Name → Dateiname-Kebab.

    Umlaute werden ausgeschrieben, sonst würde `Öl-Physik` zu `-l-physik`.
    Auf MAX_KEBAB gekürzt und an der letzten Bindestrich-Grenze abgeschnitten —
    Feature-Namen sind oft ganze Sätze, der volle Kebab ergäbe 100-Zeichen-Dateinamen.
    """
    s = name.lower()
    for src, dst in UMLAUTS.items():
        s = s.replace(src, dst)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) <= MAX_KEBAB:
        return s
    cut = s[:MAX_KEBAB]
    return cut[:cut.rindex("-")] if "-" in cut else cut


def roadmap_key(hub_dir: Path, slug: str, feature: str) -> str:
    """`#key:<kebab>`-Anker des Features aus STATUS.md; "" wenn keiner da ist.

    Stabiler als der abgeleitete Kebab: der Anker überlebt eine Umformulierung
    des Feature-Namens, der Kebab würde dabei auf eine neue Datei zeigen und
    das vorhandene Log unauffindbar machen.
    """
    path = hub_dir / "topics" / slug / "STATUS.md"
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("- [") or feature not in line:
            continue
        m = re.search(r"key:(\S+)", line)
        if m:
            return m.group(1)
    return ""


def load_entry(hub_dir: Path, slug: str) -> dict:
    registry_path = hub_dir / "projects-registry.json"
    if not registry_path.exists():
        fail(f"{registry_path} fehlt")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entry = next((e for e in registry if e.get("slug") == slug), None)
    if entry is None:
        fail(f"Slug '{slug}' nicht in Registry")
    return entry


def log_path(hub_dir: Path, slug: str, feature: str, key: str = "") -> Path:
    name = key or roadmap_key(hub_dir, slug, feature) or feature_kebab(feature)
    if not name:
        fail(f"aus '{feature}' lässt sich kein Dateiname ableiten — --key setzen")
    return hub_dir / "topics" / slug / "playtests" / f"playtest-{name}.md"


def generate_log(hub_dir: Path, slug: str, feature: str,
                 auto: str, engine: str = "", key: str = "") -> Path:
    entry = load_entry(hub_dir, slug)
    if not engine:
        engine = entry.get("engine", "")
    path = log_path(hub_dir, slug, feature, key)
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
    prose_fails = []  # Fail-Marker außerhalb der Checkbox-Zeilen
    for line in text[m.end():].splitlines():
        h = re.match(r"^## (.+)$", line)
        if h:
            section = h.group(1).strip()
            continue
        if re.match(r"^- \[.\]", line) and section in ("Auto-Logik", "Playtest"):
            checks.append((section, line))
        elif FAIL_MARKER in line:
            prose_fails.append(line.strip())
    return fm, checks, prose_fails


def check_gate(hub_dir: Path, slug: str, feature: str, key: str = "") -> None:
    path = log_path(hub_dir, slug, feature, key)
    if not path.exists():
        fail(f"kein Playtest-Log: {path} — erst `/game playtest` ausführen")
    fm, checks, prose_fails = parse_log(path)
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
    # Eine fehlende Dimension wäre sonst ein bestandener Gate durch Weglassen.
    play = [l for s, l in checks if s == "Playtest"]
    for dim in DIMENSIONS:
        if not any(re.search(rf"\[.\]\s*{re.escape(dim)}\b", l) for l in play):
            problems.append(f"Dimension '{dim}' fehlt in ## Playtest")
    for line in prose_fails:
        problems.append(f"FEHLGESCHLAGEN [Fließtext]: {line}")
    status = fm.get("status", "")
    if status != "passed":
        problems.append(f"Frontmatter status ist '{status}', erwartet 'passed'")
    if problems:
        print(f"FEHLER: Playtest-Gate für {slug} ROT ({path.name}):",
              file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: Playtest-Gate für {slug} grün ({path.name}) — "
          f"{len(checks)} Punkte, status: passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Playtest-Gate (fail-hard)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--slug", required=True)
    common.add_argument("--feature", required=True)
    common.add_argument("--key", default="",
                        help="Dateiname-Anker überschreiben (sonst #key: aus "
                             "STATUS.md, sonst Kebab des Feature-Namens)")
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
        generate_log(hub_dir, args.slug, args.feature, args.auto, key=args.key)
    else:
        check_gate(hub_dir, args.slug, args.feature, args.key)


if __name__ == "__main__":
    main()

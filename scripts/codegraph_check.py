#!/usr/bin/env python3
"""Fail-hard-Gate für die plan-discovery: validiert referenzierte Symbole gegen
den code-review-graph-Graph (erfunden -> exit 1) und injiziert den Blast-Radius
der Zieldateien. Pilot: job-scanner.

Liest einen `<!-- codegraph-check symbols:… files:… -->`-Block aus dem Plan-Entwurf.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.console import enable_safe_console

enable_safe_console()


_BLOCK_RE = re.compile(r"<!--\s*codegraph-check\b(.*?)-->", re.DOTALL)


def _binary() -> str:
    exe = shutil.which("code-review-graph")
    if not exe:
        print("BLOCKED: 'code-review-graph' nicht auf PATH — "
              "pip install code-review-graph", file=sys.stderr)
        sys.exit(1)
    return exe


def parse_block(text: str):
    """(-> symbols:list, files:list) oder (None, None) wenn kein Block."""
    m = _BLOCK_RE.search(text)
    if not m:
        return (None, None)
    body = m.group(1)

    def _field(name: str) -> list:
        fm = re.search(rf"{name}\s*:\s*([^\n]*)", body)
        if not fm:
            return []
        return [x.strip() for x in fm.group(1).split(",") if x.strip()]

    return (_field("symbols"), _field("files"))


def run_crg(args: list) -> dict:
    """Ein code-review-graph-Subcommand -> geparster JSON-Wert von stdout."""
    proc = subprocess.run([_binary(), *args], capture_output=True, text=True)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(f"BLOCKED: kein JSON von 'code-review-graph {' '.join(args)}'\n"
              f"stderr: {proc.stderr[-500:]}", file=sys.stderr)
        sys.exit(1)


def _rebuild(repo: str) -> None:
    """Vollrebuild (~3.7 s, keine Git-Abhängigkeit, CALLS + TESTED_BY)."""
    proc = subprocess.run(
        [_binary(), "build", "--repo", repo, "-q", "--skip-flows"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"BLOCKED: Graph-Build fehlgeschlagen für {repo}\n"
              f"stderr: {proc.stderr[-500:]}", file=sys.stderr)
        sys.exit(1)


def partition_callers(results: list):
    """callers_of-Results -> (echte Caller, Tests) per is_test-Feld."""
    callers = [r["name"] for r in results if not r.get("is_test")]
    tests = [r["name"] for r in results if r.get("is_test")]
    return callers, tests


def check_symbol(repo: str, sym: str):
    """(-> exists:bool, callers:list, tests:list).

    not_found => existiert nicht. ok/ambiguous => existiert (ambiguous =
    mehrfach definiert, keine aufgelösten Caller).
    """
    d = run_crg(["query", "callers_of", sym, "--repo", repo])
    status = d.get("status")
    if status == "not_found":
        return (False, [], [])
    if status == "ambiguous":
        return (True, [], [])
    callers, tests = partition_callers(d.get("results", []))
    return (True, callers, tests)


def impact_for_file(repo: str, path: str) -> dict:
    d = run_crg(["impact", "--files", path, "--repo", repo])
    return {
        "file": path,
        "total_impacted": d.get("total_impacted", 0),
        "impacted_file_count": len(d.get("impacted_files", [])),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="codegraph-check: Symbol-Existenz + Blast-Radius-Gate")
    ap.add_argument("--repo", required=True, help="Ziel-Repo (Pilot: /opt/jobscanner)")
    ap.add_argument("--plan", required=True, help="Plan-Entwurf mit codegraph-check-Block")
    args = ap.parse_args(argv)

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"BLOCKED: Plan-Datei nicht gefunden: {args.plan}", file=sys.stderr)
        return 1

    symbols, files = parse_block(plan_path.read_text(encoding="utf-8"))
    if symbols is None:
        print("BLOCKED: kein <!-- codegraph-check … --> Block im Plan-Entwurf.",
              file=sys.stderr)
        return 1

    _rebuild(args.repo)

    missing = []
    sym_report = []
    for sym in symbols:
        exists, callers, tests = check_symbol(args.repo, sym)
        if not exists:
            missing.append(sym)
        else:
            sym_report.append((sym, callers, tests))

    if missing:
        print("BLOCKED: erfundene / unbekannte Symbole im Plan:", file=sys.stderr)
        for s in missing:
            print(f"  ✗ {s}  (kein Node im Graph)", file=sys.stderr)
        print("Korrigiere die Namen gegen den echten Code und re-run.", file=sys.stderr)
        return 1

    # Pass -> Blast-Radius-Report auf stdout (plan.md faltet ihn in den Plan).
    print("=== codegraph-check: PASS ===")
    print("Symbole (Existenz bestätigt) + Blast-Radius:")
    for sym, callers, tests in sym_report:
        print(f"  • {sym}: {len(callers)} Caller, {len(tests)} Tests")
        if callers:
            print(f"      Caller: {', '.join(callers[:8])}"
                  + (" …" if len(callers) > 8 else ""))
        if tests:
            print(f"      Tests:  {', '.join(tests[:8])}"
                  + (" …" if len(tests) > 8 else ""))
    if files:
        print("Datei-Blast-Radius:")
        for f in files:
            summ = impact_for_file(args.repo, f)
            print(f"  • {summ['file']}: {summ['total_impacted']} Nodes betroffen, "
                  f"{summ['impacted_file_count']} weitere Dateien")
    return 0


if __name__ == "__main__":
    sys.exit(main())

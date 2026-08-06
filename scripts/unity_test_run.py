#!/usr/bin/env python3
"""Fährt die Unity-Testsuite eines Projekts headless im GameCI-Container
(-batchmode -nographics -runTests), parst das NUnit3-results.xml und meldet
fail-hard zurück. Aufrufer: /game implement nach jedem [logic]-Task.

Exit 0 = results.xml da und failed == 0
Exit 1 = mindestens ein Failure ODER kein/kaputtes results.xml (Compile-Fehler)
Exit 2 = BLOCKED (docker fehlt, Lizenz fehlt, kein ProjectVersion.txt, Timeout)
"""
import argparse
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.console import enable_safe_console

enable_safe_console()


try:
    from scripts.unity_compile_check import image_tag  # Test-Kontext (Repo-Root auf sys.path)
except ImportError:
    from unity_compile_check import image_tag  # Script-Kontext (scripts/ ist sys.path[0])

PLATFORMS = ("EditMode", "PlayMode")
# Spiegelt den Mount aus unity_compile_check.docker_cmd — dort ist das Kommando
# auf -executeMethod festgelegt und für -runTests nicht wiederverwendbar.
LICENSE_MOUNT = "/root/.local/share/unity3d/Unity/Unity_lic.ulf"


def results_path(project: Path, platform: str) -> Path:
    """Ablage des NUnit3-Reports einer Plattform (Host-Sicht)."""
    return Path(project) / "Logs" / f"results-{platform}.xml"


def docker_cmd(project: Path, license_path: Path, tag: str, platform: str) -> list:
    """docker-run-Kommando für einen headless Testlauf einer Plattform."""
    return [
        "docker", "run", "--rm",
        "-v", f"{project}:/project",
        "-v", f"{license_path}:{LICENSE_MOUNT}",
        tag,
        "unity-editor", "-batchmode", "-nographics", "-runTests",
        "-projectPath", "/project",
        "-testPlatform", platform,
        "-testResults", f"/project/Logs/results-{platform}.xml",
        "-logFile", "-",
    ]


def parse_results(path: Path) -> dict:
    """NUnit3-Report -> Zähler + Failures [(fullname, erste Message-Zeile)]."""
    root = ET.parse(str(path)).getroot()
    res = {k: int(root.get(k, 0))
           for k in ("total", "passed", "failed", "skipped")}
    failures = []
    for case in root.iter("test-case"):
        if case.get("result") != "Failed":
            continue
        msg = case.findtext("failure/message") or ""
        first = next((ln.strip() for ln in msg.splitlines() if ln.strip()), "")
        failures.append((case.get("fullname") or case.get("name") or "?", first))
    res["failures"] = failures
    return res


def run_platform(project: Path, license_path: Path, tag: str, platform: str,
                 timeout: int):
    """Ein Docker-Testlauf. -> (exit_code, counts) — counts None, wenn kein
    verwertbares results.xml entstand."""
    results = results_path(project, platform)
    if results.exists():
        results.unlink()  # kein altes Ergebnis erben, wenn Unity abbricht

    print(f"\n=== {platform} — {tag}")
    try:
        proc = subprocess.run(docker_cmd(project, license_path, tag, platform),
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"BLOCKED: {platform} — Timeout nach {timeout}s", file=sys.stderr)
        return 2, None

    if not results.exists():
        log = (proc.stdout or "") + (proc.stderr or "")
        print(f"{platform}: kein results.xml (Unity-Exit {proc.returncode}) — "
              f"Compile-Fehler? Log-Ende:\n{log[-2000:]}", file=sys.stderr)
        return 1, None
    try:
        counts = parse_results(results)
    except ET.ParseError as exc:
        print(f"{platform}: results.xml unlesbar ({exc})", file=sys.stderr)
        return 1, None

    print(f"{platform}: {counts['passed']}/{counts['total']} passed, "
          f"{counts['failed']} failed, {counts['skipped']} skipped")
    for name, msg in counts["failures"]:
        print(f"  FAIL {name}: {msg}")
    return (1 if counts["failed"] else 0), counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True, help="Unity-Projektwurzel")
    ap.add_argument("--platform", choices=[*PLATFORMS, "both"], default="both")
    ap.add_argument("--license", default="/root/secrets/unity/Unity_lic.ulf")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()

    project, lic = Path(args.project), Path(args.license)
    if not shutil.which("docker"):
        print("BLOCKED: docker nicht auf PATH", file=sys.stderr)
        return 2
    if not lic.exists():
        print(f"BLOCKED: Unity-Lizenz {lic} fehlt", file=sys.stderr)
        return 2
    try:
        tag = image_tag(project)
    except SystemExit:
        return 2  # image_tag hat die Ursache bereits nach stderr geschrieben

    platforms = PLATFORMS if args.platform == "both" else (args.platform,)
    worst = 0
    for platform in platforms:
        code, counts = run_platform(project, lic, tag, platform, args.timeout)
        if counts is None:
            return code  # BLOCKED oder kein results.xml -> zweite Plattform sinnlos
        worst = max(worst, code)

    print("\nPASS — alle Unity-Tests grün." if worst == 0
          else "\nFAIL — siehe Failures oben.")
    return worst


if __name__ == "__main__":
    sys.exit(main())

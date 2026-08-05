import sys, unittest, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.unity_test_run import (
    results_path, docker_cmd, parse_results, run_platform, main,
    PLATFORMS, LICENSE_MOUNT,
)

GREEN_XML = """<?xml version="1.0" encoding="utf-8"?>
<test-run id="2" testcasecount="2" result="Passed" total="2" passed="2" failed="0"
          inconclusive="0" skipped="0">
  <test-suite type="TestSuite" name="project">
    <test-case id="1010" name="Double_Doubles" fullname="DummyEditModeTests.Double_Doubles"
               result="Passed" />
  </test-suite>
</test-run>
"""

RED_XML = """<?xml version="1.0" encoding="utf-8"?>
<test-run id="2" testcasecount="2" result="Failed(Child)" total="2" passed="1" failed="1"
          inconclusive="0" skipped="0">
  <test-suite type="TestSuite" name="project">
    <test-case id="1010" name="Double_Doubles" fullname="DummyEditModeTests.Double_Doubles"
               result="Failed">
      <failure>
        <message><![CDATA[  Expected: 5
  But was:  4
]]></message>
      </failure>
    </test-case>
  </test-suite>
</test-run>
"""


def _project(tmp, version="6000.4.3f1"):
    """Unity-Projektwurzel mit ProjectVersion.txt in tmp."""
    project = Path(tmp) / "project"
    pv = project / "ProjectSettings" / "ProjectVersion.txt"
    pv.parent.mkdir(parents=True)
    pv.write_text(f"m_EditorVersion: {version}\n")
    (project / "Logs").mkdir()
    return project


def _writer(project, platform, xml):
    """subprocess.run-Ersatz, der results-<platform>.xml schreibt."""
    def run(cmd, **kwargs):
        results_path(project, platform).write_text(xml, encoding="utf-8")
        m = MagicMock()
        m.returncode = 0 if "Passed" in xml else 2
        m.stdout = m.stderr = ""
        return m
    return run


class TestParseResults(unittest.TestCase):
    def test_green_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "r.xml"
            p.write_text(GREEN_XML, encoding="utf-8")
            res = parse_results(p)
            self.assertEqual((res["total"], res["passed"], res["failed"],
                              res["skipped"]), (2, 2, 0, 0))
            self.assertEqual(res["failures"], [])

    def test_failure_name_and_first_message_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "r.xml"
            p.write_text(RED_XML, encoding="utf-8")
            res = parse_results(p)
            self.assertEqual(res["failed"], 1)
            self.assertEqual(res["failures"],
                             [("DummyEditModeTests.Double_Doubles", "Expected: 5")])


class TestDockerCmd(unittest.TestCase):
    def test_runtests_flags_and_mounts(self):
        cmd = docker_cmd(Path("/root/unity-scratch"),
                         Path("/root/secrets/unity/Unity_lic.ulf"),
                         "unityci/editor:ubuntu-6000.4.3f1-base-3", "PlayMode")
        self.assertEqual(cmd[:3], ["docker", "run", "--rm"])
        self.assertIn("/root/unity-scratch:/project", cmd)
        self.assertIn(f"/root/secrets/unity/Unity_lic.ulf:{LICENSE_MOUNT}", cmd)
        self.assertIn("-runTests", cmd)
        self.assertIn("-nographics", cmd)
        self.assertEqual(cmd[cmd.index("-testPlatform") + 1], "PlayMode")
        self.assertEqual(cmd[cmd.index("-testResults") + 1],
                         "/project/Logs/results-PlayMode.xml")
        self.assertNotIn("-executeMethod", cmd)


class TestRunPlatform(unittest.TestCase):
    def test_green_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            with patch("scripts.unity_test_run.subprocess.run",
                       side_effect=_writer(project, "EditMode", GREEN_XML)):
                code, counts = run_platform(project, Path("/lic"), "tag",
                                            "EditMode", 60)
            self.assertEqual(code, 0)
            self.assertEqual(counts["passed"], 2)

    def test_failure_returns_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            with patch("scripts.unity_test_run.subprocess.run",
                       side_effect=_writer(project, "EditMode", RED_XML)):
                code, counts = run_platform(project, Path("/lic"), "tag",
                                            "EditMode", 60)
            self.assertEqual(code, 1)
            self.assertEqual(counts["failures"][0][0],
                             "DummyEditModeTests.Double_Doubles")

    def test_stale_results_deleted_before_run(self):
        """Altes grünes XML + Lauf, der nichts schreibt -> Exit 1, nicht 0."""
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            results_path(project, "EditMode").write_text(GREEN_XML, encoding="utf-8")
            proc = MagicMock(returncode=1, stdout="error CS0246", stderr="")
            with patch("scripts.unity_test_run.subprocess.run", return_value=proc):
                code, counts = run_platform(project, Path("/lic"), "tag",
                                            "EditMode", 60)
            self.assertEqual(code, 1)
            self.assertIsNone(counts)
            self.assertFalse(results_path(project, "EditMode").exists())

    def test_timeout_blocks(self):
        import subprocess as sp
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            with patch("scripts.unity_test_run.subprocess.run",
                       side_effect=sp.TimeoutExpired("docker", 60)):
                code, counts = run_platform(project, Path("/lic"), "tag",
                                            "EditMode", 60)
            self.assertEqual(code, 2)
            self.assertIsNone(counts)


class TestMain(unittest.TestCase):
    @patch("scripts.unity_test_run.shutil.which", return_value="/usr/bin/docker")
    def test_both_platforms_green_exits_zero(self, _which):
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            lic = Path(tmp) / "Unity_lic.ulf"
            lic.write_text("<lic/>")
            calls = []

            def run(cmd, **kwargs):
                platform = cmd[cmd.index("-testPlatform") + 1]
                calls.append(platform)
                results_path(project, platform).write_text(GREEN_XML, encoding="utf-8")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch("scripts.unity_test_run.subprocess.run", side_effect=run):
                with patch("sys.argv", ["unity_test_run.py", "--project", str(project),
                                        "--license", str(lic)]):
                    self.assertEqual(main(), 0)
            self.assertEqual(calls, list(PLATFORMS))

    @patch("scripts.unity_test_run.shutil.which", return_value="/usr/bin/docker")
    def test_failure_exits_one(self, _which):
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            lic = Path(tmp) / "Unity_lic.ulf"
            lic.write_text("<lic/>")
            with patch("scripts.unity_test_run.subprocess.run",
                       side_effect=_writer(project, "EditMode", RED_XML)):
                with patch("sys.argv", ["unity_test_run.py", "--project", str(project),
                                        "--license", str(lic),
                                        "--platform", "EditMode"]):
                    self.assertEqual(main(), 1)

    @patch("scripts.unity_test_run.shutil.which", return_value=None)
    def test_missing_docker_blocks(self, _which):
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            with patch("sys.argv", ["unity_test_run.py", "--project", str(project)]):
                self.assertEqual(main(), 2)

    @patch("scripts.unity_test_run.shutil.which", return_value="/usr/bin/docker")
    def test_missing_license_blocks(self, _which):
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            with patch("sys.argv", ["unity_test_run.py", "--project", str(project),
                                    "--license", str(Path(tmp) / "nope.ulf")]):
                self.assertEqual(main(), 2)

    @patch("scripts.unity_test_run.shutil.which", return_value="/usr/bin/docker")
    def test_missing_projectversion_blocks(self, _which):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "not-unity"
            project.mkdir()
            lic = Path(tmp) / "Unity_lic.ulf"
            lic.write_text("<lic/>")
            with patch("sys.argv", ["unity_test_run.py", "--project", str(project),
                                    "--license", str(lic)]):
                self.assertEqual(main(), 2)


if __name__ == "__main__":
    unittest.main()

import sys, unittest, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.unity_compile_check import (
    extract_blocks, class_name, placement, write_project_files,
    image_tag, docker_cmd, parse_log, main, PREFIX, FEATURE,
)

SAMPLE_MD = """# Doc
```csharp
using UnityEngine;
using UnityEditor;

public static class EditorThing
{
    [MenuItem("Tools/X")]
    public static void Go() {}
}
```
prose
```bash
echo ignored
```
```csharp
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

public class RuntimeThing : MonoBehaviour {}
```
```csharp
using NUnit.Framework;

public class ThingEditModeTests {}
```
```csharp
using System.Collections;
using NUnit.Framework;
using UnityEngine.TestTools;

public class ThingPlayModeTests
{
    [UnityTest]
    public System.Collections.IEnumerator Runs() { yield return null; }
}
```
"""

REAL_MD = Path.home() / ".claude" / "skills" / "game" / "references" / "unity.md"


class TestExtractBlocks(unittest.TestCase):
    def test_only_csharp_fences(self):
        blocks = extract_blocks(SAMPLE_MD)
        self.assertEqual(len(blocks), 4)
        self.assertNotIn("echo ignored", "".join(blocks))

    @unittest.skipUnless(REAL_MD.exists(), "references/unity.md nicht auf dieser Maschine")
    def test_real_file_has_nine_blocks(self):
        blocks = extract_blocks(REAL_MD.read_text(encoding="utf-8"))
        self.assertEqual(len(blocks), 9)
        names = [class_name(b) for b in blocks]
        self.assertEqual(names, [
            "FeatureHarness", "DebugCheats", "CaptureScreenshot", "PlaytestSeed",
            "FeatureTuning", "PlayerController", "BuildScript",
            "FeatureEditModeTests", "FeaturePlayModeTests",
        ])
        self.assertEqual([placement(b) for b in blocks], [
            "Editor/Templates", "Runtime/Templates", "Runtime/Templates",
            "Runtime/Templates", "Runtime/Templates", "Runtime/Templates",
            "Editor/Templates", "Tests/EditMode/Templates",
            "Tests/PlayMode/Templates",
        ])


class TestClassName(unittest.TestCase):
    def test_first_class_wins(self):
        blocks = extract_blocks(SAMPLE_MD)
        self.assertEqual(class_name(blocks[0]), "EditorThing")

    def test_no_class_returns_none(self):
        self.assertIsNone(class_name("// nur ein Kommentar\n"))


class TestPlacement(unittest.TestCase):
    def setUp(self):
        self.blocks = extract_blocks(SAMPLE_MD)

    def test_unguarded_unityeditor_is_editor(self):
        self.assertEqual(placement(self.blocks[0]), "Editor/Templates")

    def test_guarded_unityeditor_is_runtime(self):
        self.assertEqual(placement(self.blocks[1]), "Runtime/Templates")

    def test_nunit_is_editmode(self):
        self.assertEqual(placement(self.blocks[2]), "Tests/EditMode/Templates")

    def test_unitytest_is_playmode(self):
        self.assertEqual(placement(self.blocks[3]), "Tests/PlayMode/Templates")


class TestScratchConstants(unittest.TestCase):
    def test_prefix_and_feature(self):
        self.assertEqual(PREFIX, "Skill")
        self.assertEqual(FEATURE, "Templates")


class TestWriteProjectFiles(unittest.TestCase):
    def test_wipes_and_writes_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            stale = scratch / "Assets" / "Skill" / "Runtime" / "Old.cs"
            stale.parent.mkdir(parents=True)
            stale.write_text("old", encoding="utf-8")

            written = write_project_files(extract_blocks(SAMPLE_MD), scratch)

            skill = scratch / "Assets" / "Skill"
            self.assertFalse(stale.exists())
            self.assertEqual(sorted(written), sorted([
                "Editor/Templates/EditorThing.cs",
                "Runtime/Templates/RuntimeThing.cs",
                "Tests/EditMode/Templates/ThingEditModeTests.cs",
                "Tests/PlayMode/Templates/ThingPlayModeTests.cs",
            ]))
            for rel in written:
                self.assertTrue((skill / rel).exists())
            for asmdef in [
                "Runtime/Skill.Runtime.asmdef", "Editor/Skill.Editor.asmdef",
                "Tests/EditMode/Skill.Tests.EditMode.asmdef",
                "Tests/PlayMode/Skill.Tests.PlayMode.asmdef",
            ]:
                self.assertTrue((skill / asmdef).exists(), asmdef)
            self.assertTrue((skill / "Runtime" / "Shared").is_dir())

    def test_block_without_class_fails_hard(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                write_project_files(["// kein typ\n"], Path(tmp))


class TestImageTag(unittest.TestCase):
    def test_version_from_projectversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            pv = Path(tmp) / "ProjectSettings" / "ProjectVersion.txt"
            pv.parent.mkdir(parents=True)
            pv.write_text("m_EditorVersion: 6000.0.32f1\n"
                          "m_EditorVersionWithRevision: 6000.0.32f1 (12345abc)\n", encoding="utf-8")
            self.assertEqual(image_tag(Path(tmp)),
                             "unityci/editor:ubuntu-6000.0.32f1-base-3")

    def test_missing_projectversion_fails_hard(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                image_tag(Path(tmp))


class TestDockerCmd(unittest.TestCase):
    def test_mounts_and_execute_method(self):
        cmd = docker_cmd(Path("/root/unity-scratch"),
                         Path("/root/secrets/unity/Unity_lic.ulf"),
                         "unityci/editor:ubuntu-6000.0.32f1-base-3")
        self.assertEqual(cmd[:3], ["docker", "run", "--rm"])
        self.assertIn("/root/unity-scratch:/project", cmd)
        self.assertIn("/root/secrets/unity/Unity_lic.ulf:"
                      "/root/.local/share/unity3d/Unity/Unity_lic.ulf", cmd)
        self.assertIn("-executeMethod", cmd)
        self.assertIn("SkillCheck.Run", cmd)
        self.assertNotIn("-quit", cmd)


class TestParseLog(unittest.TestCase):
    def test_compile_errors_deduped(self):
        log = ("Assets/Skill/Runtime/X.cs(5,1): error CS0246: type not found\n"
               "Assets/Skill/Runtime/X.cs(5,1): error CS0246: type not found\n"
               "warning CS0618: obsolete\n")
        res = parse_log(log)
        self.assertEqual(len(res["errors"]), 1)
        self.assertIn("CS0246", res["errors"][0])
        self.assertFalse(res["result_pass"])

    def test_menu_markers_and_pass(self):
        log = ("[SkillCheck] MENUITEM OK: Tools/Playtest/Feature\n"
               "[SkillCheck] MENUITEM MISSING: Tools/Build/WebGL\n"
               "[SkillCheck] RESULT PASS\n")
        res = parse_log(log)
        self.assertEqual(res["menu_ok"], ["Tools/Playtest/Feature"])
        self.assertEqual(res["menu_missing"], ["Tools/Build/WebGL"])
        self.assertTrue(res["result_pass"])


def _env(tmp):
    """Baut md/scratch/license in tmp, gibt argv zurück."""
    md = Path(tmp) / "unity.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    scratch = Path(tmp) / "scratch"
    pv = scratch / "ProjectSettings" / "ProjectVersion.txt"
    pv.parent.mkdir(parents=True)
    pv.write_text("m_EditorVersion: 6000.0.32f1\n", encoding="utf-8")
    lic = Path(tmp) / "Unity_lic.ulf"
    lic.write_text("<lic/>", encoding="utf-8")
    return ["unity_compile_check.py", "--md", str(md),
            "--scratch", str(scratch), "--license", str(lic)]


def _proc(rc, out):
    m = MagicMock()
    m.returncode = rc
    m.stdout = out
    m.stderr = ""
    return m


class TestMain(unittest.TestCase):
    @patch("scripts.unity_compile_check.shutil.which", return_value="/usr/bin/docker")
    @patch("scripts.unity_compile_check.subprocess.run")
    def test_pass_exits_zero(self, run, _which):
        run.return_value = _proc(0, "[SkillCheck] MENUITEM OK: Tools/X\n"
                                    "[SkillCheck] RESULT PASS\n")
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.argv", _env(tmp)):
                self.assertEqual(main(), 0)

    @patch("scripts.unity_compile_check.shutil.which", return_value="/usr/bin/docker")
    @patch("scripts.unity_compile_check.subprocess.run")
    def test_compile_error_exits_one(self, run, _which):
        run.return_value = _proc(1, "Assets/Skill/Runtime/X.cs(5,1): "
                                    "error CS0246: type not found\n")
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.argv", _env(tmp)):
                self.assertEqual(main(), 1)

    @patch("scripts.unity_compile_check.shutil.which", return_value="/usr/bin/docker")
    @patch("scripts.unity_compile_check.subprocess.run")
    def test_missing_menuitem_exits_one(self, run, _which):
        run.return_value = _proc(1, "[SkillCheck] MENUITEM MISSING: Tools/Build/WebGL\n"
                                    "[SkillCheck] RESULT FAIL\n")
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.argv", _env(tmp)):
                self.assertEqual(main(), 1)

    def test_missing_license_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = _env(tmp)
            Path(argv[argv.index("--license") + 1]).unlink()
            with patch("sys.argv", argv):
                self.assertEqual(main(), 1)


if __name__ == "__main__":
    unittest.main()

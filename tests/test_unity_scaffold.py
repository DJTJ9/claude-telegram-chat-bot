import json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.unity_scaffold import (
    LAYOUT, ASMDEFS, asmdefs_for, scaffold, main,
)

CONVENTIONS = Path("/root/.claude/skills/game/references/unity-conventions.md")


class TestAsmdefsFor(unittest.TestCase):
    def test_prefix_substituted_in_paths_and_content(self):
        a = asmdefs_for("Bowling")
        self.assertIn("Runtime/Bowling.Runtime.asmdef", a)
        self.assertEqual(a["Editor/Bowling.Editor.asmdef"]["name"], "Bowling.Editor")
        self.assertEqual(a["Editor/Bowling.Editor.asmdef"]["references"],
                         ["Bowling.Runtime"])
        self.assertNotIn("{prefix}", json.dumps(a))

    def test_test_assemblies_keep_nunit_settings(self):
        a = asmdefs_for("Bowling")
        for rel in ("Tests/EditMode/Bowling.Tests.EditMode.asmdef",
                    "Tests/PlayMode/Bowling.Tests.PlayMode.asmdef"):
            self.assertTrue(a[rel]["overrideReferences"], rel)
            self.assertEqual(a[rel]["precompiledReferences"],
                             ["nunit.framework.dll"], rel)
            self.assertFalse(a[rel]["autoReferenced"], rel)
            self.assertEqual(a[rel]["defineConstraints"],
                             ["UNITY_INCLUDE_TESTS"], rel)
            self.assertIn("Bowling.Runtime", a[rel]["references"], rel)

    def test_constants_are_not_empty(self):
        self.assertIn("Runtime/Shared", LAYOUT)
        self.assertEqual(len(ASMDEFS), 4)


class TestScaffold(unittest.TestCase):
    def test_creates_layout_and_asmdefs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "Assets").mkdir()

            created = scaffold(project, "Bowling")

            root = project / "Assets" / "Bowling"
            for rel in LAYOUT:
                self.assertTrue((root / rel).is_dir(), rel)
            for rel in asmdefs_for("Bowling"):
                self.assertTrue((root / rel).is_file(), rel)
            self.assertEqual(len(created), len(LAYOUT) + 4)
            content = json.loads(
                (root / "Runtime/Bowling.Runtime.asmdef").read_text(encoding="utf-8"))
            self.assertEqual(content, {"name": "Bowling.Runtime"})

    def test_idempotent_second_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "Assets").mkdir()
            scaffold(project, "Bowling")

            root = project / "Assets" / "Bowling"
            code = root / "Runtime" / "Jump" / "JumpController.cs"
            code.parent.mkdir(parents=True)
            code.write_text("// handgeschrieben", encoding="utf-8")
            asmdef = root / "Runtime/Bowling.Runtime.asmdef"
            asmdef.write_text('{"name": "Bowling.Runtime", "noEngineReferences": true}\n',
                              encoding="utf-8")

            created = scaffold(project, "Bowling")

            self.assertEqual(created, [])
            self.assertEqual(code.read_text(encoding="utf-8"), "// handgeschrieben")
            self.assertIn("noEngineReferences", asmdef.read_text(encoding="utf-8"))


class TestMain(unittest.TestCase):
    def test_missing_assets_dir_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.argv", ["unity_scaffold.py", "--project", tmp,
                                    "--prefix", "Bowling"]):
                self.assertEqual(main(), 1)

    def test_scaffolds_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Assets").mkdir()
            with patch("sys.argv", ["unity_scaffold.py", "--project", tmp,
                                    "--prefix", "Bowling"]):
                self.assertEqual(main(), 0)
            self.assertTrue((Path(tmp) / "Assets" / "Bowling" / "Runtime"
                             / "Bowling.Runtime.asmdef").is_file())


class TestDocConsistency(unittest.TestCase):
    """Drift-Schutz: jeder Ordner-/Assembly-Name der Konstanten steht im Regelwerk."""

    @unittest.skipUnless(CONVENTIONS.exists(),
                         "unity-conventions.md nicht auf dieser Maschine")
    def test_every_layout_and_assembly_name_documented(self):
        doc = CONVENTIONS.read_text(encoding="utf-8")
        for rel in LAYOUT:
            self.assertIn(rel, doc, f"Ordner fehlt im Regelwerk: {rel}")
        for content in ASMDEFS.values():
            name = content["name"].replace("{prefix}", "<Prefix>")
            self.assertIn(name, doc, f"Assembly fehlt im Regelwerk: {name}")


if __name__ == "__main__":
    unittest.main()

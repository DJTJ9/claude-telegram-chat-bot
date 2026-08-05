# unity_dummy — Prüf-Feature für unity_test_run.py

Minimales Unity-Feature (Runtime + EditMode- + PlayMode-Test), mit dem sich
`scripts/unity_test_run.py` gegen einen echten headless Editor-Lauf prüfen lässt.

Ins Scratch-Projekt spielen:

```bash
python3 "$WORK_DIR/scripts/unity_scaffold.py" --project /root/unity-scratch --prefix SkillTests
cp tests/fixtures/unity_dummy/Runtime/DummyMath.cs                  /root/unity-scratch/Assets/SkillTests/Runtime/
cp tests/fixtures/unity_dummy/Tests/EditMode/DummyEditModeTests.cs  /root/unity-scratch/Assets/SkillTests/Tests/EditMode/
cp tests/fixtures/unity_dummy/Tests/PlayMode/DummyPlayModeTests.cs  /root/unity-scratch/Assets/SkillTests/Tests/PlayMode/
python3 "$WORK_DIR/scripts/unity_test_run.py" --project /root/unity-scratch
```

`scaffold` liefert die vier asmdefs (Runtime/Editor/Tests.EditMode/Tests.PlayMode) —
deshalb liegt hier kein asmdef-JSON.

Ziel ist bewusst `Assets/SkillTests/`, **nicht** `Assets/Skill/`: letzteres gehört
`unity_compile_check.py` und wird bei jedem Lauf gewiped.

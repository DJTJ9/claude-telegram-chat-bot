using System.Collections;
using NUnit.Framework;
using UnityEngine.TestTools;
using SkillTests;

public class DummyPlayModeTests
{
    [UnityTest]
    public IEnumerator Double_Doubles_AfterFrame()
    {
        yield return null;
        Assert.AreEqual(6, DummyMath.Double(3));
    }
}

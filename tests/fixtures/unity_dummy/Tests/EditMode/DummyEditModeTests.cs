using NUnit.Framework;
using SkillTests;

public class DummyEditModeTests
{
    [Test]
    public void Double_Doubles()
    {
        Assert.AreEqual(4, DummyMath.Double(2));
    }
}

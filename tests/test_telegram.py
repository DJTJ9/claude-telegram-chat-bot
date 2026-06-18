from core.telegram import build_inline_keyboard

def test_abc_options():
    kb = build_inline_keyboard("Welche Option? A) Eins B) Zwei C) Drei")
    labels = [btn["text"] for row in kb for btn in row]
    assert "A" in labels
    assert "B" in labels
    assert "C" in labels
    assert "Freitext" in labels

def test_ja_nein():
    kb = build_inline_keyboard("Ist das richtig? ja oder nein")
    labels = [btn["text"] for row in kb for btn in row]
    assert "Ja" in labels
    assert "Nein" in labels

def test_unknown_question():
    kb = build_inline_keyboard("Was ist dein Name?")
    labels = [btn["text"] for row in kb for btn in row]
    assert "Freitext" in labels
    assert len([l for l in labels if l != "Freitext"]) == 0

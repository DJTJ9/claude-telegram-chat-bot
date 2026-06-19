import os, sys
os.environ.setdefault("TOKEN_TEACH", "test_token")
os.environ.setdefault("CHAT_ID", "12345")
os.environ.setdefault("GROQ_API_KEY", "test_key")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from pathlib import Path
from unittest.mock import patch
from bots.teach import (
    _lesson_title_from_filename,
    _get_topics,
    _build_lessons_keyboard,
    _send_lesson_list,
    _update_index_html,
    _inject_lesson_navigation,
)


# --- _lesson_title_from_filename ---

def test_title_lektion_prefix():
    assert _lesson_title_from_filename("lektion-01-python-vs-csharp.html") == "Python Vs Csharp"

def test_title_numeric_prefix():
    assert _lesson_title_from_filename("01-was-ist-eine-datenbank.html") == "Was Ist Eine Datenbank"

def test_title_lektion_two_digit():
    assert _lesson_title_from_filename("lektion-10-llm-apis-und-prompting.html") == "Llm Apis Und Prompting"


# --- _get_topics ---

def test_get_topics_returns_sorted_slugs(tmp_path):
    for slug in ["sql-basics", "python-grundlagen", "tdd"]:
        (tmp_path / slug / "lessons").mkdir(parents=True)
        (tmp_path / slug / "lessons" / "lektion-01-intro.html").write_text("")
    topics = _get_topics(teach_dir=tmp_path)
    assert [s for s, _ in topics] == ["python-grundlagen", "sql-basics", "tdd"]

def test_get_topics_skips_empty_lessons(tmp_path):
    (tmp_path / "empty-course" / "lessons").mkdir(parents=True)
    (tmp_path / "python-grundlagen" / "lessons").mkdir(parents=True)
    (tmp_path / "python-grundlagen" / "lessons" / "lektion-01-intro.html").write_text("")
    topics = _get_topics(teach_dir=tmp_path)
    assert len(topics) == 1
    assert topics[0][0] == "python-grundlagen"

def test_get_topics_slug_to_label(tmp_path):
    (tmp_path / "python-grundlagen" / "lessons").mkdir(parents=True)
    (tmp_path / "python-grundlagen" / "lessons" / "lektion-01-intro.html").write_text("")
    topics = _get_topics(teach_dir=tmp_path)
    assert topics[0][1] == "Python Grundlagen"


# --- _build_lessons_keyboard ---

def test_keyboard_two_per_row():
    topics = [("a", "A"), ("b", "B"), ("c", "C")]
    kb = _build_lessons_keyboard(topics)
    assert len(kb[0]) == 2
    assert len(kb[1]) == 1

def test_keyboard_callback_data_prefix():
    topics = [("python-grundlagen", "Python Grundlagen")]
    kb = _build_lessons_keyboard(topics)
    assert kb[0][0]["callback_data"] == "lessons__python-grundlagen"

def test_keyboard_button_text():
    topics = [("python-grundlagen", "Python Grundlagen")]
    kb = _build_lessons_keyboard(topics)
    assert kb[0][0]["text"] == "Python Grundlagen"


# --- _send_lesson_list ---

def test_send_lesson_list_format(tmp_path):
    lessons = tmp_path / "python-grundlagen" / "lessons"
    lessons.mkdir(parents=True)
    (lessons / "lektion-01-erste-schritte.html").write_text("")
    (lessons / "lektion-02-variablen.html").write_text("")

    sent_kwargs = []
    with patch("bots.teach.send_message", lambda tok, cid, text, **kw: sent_kwargs.append((text, kw))):
        _send_lesson_list("python-grundlagen", teach_dir=tmp_path)

    text, kw = sent_kwargs[0]
    assert "Python Grundlagen" in text
    assert "2 Lektionen" in text
    kb = kw["reply_markup"]["inline_keyboard"]
    assert len(kb) == 2
    btn1 = kb[0][0]
    assert btn1["url"] == "https://djtj9.github.io/teach-lessons/python-grundlagen/lessons/lektion-01-erste-schritte.html"
    assert "Erste Schritte" in btn1["text"]
    btn2 = kb[1][0]
    assert btn2["url"] == "https://djtj9.github.io/teach-lessons/python-grundlagen/lessons/lektion-02-variablen.html"

MINIMAL_INDEX = """\
<!DOCTYPE html>
<html><body>
<h2>Python Grundlagen</h2>
<ul>
</ul>
</body></html>"""

def test_update_index_adds_li_to_existing_section(tmp_path):
    index = tmp_path / "index.html"
    index.write_text(MINIMAL_INDEX, encoding="utf-8")
    (tmp_path / "python-grundlagen" / "lessons").mkdir(parents=True)
    (tmp_path / "python-grundlagen" / "lessons" / "lektion-01-erste-schritte.html").write_text(
        "<title>Lektion 1 – Erste Schritte</title>", encoding="utf-8"
    )
    _update_index_html("python-grundlagen/lessons/lektion-01-erste-schritte.html", teach_dir=tmp_path)
    content = index.read_text(encoding="utf-8")
    assert 'href="python-grundlagen/lessons/lektion-01-erste-schritte.html"' in content
    assert "Erste Schritte" in content

def test_update_index_creates_new_section_for_unknown_course(tmp_path):
    index = tmp_path / "index.html"
    index.write_text("<!DOCTYPE html><html><body></body></html>", encoding="utf-8")
    (tmp_path / "neuer-kurs" / "lessons").mkdir(parents=True)
    (tmp_path / "neuer-kurs" / "lessons" / "lektion-01-intro.html").write_text("", encoding="utf-8")
    _update_index_html("neuer-kurs/lessons/lektion-01-intro.html", teach_dir=tmp_path)
    content = index.read_text(encoding="utf-8")
    assert "<h2>Neuer Kurs</h2>" in content
    assert 'href="neuer-kurs/lessons/lektion-01-intro.html"' in content

def test_update_index_no_duplicate(tmp_path):
    existing = """\
<!DOCTYPE html><html><body>
<h2>Python Grundlagen</h2>
<ul>
  <li><a href="python-grundlagen/lessons/lektion-01-erste-schritte.html">Erste Schritte</a></li>
</ul>
</body></html>"""
    index = tmp_path / "index.html"
    index.write_text(existing, encoding="utf-8")
    (tmp_path / "python-grundlagen" / "lessons").mkdir(parents=True)
    (tmp_path / "python-grundlagen" / "lessons" / "lektion-01-erste-schritte.html").write_text("", encoding="utf-8")
    _update_index_html("python-grundlagen/lessons/lektion-01-erste-schritte.html", teach_dir=tmp_path)
    content = index.read_text(encoding="utf-8")
    assert content.count('href="python-grundlagen/lessons/lektion-01-erste-schritte.html"') == 1


def test_send_lesson_list_empty(tmp_path):
    (tmp_path / "python-grundlagen" / "lessons").mkdir(parents=True)
    sent = []
    with patch("bots.teach.send_message", lambda tok, cid, text, **kw: sent.append(text)):
        _send_lesson_list("python-grundlagen", teach_dir=tmp_path)
    assert "Keine Lektionen" in sent[0]


# --- _inject_lesson_navigation ---

FOOTER_HTML = """\
<!DOCTYPE html><html><body>
<footer>Weiter: <strong>Lektion 02</strong></footer>
</body></html>"""

def test_inject_nav_first_lesson_has_only_next(tmp_path):
    lessons = tmp_path / "my-kurs" / "lessons"
    lessons.mkdir(parents=True)
    (lessons / "lektion-01-intro.html").write_text(FOOTER_HTML, encoding="utf-8")
    (lessons / "lektion-02-vertiefung.html").write_text(FOOTER_HTML, encoding="utf-8")
    _inject_lesson_navigation("my-kurs", teach_dir=tmp_path)
    content = (lessons / "lektion-01-intro.html").read_text(encoding="utf-8")
    assert 'href="lektion-02-vertiefung.html"' in content
    assert "←" not in content

def test_inject_nav_last_lesson_shows_done(tmp_path):
    lessons = tmp_path / "my-kurs" / "lessons"
    lessons.mkdir(parents=True)
    (lessons / "lektion-01-intro.html").write_text(FOOTER_HTML, encoding="utf-8")
    (lessons / "lektion-02-vertiefung.html").write_text(FOOTER_HTML, encoding="utf-8")
    _inject_lesson_navigation("my-kurs", teach_dir=tmp_path)
    content = (lessons / "lektion-02-vertiefung.html").read_text(encoding="utf-8")
    assert "Kurs abgeschlossen" in content
    assert 'href="lektion-01-intro.html"' in content

def test_inject_nav_middle_lesson_has_both(tmp_path):
    lessons = tmp_path / "my-kurs" / "lessons"
    lessons.mkdir(parents=True)
    for name in ["lektion-01-a.html", "lektion-02-b.html", "lektion-03-c.html"]:
        (lessons / name).write_text(FOOTER_HTML, encoding="utf-8")
    _inject_lesson_navigation("my-kurs", teach_dir=tmp_path)
    content = (lessons / "lektion-02-b.html").read_text(encoding="utf-8")
    assert 'href="lektion-01-a.html"' in content
    assert 'href="lektion-03-c.html"' in content

def test_inject_nav_skips_file_without_footer(tmp_path):
    lessons = tmp_path / "my-kurs" / "lessons"
    lessons.mkdir(parents=True)
    (lessons / "lektion-01-a.html").write_text("<html><body>no footer</body></html>", encoding="utf-8")
    (lessons / "lektion-02-b.html").write_text(FOOTER_HTML, encoding="utf-8")
    _inject_lesson_navigation("my-kurs", teach_dir=tmp_path)
    content = (lessons / "lektion-01-a.html").read_text(encoding="utf-8")
    assert "<footer>" not in content

def test_inject_nav_idempotent(tmp_path):
    lessons = tmp_path / "my-kurs" / "lessons"
    lessons.mkdir(parents=True)
    (lessons / "lektion-01-intro.html").write_text(FOOTER_HTML, encoding="utf-8")
    (lessons / "lektion-02-end.html").write_text(FOOTER_HTML, encoding="utf-8")
    _inject_lesson_navigation("my-kurs", teach_dir=tmp_path)
    first_run = (lessons / "lektion-01-intro.html").read_text(encoding="utf-8")
    _inject_lesson_navigation("my-kurs", teach_dir=tmp_path)
    second_run = (lessons / "lektion-01-intro.html").read_text(encoding="utf-8")
    assert first_run == second_run

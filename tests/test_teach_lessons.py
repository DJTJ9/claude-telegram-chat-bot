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

    sent = []
    with patch("bots.teach.send_message", lambda tok, cid, text, **kw: sent.append(text)):
        _send_lesson_list("python-grundlagen", teach_dir=tmp_path)

    msg = sent[0]
    assert "Python Grundlagen" in msg
    assert "2 Lektionen" in msg
    assert "Erste Schritte" in msg
    assert "https://djtj9.github.io/teach-lessons/python-grundlagen/lessons/lektion-01-erste-schritte.html" in msg
    assert "Variablen" in msg

def test_send_lesson_list_empty(tmp_path):
    (tmp_path / "python-grundlagen" / "lessons").mkdir(parents=True)
    sent = []
    with patch("bots.teach.send_message", lambda tok, cid, text, **kw: sent.append(text)):
        _send_lesson_list("python-grundlagen", teach_dir=tmp_path)
    assert "Keine Lektionen" in sent[0]

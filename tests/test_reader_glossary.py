from __future__ import annotations

import json

from app.reader.page import reader_page
from app.reader.service import clean_bookmarks, job_glossary_terms


def _snapshot(tmp_path, terms):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "glossary.json").write_text(json.dumps({"terms": terms}, ensure_ascii=False), encoding="utf-8")
    return {"job_dir": str(job_dir)}


def _term(source, target, approved=True):
    return {"source_term": source, "target_term": target, "approved": approved}


def test_glossary_terms_come_from_the_job_snapshot(tmp_path):
    paths = _snapshot(tmp_path, [_term("clean architecture", "معماری تمیز")])
    assert job_glossary_terms(paths) == [
        {"source_term": "clean architecture", "target_term": "معماری تمیز"}
    ]


def test_glossary_terms_exclude_unapproved_and_empty(tmp_path):
    paths = _snapshot(
        tmp_path,
        [
            _term("clean architecture", "معماری تمیز"),
            _term("draft term", "پیشنویس", approved=False),
            _term("no equivalent", "  "),
            _term("  ", "خالی"),
            "not-a-dict",
        ],
    )
    assert job_glossary_terms(paths) == [
        {"source_term": "clean architecture", "target_term": "معماری تمیز"}
    ]


def test_glossary_terms_prefer_longer_sources_and_cap(tmp_path):
    terms = [_term(f"term {i}", f"معادل {i}") for i in range(60)]
    terms.append(_term("clean architecture patterns", "الگوهای معماری تمیز"))
    paths = _snapshot(tmp_path, terms)
    items = job_glossary_terms(paths)
    assert len(items) == 40
    assert items[0] == {
        "source_term": "clean architecture patterns",
        "target_term": "الگوهای معماری تمیز",
    }


def test_glossary_terms_without_snapshot_is_empty(tmp_path):
    assert job_glossary_terms(None) == []
    assert job_glossary_terms({}) == []
    assert job_glossary_terms({"job_dir": str(tmp_path / "missing")}) == []


def test_clean_bookmarks_keeps_shape_and_caps_at_fifty():
    value = [{"chapter": i, "block": 2, "note": f"n{i}", "created": "x"} for i in range(55)]
    cleaned = clean_bookmarks(value)
    assert len(cleaned) == 50
    # The oldest beyond the cap are dropped, never the request rejected.
    assert cleaned[0]["chapter"] == 5
    assert cleaned[-1]["chapter"] == 54


def test_clean_bookmarks_drops_bad_entries_and_trims_notes():
    cleaned = clean_bookmarks([
        {"chapter": 1, "block": 0, "note": "ok"},
        {"chapter": "two"},
        {"chapter": -1},
        "garbage",
        {"chapter": 3, "note": "y" * 600},
    ])
    assert [(item["chapter"], len(item["note"])) for item in cleaned] == [(1, 2), (3, 500)]


def test_clean_bookmarks_rejects_non_lists():
    assert clean_bookmarks(None) == []
    assert clean_bookmarks({"chapter": 1}) == []


def test_reading_defaults_carry_the_new_keys():
    from app.web import READING_DEFAULTS

    assert READING_DEFAULTS["reading_bookmarks"] == []
    assert READING_DEFAULTS["reading_glossary"] is True


def test_reader_page_has_contrast_theme_glossary_speech_and_marks():
    page = reader_page("job-1")
    assert "theme-contrast" in page
    assert 'data-theme="contrast"' in page
    assert "mark.gloss" in page
    assert "data-gloss" in page
    assert "speechSynthesis" in page
    assert "reading_bookmarks" in page
    assert "marks-list" in page
    assert "speak-btn" in page
    assert "mark-btn" in page


def test_reader_blocks_carry_stable_indexes_for_marks_and_speech():
    page = reader_page("job-1")
    assert "data-bi" in page

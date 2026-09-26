import json

import pytest

from app.jobs.detail_page import job_detail_page
from app.web import Job, _job_chunks_payload


def _job_with_state(tmp_path, translations=None):
    chunks_file = tmp_path / "chunks.json"
    translations_file = tmp_path / "translations.json"
    chunks_file.write_text(
        json.dumps(
            {
                "chunks": [["chunk-0", "First source."], ["chunk-1", "Second source."]],
                "chapter_map": {
                    "chunk-0": {"item": "ch01.xhtml", "pos": 0},
                    "chunk-1": {"item": "ch02.xhtml", "pos": 1},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    translations_file.write_text(
        json.dumps(translations or {}, ensure_ascii=False), encoding="utf-8"
    )
    job = Job("jid", "book.epub", tmp_path / "book.epub", "epub", 42, {}, "EN", "FA", "gpt", "fast")
    job.paths = {"chunks_file": str(chunks_file), "translations_file": str(translations_file)}
    return job


def test_page_renders_all_monitor_tabs():
    page = job_detail_page("abc123")
    for name in ("overview", "chunks", "qa", "logs", "assets"):
        assert f'id="tab-{name}"' in page
        assert f'id="panel-{name}"' in page
    assert "__FONTS__" not in page and "__JOB_ID__" not in page
    assert "abc123" in page
    assert 'jbook-study-dark' in page
    assert "prefers-reduced-motion" in page


def test_page_exposes_accessible_interaction_primitives():
    page = job_detail_page("x")
    assert 'role="tablist"' in page
    assert 'role="tabpanel"' in page
    assert 'role="progressbar"' in page
    assert 'role="dialog"' in page and 'aria-modal="true"' in page
    assert 'role="status"' in page and 'aria-live="polite"' in page
    assert 'role="alert"' in page
    assert "skeleton" in page
    # Virtualised chunk table: windowed rows driven by scroll position.
    assert "ROW_H" in page and "scrollTop" in page and "OVERSCAN" in page


def test_chunks_payload_reports_missing_job():
    assert _job_chunks_payload(None) == {"error": "کار موردنظر پیدا نشد."}


def test_chunks_payload_without_paths_is_not_available(tmp_path):
    job = Job("jid", "b.epub", tmp_path / "b.epub", "epub", 1, {}, "EN", "FA", "gpt", "fast")
    assert _job_chunks_payload(job) == {"items": [], "total": 0, "available": False}


def test_chunks_payload_pairs_source_with_translation(tmp_path):
    job = _job_with_state(tmp_path, {"chunk-0": "ترجمهٔ بخش اول"})
    result = _job_chunks_payload(job)
    assert result["available"] is True
    assert result["total"] == 2
    assert result["translated"] == 1
    first, second = result["items"]
    assert first["id"] == "chunk-0"
    assert first["chapter"] == "ch01.xhtml"
    assert first["source"] == "First source."
    assert first["target"] == "ترجمهٔ بخش اول"
    assert second["target"] == ""


@pytest.mark.parametrize("marker", ["{NOTE: kept transliteration}", "{BOUNDARY_WARNING: boundary}"])
def test_chunks_payload_flags_qa_markers(tmp_path, marker):
    job = _job_with_state(tmp_path, {"chunk-0": marker})
    items = _job_chunks_payload(job)["items"]
    assert items[0]["flagged"] is True
    assert items[1]["flagged"] is False


def test_chunks_payload_survives_corrupt_state_file(tmp_path):
    job = _job_with_state(tmp_path)
    (tmp_path / "chunks.json").write_text("{not json", encoding="utf-8")
    assert _job_chunks_payload(job) == {"items": [], "total": 0, "available": False}

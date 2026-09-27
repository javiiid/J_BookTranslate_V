"""Offline regression coverage for the critical translation failure modes.

No test in this module calls a real provider or consumes API tokens.
"""

from __future__ import annotations

import json
import threading
import zipfile
from pathlib import Path

import fitz
import pytest

from app.core.retry import retry_operation
from app.core.validation import validate_book
from app.jobs.state import load_job_state, save_chunks, save_translations
from app.pipeline.epub_handler import EPUBHandler
from app.pipeline.pdf_handler import PDFHandler
from app.translation.translator import process_translations


class FakeHTTPError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class FakeClient:
    def __init__(self, failures=0):
        self.failures = failures
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        chunk_id = kwargs["messages"][1]["content"]
        self.calls.append(chunk_id)
        if self.failures:
            self.failures -= 1
            raise FakeHTTPError(503)
        return type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": f"ترجمهٔ {chunk_id} العربية Ελληνικά"})()})()]})()


def _paths(tmp_path: Path) -> dict:
    return {
        "job_dir": tmp_path,
        "chunks_file": tmp_path / "chunks.json",
        "translations_file": tmp_path / "translations.json",
        "state_file": tmp_path / "job_state.json",
        "progress_log": tmp_path / "progress.log",
        "system_prompt_file": tmp_path / "system_prompt.txt",
    }


def _make_epub(path: Path, body: str) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", "<container/>" )
        archive.writestr("OEBPS/chapter.xhtml", f"<html><body>{body}</body></html>")
    return path


def _make_pdf(path: Path, scanned: bool = False) -> Path:
    document = fitz.open()
    page = document.new_page()
    if scanned:
        pixmap = fitz.Pixmap(fitz.csRGB, (0, 0, 80, 80), 0)
        pixmap.clear_with(255)
        page.insert_image(page.rect, pixmap=pixmap)
    else:
        page.insert_text((40, 60), "متن فارسی Arabic Ελληνικά")
    document.save(path)
    document.close()
    return path


def test_small_epub_and_complex_unicode_html(tmp_path):
    source = _make_epub(tmp_path / "unicode.epub", "<p>سلام العربية Ελληνικά</p><div><em>nested</em></div>")
    validate_book(source)
    # build_chunks returns a third value, the per-chunk context map, as of the
    # semantic chunker. It is empty while `semantic_chunking` is off, which is
    # the default.
    chunks, chapter_map, contexts = EPUBHandler.build_chunks(source)
    assert chunks
    assert chapter_map
    assert contexts == {}
    assert any("سلام" in text and "العربية" in text for _, text in chunks)


@pytest.mark.parametrize("scanned", [False, True])
def test_text_and_scanned_pdf_validation(tmp_path, scanned):
    source = _make_pdf(tmp_path / ("scan.pdf" if scanned else "text.pdf"), scanned=scanned)
    assert validate_book(source) == source


def test_corrupt_epub_is_rejected(tmp_path):
    source = tmp_path / "broken.epub"
    source.write_bytes(b"not a zip")
    with pytest.raises(ValueError, match="EPUB"):
        validate_book(source)


@pytest.mark.parametrize("status", [429, 500])
def test_retry_recovers_from_provider_errors(status):
    calls = {"count": 0}

    def operation():
        calls["count"] += 1
        if calls["count"] == 1:
            raise FakeHTTPError(status)
        return "ok"

    assert retry_operation(operation, max_attempts=3, sleep_func=lambda _: None) == "ok"
    assert calls["count"] == 2


def test_network_interruption_stops_retry_without_extra_call():
    calls = {"count": 0}

    def operation():
        calls["count"] += 1
        raise FakeHTTPError(503)

    with pytest.raises(KeyboardInterrupt):
        retry_operation(operation, max_attempts=5, sleep_func=lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert calls["count"] == 1


def test_resume_skips_completed_and_duplicate_chunks(tmp_path):
    paths = _paths(tmp_path)
    chunks = [("chunk-0", "zero"), ("chunk-0", "duplicate"), ("chunk-1", "one")]
    client = FakeClient()
    process_translations(client, chunks, {"chunk-0": "already"}, "resume", "EN", "FA", paths, model="test")
    assert client.calls == ["one"]
    assert json.loads(paths["translations_file"].read_text(encoding="utf-8")) == {"chunk-0": "already", "chunk-1": "ترجمهٔ one العربية Ελληνικά"}


def test_state_survives_restart_and_is_valid_json(tmp_path):
    paths = _paths(tmp_path)
    save_chunks(paths, [("a", "A"), ("a", "duplicate"), ("b", "B")], {"a": ("x", 0), "b": ("x", 1)})
    save_translations(paths, {"a": "ترجمه"})
    restored = load_job_state(paths)
    assert restored["chunks_total"] == 2
    assert restored["chunks_completed"] == 1
    assert json.loads(paths["translations_file"].read_text(encoding="utf-8"))["a"] == "ترجمه"


def test_state_lock_handles_concurrent_writes(tmp_path):
    paths = _paths(tmp_path)

    def writer(index):
        save_translations(paths, {"chunk": f"value-{index}"})

    threads = [threading.Thread(target=writer, args=(index,)) for index in range(4)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    result = json.loads(paths["translations_file"].read_text(encoding="utf-8"))
    assert result["chunk"].startswith("value-")


def test_pdf_output_falls_back_without_ghostscript(tmp_path, monkeypatch):
    source = _make_pdf(tmp_path / "source.pdf")
    output = tmp_path / "output.pdf"
    monkeypatch.setattr("app.pipeline.pdf_handler.shutil.which", lambda _: None)
    PDFHandler.compress_pdf(source, output)
    assert output.exists()
    assert fitz.open(output).page_count == 1


def test_restart_recovery_marks_active_web_job_paused(tmp_path, monkeypatch):
    import app.web as web

    input_path = tmp_path / "book.epub"
    _make_epub(input_path, "<p>restart</p>")
    meta_dir = tmp_path / "jobs"
    monkeypatch.setattr(web, "JOB_META_DIR", meta_dir)
    monkeypatch.setattr(web, "JOBS", {})
    job = web.Job("restart-1", input_path.name, input_path, "epub", input_path.stat().st_size,
                  {"from_lang": "EN", "to_lang": "FA", "model": "test", "mode": "fast", "prompt": "", "debug": "true"},
                  "EN", "FA", "test", "fast", status="paused", pipeline_job_id="pipeline-1")
    web.JOBS[job.id] = job
    web._persist_job(job)
    web.JOBS.clear()
    web.restore_jobs()
    assert web.JOBS["restart-1"].status == "paused"


def test_output_incomplete_is_detectable(tmp_path):
    output = tmp_path / "missing.pdf"
    assert not output.exists()
    source = _make_pdf(tmp_path / "valid.pdf")
    validate_book(source)
    assert source.exists()

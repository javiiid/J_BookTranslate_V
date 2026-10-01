"""Tests for `web._import_rescue`: the route's body, without the HTTP.

The first version of this function returned `job.from_lang`, which is not a field
on `Job` -- the dataclass calls them `source_language` and `target_language`. Every
unit test in `test_rescue_import.py` passed, because none of them called it. The
AttributeError only appeared when a real archive was posted to a running server,
where it killed the connection.

So the function is tested here, directly. The globals it touches -- `JOBS`,
`UPLOAD_DIR` and the temp directory -- are redirected into `tmp_path`.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

import pytest

sys.stdout.reconfigure(encoding="utf-8")

import app.web as web


def _book(paragraphs: int = 60) -> bytes:
    """A real EPUB.

    The estimate endpoint has to chunk the restored book, and it only does that
    for a file it can read as one. A few bytes of placeholder would make
    `count_chunks` fall back to the size estimate, so the test would be checking
    the fallback rather than the thing it claims to.
    """
    body = "".join(
        f"<p>{'word ' * 40}Paragraph number {n} of the chapter.</p>"
        for n in range(paragraphs)
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("OEBPS/ch1.xhtml", f"<html><body>{body}</body></html>")
        archive.writestr("OEBPS/ch2.xhtml", f"<html><body>{body}</body></html>")
    return buffer.getvalue()


def _archive(
    *,
    job_id: str = "abc123",
    pipeline_job_id: str = "abc123_overthesevensea_EN_FA_gpt-5.6-luna_20260928_120000",
    filename: str = "overthesevensea.epub",
    model: str = "gpt-5.6-luna",
    translations: dict[str, str] | None = None,
    done: int | None = None,
    chunk_budget: int | None = None,
) -> tuple[bytes, int]:
    """A rescue archive whose chunk list is what a real chunker produces.

    Derived rather than invented. The import refuses an archive whose chunking
    does not match the current settings, so a fixture with a made-up chunk count
    would be refused by the very check these tests are about -- and the first
    version of this helper had 60 invented chunks against a book that chunks into
    four, which failed all thirteen tests for that reason.

    `chunk_budget` overrides the budget the archive was "produced at", so a test
    can build one that deliberately disagrees with the config.

    Returns the archive and the real chunk count.
    """
    from app.core.config import get_chunking_config
    from app.jobs.rescue import chunk_signature

    cfg = get_chunking_config()
    budget = chunk_budget or int(cfg["chunk_max_tokens"])
    window = int(cfg["chunk_context_window"])

    book = _book()
    scratch = Path(gettempdir()) / f"rescue-fixture-{uuid4().hex}.epub"
    scratch.write_bytes(book)
    try:
        pairs = chunk_signature(scratch, budget, window)
    finally:
        scratch.unlink()

    total = len(pairs)
    done = total - 1 if done is None else max(0, min(done, total))

    meta = {
        "id": job_id,
        "filename": filename,
        "filetype": Path(filename).suffix.lstrip("."),
        "options": {
            "from_lang": "EN",
            "to_lang": "FA",
            "model": model,
            "mode": "fast",
            "style_preset": "literary",
        },
        "model": model,
        "mode": "fast",
        "pipeline_job_id": pipeline_job_id,
    }
    if translations is None:
        translations = {f"chunk-{n}": "متن ترجمه‌شده" for n in range(done)}

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"project/{job_id}.json", json.dumps(meta, ensure_ascii=False))
        archive.writestr(f"project/{job_id}_{filename}", book)
        archive.writestr("project/chunks.json", json.dumps({
            "chunks": [[f"chunk-{n}", chunk_html] for n, chunk_html in pairs]
        }))
        archive.writestr("project/translations.json", json.dumps(translations, ensure_ascii=False))
        archive.writestr("project/glossary.json", json.dumps({"terms": []}))
    return buffer.getvalue(), total


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Redirect the globals the import writes through.

    `app.core.paths.ensure_dir` and `app.jobs.state.ensure_dir` are patched too.
    The resume lookup is what proves the restore is usable, and it reaches the
    temp directory through `ensure_temp_structure` -- which lives in
    `app.core.paths` and calls that module's own `ensure_dir`. Patching only
    `web` left it pointed at the real `temp/`, so the estimate saw no job and
    quoted a fresh full-price run, which reads as a broken product rather than a
    broken fixture.
    """
    import app.core.paths as core_paths
    import app.jobs.state as state

    uploads = tmp_path / "uploads"
    temp = tmp_path / "temp"
    sandboxed = lambda name: temp if name == "temp" else tmp_path  # noqa: E731
    monkeypatch.setattr(web, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(web, "ensure_dir", sandboxed)
    monkeypatch.setattr(state, "ensure_dir", sandboxed)
    monkeypatch.setattr(core_paths, "ensure_dir", sandboxed)
    monkeypatch.setattr(web, "JOBS", {})
    # The job is not really persisted, and the library index is optional.
    monkeypatch.setattr(web, "_persist_job", lambda job: None)
    monkeypatch.setattr(web, "_job_event", lambda *a, **k: None)
    monkeypatch.setattr(web, "_ensure_library_source", lambda job: None)
    return uploads, temp


class TestImportRescue:
    def test_reports_what_was_restored(self, sandbox):
        payload, total = _archive(done=2)
        result = web._import_rescue(payload, force=False)
        assert result["id"] == "abc123"
        assert result["chunk_count_total"] == total
        assert result["chunks_already_done"] == 2
        assert result["chunks_remaining"] == total - 2
        assert result["from_lang"] == "EN"
        assert result["to_lang"] == "FA"
        assert result["model"] == "gpt-5.6-luna"

    def test_the_job_is_paused_so_the_resume_route_accepts_it(self, sandbox):
        # `POST /api/jobs/{id}/resume` requires status in {paused, failed}. A
        # rescue that started translating on import would skip the estimate
        # dialog this exists to feed.
        result = web._import_rescue(_archive()[0], force=False)
        assert result["status"] == "paused"
        job = web.JOBS[result["id"]]
        assert job.status == "paused"
        assert job.filetype == "epub"

    def test_the_pipeline_job_id_is_carried_over(self, sandbox):
        # The resume reads this to find the directory it continues from. Losing it
        # means the restore succeeded and the resume restarts from nothing.
        result = web._import_rescue(_archive()[0], force=False)
        job = web.JOBS[result["id"]]
        assert job.pipeline_job_id == (
            "abc123_overthesevensea_EN_FA_gpt-5.6-luna_20260928_120000"
        )

    def test_the_book_and_the_job_directory_are_written(self, sandbox):
        uploads, temp = sandbox
        result = web._import_rescue(_archive()[0], force=False)
        book = Path(result["file_path"])
        assert book.parent == uploads
        assert book.name == "abc123_overthesevensea.epub"
        job_dir = temp / result["resumed_from"]
        assert job_dir.is_dir()
        assert (job_dir / "chunks.json").exists()
        assert (job_dir / "translations.json").exists()
        assert (job_dir / "job_state.json").exists()

    def test_the_state_the_resume_reads_is_correct(self, sandbox):
        _, temp = sandbox
        payload, total = _archive(done=2)
        result = web._import_rescue(payload, force=False)
        state = json.loads(
            (temp / result["resumed_from"] / "job_state.json").read_text(encoding="utf-8")
        )
        assert state == {"chunks_total": total, "chunks_completed": 2}

    def test_the_estimate_endpoint_finds_the_restored_job(self, sandbox):
        """The two names have to agree.

        `find_resumable_jobs` -- and so the estimate dialog -- looks for a temp
        directory starting with "{book stem}_{from}_{to}_{model}_". If the upload
        name and the job directory drift apart, the import reports 48 of 60 done
        and the estimate quotes a full-price fresh run.
        """
        from app.jobs.estimate import estimate

        # The route passes the configured budget, and so must this: `estimate`'s
        # own default is 1200, and calling it bare made the book chunk into eight
        # where the archive had four. The mismatch looked like a broken restore
        # rather than a test that had left off an argument the route does send.
        from app.core.config import get_chunking_config
        cfg = get_chunking_config()

        payload, total = _archive(done=2)
        result = web._import_rescue(payload, force=False)
        found = estimate(
            result["file_path"],
            result["model"],
            12,
            "fast",
            glossary_auto=False,
            source_lang=result["from_lang"],
            target_lang=result["to_lang"],
            max_tokens=int(cfg["chunk_max_tokens"]),
            context_window=int(cfg["chunk_context_window"]),
        )
        assert found.resume.found is True
        assert found.resume.remaining == total - 2
        assert found.chunk_count == total - 2
        assert found.chunk_count_total == total
        # And the bill is for twelve chunks, not sixty. The comparison is against
        # the same book with a language pair that matches no saved job, so the
        # resume lookup misses and the full book is priced.
        fresh = estimate(
            result["file_path"], result["model"], 12, "fast",
            glossary_auto=False, source_lang="ZZ", target_lang="YY",
            max_tokens=int(cfg["chunk_max_tokens"]),
            context_window=int(cfg["chunk_context_window"]),
        )
        assert fresh.resume.found is False
        assert found.cost.maximum < fresh.cost.maximum


class TestConflicts:
    def test_a_second_import_asks_rather_than_replacing(self, sandbox):
        payload, _total = _archive(done=1)
        web._import_rescue(payload, force=False)
        with pytest.raises(web._RescueConflict) as caught:
            web._import_rescue(payload, force=False)
        conflict = caught.value
        assert conflict.existing.id == "abc123"
        assert conflict.imported.chunks_completed == 1

    def test_the_conflict_reports_what_differs(self, sandbox):
        web._import_rescue(_archive(model="gpt-5.6-luna")[0], force=False)
        with pytest.raises(web._RescueConflict) as caught:
            web._import_rescue(_archive(model="gpt-5.6-terra")[0], force=False)
        model = caught.value.differences["model"]
        assert model == ("gpt-5.6-terra", "gpt-5.6-luna")

    def test_force_replaces(self, sandbox):
        first = web._import_rescue(_archive(translations={"chunk-0": "قدیمی"})[0], force=False)
        _, temp = sandbox
        second = web._import_rescue(
            _archive(translations={f"chunk-{n}": "جدید" for n in range(999)})[0],
            force=True,
        )
        assert second["id"] == first["id"]
        stored = json.loads(
            (temp / second["resumed_from"] / "translations.json").read_text(encoding="utf-8")
        )
        assert "قدیمی" not in stored.values()
        assert set(stored.values()) == {"جدید"}

    def test_an_identical_reimport_still_asks(self, sandbox):
        # Nothing differs, so there is no reason to overwrite -- and the reader
        # is the one who knows whether the on-server copy is the newer one.
        web._import_rescue(_archive()[0], force=False)
        with pytest.raises(web._RescueConflict):
            web._import_rescue(_archive()[0], force=False)


class TestChunkingCheck:
    """The import must refuse a rescue whose chunking no longer matches.

    Chunk ids are positional, so a rescue produced at a different
    `chunk_max_tokens` would replay translations onto different spans of text.
    That does not raise -- it produces a book with sentences in the wrong places,
    which is what makes it worth a hard refusal rather than a warning.
    """

    def test_a_rescue_built_at_the_configured_budget_is_accepted(self, sandbox):
        result = web._import_rescue(_archive()[0], force=False)
        assert result["chunks_remaining"] >= 1

    def test_a_rescue_built_at_a_different_budget_is_refused(self, sandbox, monkeypatch):
        # The archive is genuine -- it was chunked at 400 -- and the config says
        # 3000. Importing it would put the saved translations on the wrong spans.
        payload, _total = _archive(chunk_budget=400)
        monkeypatch.setattr(
            web, "get_chunking_config",
            lambda: {"chunk_max_tokens": 3000, "chunk_context_window": 2},
        )
        with pytest.raises(ValueError, match="تقسیم‌بندی"):
            web._import_rescue(payload, force=False)

    def test_the_refusal_says_what_to_do(self, sandbox):
        from app.jobs.rescue import check_chunking, read_rescue

        payload, _total = _archive(chunk_budget=400)
        imported = read_rescue(payload)
        book = sandbox[0] / "abc123_overthesevensea.epub"
        book.parent.mkdir(parents=True, exist_ok=True)
        book.write_bytes(imported.book_bytes)

        check = check_chunking(imported, book, max_tokens=3000, context_window=2)
        assert check.matches is False
        message = check.message()
        assert "chunk_max_tokens" in message
        assert str(check.saved) in message
        assert str(check.current) in message

    def test_a_rejected_import_leaves_no_job(self, sandbox, monkeypatch):
        _, temp = sandbox
        payload, _total = _archive(chunk_budget=400)
        monkeypatch.setattr(
            web, "get_chunking_config",
            lambda: {"chunk_max_tokens": 3000, "chunk_context_window": 2},
        )
        with pytest.raises(ValueError):
            web._import_rescue(payload, force=False)

        # The refusal happens before the job state is written, so a retry after
        # fixing the config is not fighting leftovers from the failed attempt.
        assert web.JOBS == {}
        assert not temp.exists() or list(temp.iterdir()) == []

    def test_the_refusal_names_the_setting_that_changed(self, sandbox):
        """A refusal that only says "change the budget" sends the reader in circles.

        A real archive from 2026-09-24 carried 166 chunks and no budget of today's
        chunker produces 166 -- it ran before the semantic chunker existed. Told
        only to adjust `chunk_max_tokens`, the reader tries every value and fails
        every time. So the archive records how it was chunked and the message says
        which setting differs.
        """
        from app.jobs.rescue import check_chunking, read_rescue

        payload, _total = _archive(chunk_budget=400)
        imported = read_rescue(payload)
        book = sandbox[0] / "abc123_overthesevensea.epub"
        book.parent.mkdir(parents=True, exist_ok=True)
        book.write_bytes(imported.book_bytes)

        # An archive that recorded its settings.
        imported.chunking_settings = {
            "semantic_chunking": False,
            "chunk_max_tokens": 400,
            "chunk_context_window": 2,
        }
        check = check_chunking(
            imported, book, max_tokens=3000, context_window=2, semantic_chunking=True
        )
        assert check.matches is False
        message = check.message()
        assert "semantic_chunking" in message
        assert "chunk_max_tokens" in message

    def test_an_archive_with_no_recorded_settings_says_so(self, sandbox):
        from app.jobs.rescue import check_chunking, read_rescue

        payload, _total = _archive(chunk_budget=400)
        imported = read_rescue(payload)
        assert imported.chunking_settings is None
        book = sandbox[0] / "abc123_overthesevensea.epub"
        book.parent.mkdir(parents=True, exist_ok=True)
        book.write_bytes(imported.book_bytes)

        check = check_chunking(imported, book, max_tokens=3000, context_window=2)
        assert check.matches is False
        # It has to admit it is guessing, rather than asserting a cause it cannot know.
        assert "حدس" in check.message()

    def test_a_matching_rescue_reports_no_message(self, sandbox):
        from app.jobs.rescue import check_chunking, read_rescue

        payload, _total = _archive()
        imported = read_rescue(payload)
        book = sandbox[0] / "abc123_overthesevensea.epub"
        book.parent.mkdir(parents=True, exist_ok=True)
        book.write_bytes(imported.book_bytes)

        from app.core.config import get_chunking_config
        cfg = get_chunking_config()
        check = check_chunking(
            imported, book,
            max_tokens=int(cfg["chunk_max_tokens"]),
            context_window=int(cfg["chunk_context_window"]),
        )
        assert check.matches is True
        assert check.message() == ""


class TestRejections:
    def test_a_model_this_build_does_not_support(self, sandbox):
        with pytest.raises(ValueError, match="پشتیبانی"):
            web._import_rescue(_archive(model="gpt-4-imaginary")[0], force=False)

    def test_a_plain_zip_that_is_not_a_rescue(self, sandbox):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("readme.txt", "hello")
        with pytest.raises(ValueError, match="نجاتی"):
            web._import_rescue(buffer.getvalue(), force=False)

    def test_nothing_is_written_when_the_import_is_refused(self, sandbox):
        uploads, temp = sandbox
        with pytest.raises(ValueError):
            web._import_rescue(b"not a zip", force=False)
        assert not uploads.exists() or list(uploads.iterdir()) == []
        assert not temp.exists() or list(temp.iterdir()) == []

"""Tests for importing a rescue archive.

The archive is untrusted input, so most of these are about what it must not be
able to do: write outside its destination, claim progress the text does not
support, or be mistaken for a rescue when it is not one.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.stdout.reconfigure(encoding="utf-8")

from app.jobs.rescue import (
    JOB_FILES,
    MAX_EXPANDED_BYTES,
    RescueError,
    read_rescue,
    restore,
)

CHUNKS = ["chunk-0", "chunk-1", "chunk-2", "chunk-3"]
BOOK = b"PK\x03\x04 not really an epub, but bytes are bytes"


def make_rescue(
    *,
    job_id: str = "abc123",
    pipeline_job_id: str = "abc123_overthesevensea_EN_FA_gpt-5.6-luna_20260928_120000",
    filename: str = "overthesevensea.epub",
    translations: dict[str, str] | None = None,
    chunks: list[str] | None = None,
    extra: dict[str, bytes] | None = None,
    omit: set[str] | None = None,
    book: bytes = BOOK,
) -> bytes:
    """A rescue archive shaped exactly like `_rescue_job` writes one."""
    options = {
        "from_lang": "EN",
        "to_lang": "FA",
        "model": "gpt-5.6-luna",
        "mode": "fast",
        "style_preset": "literary",
    }
    meta = {
        "id": job_id,
        "filename": filename,
        "filetype": Path(filename).suffix.lstrip("."),
        "file_size": len(book),
        "options": options,
        "source_language": "EN",
        "target_language": "FA",
        "model": "gpt-5.6-luna",
        "mode": "fast",
        "pipeline_job_id": pipeline_job_id,
        "style": "literary",
    }

    translations = {"chunk-0": "متن", "chunk-1": "متن"} if translations is None else translations
    chunks = CHUNKS if chunks is None else chunks
    omit = omit or set()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        if "meta" not in omit:
            archive.writestr(f"project/{job_id}.json", json.dumps(meta, ensure_ascii=False))
        if "book" not in omit:
            # The job-id prefix is what `_rescue_job` actually writes, because it
            # archives `job.input_path`, and that is the stored upload. A fixture
            # using the bare filename passes while every real archive is refused.
            archive.writestr(f"project/{job_id}_{filename}", book)
        if "chunks" not in omit:
            archive.writestr(
                "project/chunks.json",
                json.dumps({"chunks": [[c, f"<p>{c}</p>"] for c in chunks]}, ensure_ascii=False),
            )
        if "translations" not in omit:
            archive.writestr(
                "project/translations.json", json.dumps(translations, ensure_ascii=False)
            )
        if "glossary" not in omit:
            archive.writestr("project/glossary.json", json.dumps({"terms": []}))
        if "events" not in omit:
            archive.writestr("project/events.jsonl", "")
        for name, blob in (extra or {}).items():
            archive.writestr(name, blob)
    return buffer.getvalue()


class TestReadRescue:
    def test_reads_the_metadata(self):
        imported = read_rescue(make_rescue())
        assert imported.job_id == "abc123"
        assert imported.filename == "overthesevensea.epub"
        assert imported.filetype == "epub"
        assert imported.from_lang == "EN"
        assert imported.to_lang == "FA"
        assert imported.model == "gpt-5.6-luna"

    def test_carries_the_book_and_the_job_files(self):
        imported = read_rescue(make_rescue())
        assert imported.book_bytes == BOOK
        assert "chunks.json" in imported.job_files
        assert "translations.json" in imported.job_files

    def test_rebuilds_the_counts_from_the_text(self):
        # job_state.json is not in a rescue archive, so 4 chunks and 2
        # translations has to come out as (4, 2).
        imported = read_rescue(make_rescue())
        assert imported.chunks_total == 4
        assert imported.chunks_completed == 2
        assert imported.chunks_remaining == 2

    def test_an_empty_translation_is_not_progress(self):
        # A chunk that was started and failed is keyed with an empty string.
        # Counting keys would call that done and the resume would skip it.
        imported = read_rescue(
            make_rescue(translations={"chunk-0": "متن", "chunk-1": "", "chunk-2": "   "})
        )
        assert imported.chunks_completed == 1
        assert imported.chunks_remaining == 3

    def test_a_fully_translated_archive_has_nothing_remaining(self):
        imported = read_rescue(
            make_rescue(translations={c: "متن" for c in CHUNKS})
        )
        assert imported.chunks_remaining == 0

    def test_the_metadata_is_found_without_relying_on_its_name(self):
        # The name is a convention, not a guarantee. A writer that renamed the
        # file must not make a rescue unrecoverable.
        payload = make_rescue()
        buffer = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(payload)) as src, zipfile.ZipFile(buffer, "w") as dst:
            for name in src.namelist():
                data = src.read(name)
                if name.endswith("abc123.json"):
                    name = "project/state-of-the-world.json"
                dst.writestr(name, data)
        assert read_rescue(buffer.getvalue()).job_id == "abc123"

    def test_finds_the_book_under_its_stored_upload_name(self):
        """The bug the live check found.

        `_rescue_job` archives `project/{job_path.name}`, and the job path is the
        *stored* upload -- `data/uploads/{job_id}_{filename}` -- so a real archive
        holds `project/e63c36fe2d3a_overthesevensea.epub` while the metadata says
        `filename: overthesevensea.epub`. Looking for the metadata's name refuses
        every rescue this product has ever produced.

        It passed the unit tests because the fixture wrote the bare name, which is
        not what the writer does. So the fixture is fixed, and this pins the
        shape.
        """
        payload = make_rescue(job_id="e63c36fe2d3a", filename="overthesevensea.epub")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            stored = [n for n in archive.namelist() if n.endswith(".epub")]
            assert stored == ["project/e63c36fe2d3a_overthesevensea.epub"]
        imported = read_rescue(payload)
        assert imported.book_bytes == BOOK
        assert imported.filename == "overthesevensea.epub"

    def test_an_exact_name_wins_over_a_prefixed_one(self):
        # A filename may itself contain underscores, so a chapter file can look
        # like a prefix match. The exact name has to take priority.
        payload = make_rescue(filename="part_one.epub")
        buffer = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(payload)) as src, zipfile.ZipFile(buffer, "w") as dst:
            for name in src.namelist():
                data = src.read(name)
                if name.endswith(".epub"):
                    # A decoy that also ends with "_part_one.epub".
                    dst.writestr("project/other_part_one.epub", b"DECOY")
                dst.writestr(name, data)
        imported = read_rescue(buffer.getvalue())
        assert imported.book_bytes == BOOK, "picked the decoy"

    def test_an_ambiguous_suffix_match_refuses_rather_than_guessing(self):
        # The book is stored under a name that is neither the bare filename nor
        # `{job_id}_{filename}`, and two other members end with the same suffix.
        # There is no correct answer, and restoring one of them would put the
        # wrong book on the server under a job id that says otherwise.
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("project/abc123.json", json.dumps({
                "id": "abc123",
                "filename": "part_one.epub",
                "pipeline_job_id": "abc123_part_one_EN_FA_m_1",
                "options": {"from_lang": "EN", "to_lang": "FA", "model": "m"},
            }))
            archive.writestr("project/chunks.json", json.dumps({"chunks": []}))
            archive.writestr("project/aaa_part_one.epub", b"WRONG")
            archive.writestr("project/bbb_part_one.epub", b"ALSO WRONG")
        with pytest.raises(RescueError, match="کتاب"):
            read_rescue(buffer.getvalue())

    def test_chunks_json_is_not_mistaken_for_the_metadata(self):
        # Both parse as JSON. Selecting by name alone would restore the chunk
        # list as if it were the job's settings, and the import would "succeed"
        # with no book and no languages.
        imported = read_rescue(make_rescue())
        assert imported.from_lang == "EN"
        assert imported.job_id == "abc123"


    def test_reads_the_recorded_chunking_settings(self):
        # Every rescue written by the current `_rescue_job` carries this, and the
        # first implementation read it after the `with archive:` block had closed.
        # No test caught that, because no fixture had a `chunking.json` at all --
        # a file every real archive has, on a path nothing had reached.
        payload = make_rescue(extra={
            "project/chunking.json": json.dumps({
                "semantic_chunking": True,
                "chunk_max_tokens": 3000,
                "chunk_context_window": 2,
                "created_at": "2026-09-28T12:00:00+00:00",
            })
        })
        imported = read_rescue(payload)
        assert imported.chunking_settings == {
            "semantic_chunking": True,
            "chunk_max_tokens": 3000,
            "chunk_context_window": 2,
        }

    def test_an_archive_without_them_reports_none(self):
        assert read_rescue(make_rescue()).chunking_settings is None

    def test_the_settings_are_not_restored_into_the_job_directory(self, tmp_path):
        # It is metadata about the archive, not something the pipeline reads back.
        payload = make_rescue(extra={"project/chunking.json": json.dumps({"chunk_max_tokens": 3000})})
        imported = read_rescue(payload)
        written = restore(imported, tmp_path / "uploads", tmp_path / "temp")
        assert "chunking.json" not in written
        assert not (Path(written["job_dir"]) / "chunking.json").exists()


class TestRejections:
    def test_not_a_zip(self):
        with pytest.raises(RescueError, match="زیپ"):
            read_rescue(b"this is not a zip file at all")

    def test_a_zip_with_no_project_folder(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("readme.txt", "hello")
        with pytest.raises(RescueError, match="نجاتی"):
            read_rescue(buffer.getvalue())

    def test_no_metadata(self):
        with pytest.raises(RescueError, match="نجاتی"):
            read_rescue(make_rescue(omit={"meta"}))

    def test_no_chunks(self):
        # Without the chunk list there is nothing to resume *from*.
        with pytest.raises(RescueError, match="بخش"):
            read_rescue(make_rescue(omit={"chunks"}))

    def test_no_book(self):
        with pytest.raises(RescueError, match="کتاب"):
            read_rescue(make_rescue(omit={"book"}))

    def test_two_metadata_files_is_ambiguous(self):
        # Better to refuse than to restore whichever sorted first.
        payload = make_rescue()
        buffer = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(payload)) as src, zipfile.ZipFile(buffer, "w") as dst:
            for name in src.namelist():
                data = src.read(name)
                dst.writestr(name, data)
                if name.endswith("abc123.json"):
                    dst.writestr("project/copy.json", data)
        with pytest.raises(RescueError, match="مبهم"):
            read_rescue(buffer.getvalue())

    def test_a_non_book_extension(self):
        with pytest.raises(RescueError, match="EPUB"):
            read_rescue(make_rescue(filename="notes.txt"))

    def test_a_corrupt_member(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("project/a.json", b"not json at all")
            archive.writestr("project/b.json", b"\x00\x01\x02")
        with pytest.raises(RescueError):
            read_rescue(buffer.getvalue())


class TestPathTraversal:
    """The archive is untrusted, and `ZipFile.extractall` follows `../`."""

    def _archive_with(self, member: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("project/abc123.json", json.dumps({
                "id": "abc123", "filename": "b.epub",
                "pipeline_job_id": "abc123_b_EN_FA_m_1", "options": {},
            }))
            archive.writestr("project/chunks.json", json.dumps({"chunks": []}))
            archive.writestr("project/b.epub", BOOK)
            archive.writestr(member, "pwned")
        return buffer.getvalue()

    def test_a_parent_reference_is_refused(self):
        with pytest.raises(RescueError, match="بیرون"):
            read_rescue(self._archive_with("project/../../../../startup.py"))

    def test_a_deep_parent_reference_is_refused(self):
        with pytest.raises(RescueError, match="بیرون"):
            read_rescue(self._archive_with("../evil.txt"))

    def test_an_absolute_path_is_refused(self):
        with pytest.raises(RescueError, match="مطلق"):
            read_rescue(self._archive_with("/etc/passwd"))

    def test_a_windows_separator_is_refused(self):
        # Python's `zipfile` rewrites "\" to "/" on write, so an archive built
        # through it never reaches this guard -- the name arrives already
        # normalised and the ".." rule above catches it. The guard is for an
        # archive written by something else that stored a literal backslash,
        # which a Windows extractor would treat as a separator. Tested directly,
        # because going through `zipfile` cannot produce the input.
        import app.jobs.rescue as rescue

        class Member:
            def __init__(self, filename: str, size: int = 5) -> None:
                self.filename = filename
                self.file_size = size

        class FakeArchive:
            def infolist(self):
                return [Member("project/..\\..\\startup.py")]

        with pytest.raises(RescueError, match="ویندوز"):
            rescue._check_members(FakeArchive())

    def test_a_backslash_written_through_zipfile_is_still_refused(self):
        # What actually happens when a caller tries: the name is normalised to
        # forward slashes, and the ".." rule is what refuses it. Both branches
        # must refuse; this pins the one that fires.
        with pytest.raises(RescueError, match="بیرون"):
            read_rescue(self._archive_with("project/..\\..\\startup.py"))

    def test_a_drive_letter_is_refused(self):
        with pytest.raises(RescueError, match="مطلق"):
            read_rescue(self._archive_with("C:/Windows/system32/x.txt"))

    def test_a_job_id_that_escapes_is_refused(self):
        # pipeline_job_id becomes a directory name under temp/.
        with pytest.raises(RescueError, match="شناسه"):
            read_rescue(make_rescue(pipeline_job_id="../../../escape"))

    def test_an_oversized_expansion_is_refused(self, monkeypatch):
        import app.jobs.rescue as rescue

        monkeypatch.setattr(rescue, "MAX_EXPANDED_BYTES", 10)
        with pytest.raises(RescueError, match="حجم"):
            read_rescue(make_rescue())


class TestRestore:
    def test_writes_the_book_and_the_job_state(self, tmp_path):
        imported = read_rescue(make_rescue())
        written = restore(imported, tmp_path / "uploads", tmp_path / "temp")

        book = Path(written["book"])
        assert book.name == "abc123_overthesevensea.epub"
        assert book.read_bytes() == BOOK

        job_dir = Path(written["job_dir"])
        assert job_dir.name == imported.pipeline_job_id
        assert (job_dir / "chunks.json").exists()
        assert (job_dir / "translations.json").exists()
        assert (job_dir / "glossary.json").exists()

    def test_rebuilds_job_state(self, tmp_path):
        # This is the file the resume path reads, and the one a rescue archive
        # does not carry.
        imported = read_rescue(make_rescue())
        written = restore(imported, tmp_path / "uploads", tmp_path / "temp")
        state = json.loads(Path(written["job_state.json"]).read_text(encoding="utf-8"))
        assert state["chunks_total"] == 4
        assert state["chunks_completed"] == 2

    def test_the_book_stem_matches_the_job_directory(self, tmp_path):
        # `find_resumable_jobs` -- and therefore the estimate dialog -- looks for
        # a temp directory starting with "{book stem}_{from}_{to}_{model}_". If
        # these two names drift apart the import "works" and then the estimate
        # reports a fresh full-price run.
        imported = read_rescue(make_rescue())
        written = restore(imported, tmp_path / "uploads", tmp_path / "temp")
        stem = Path(written["book"]).stem
        assert Path(written["job_dir"]).name.startswith(stem)

    def test_importing_twice_replaces_rather_than_merges(self, tmp_path):
        # A second import of a further-along archive must win. Merging would leave
        # stale translations from the first import in place.
        first = read_rescue(make_rescue(translations={"chunk-0": "قدیمی"}))
        uploads, temp = tmp_path / "uploads", tmp_path / "temp"
        restore(first, uploads, temp)
        second = read_rescue(make_rescue(translations={c: "جدید" for c in CHUNKS}))
        written = restore(second, uploads, temp)

        stored = json.loads(Path(written["translations.json"]).read_text(encoding="utf-8"))
        assert set(stored.values()) == {"جدید"}
        assert "قدیمی" not in stored.values()

    def test_unknown_files_in_the_archive_are_not_written(self, tmp_path):
        # Only the known job files are restored. Everything else in the archive is
        # data the pipeline reads through a path it computes, so copying it would
        # put unvetted bytes in the job directory.
        payload = make_rescue(extra={"project/notes.txt": "hello", "project/run.sh": "#!/bin/sh"})
        imported = read_rescue(payload)
        written = restore(imported, tmp_path / "uploads", tmp_path / "temp")
        job_dir = Path(written["job_dir"])
        assert not (job_dir / "notes.txt").exists()
        assert not (job_dir / "run.sh").exists()
        for name in JOB_FILES:
            if name in imported.job_files:
                assert (job_dir / name).exists()

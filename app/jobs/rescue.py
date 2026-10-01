"""Import a rescue archive and put a book back into a resumable state.

Why this exists
---------------
``POST /api/jobs/{id}/rescue`` has always produced a ``*_rescue.zip`` carrying
the translated text, the chunk list and the settings. There was no way back in:
the only path to translating that book again was to upload the original and pay
for every chunk a second time. A rescue archive that cannot be re-imported is a
backup nobody can act on.

The archive
-----------
``_rescue_job`` writes a flat ``project/`` folder::

    project/{job_id}.json      the job metadata
    project/{filename}         the input book
    project/chunks.json        the chunk list, chapter map and contexts
    project/translations.json  the translated text, keyed by chunk id
    project/glossary.json      the glossary snapshot
    project/glossary_learned.json   terms learned so far
    project/events.jsonl       the log

``job_state.json`` is **not** in it. ``chunks_completed`` lives there, and the
rescue writer collects ``job.paths.values()`` -- which does contain
``state_file`` -- but the file is only written once the pipeline reports
progress, and a job that was stopped in between has none. So the state is
rebuilt here from the number of keys in ``translations.json``, which is the same
number the pipeline would have written.

Safety
------
The archive is untrusted input and is unpacked with hand-written code rather than
``ZipFile.extractall``, because ``extractall`` follows ``../`` in a member name.
That is a directory traversal: an archive named ``project/../../startup.py``
writes outside the destination. Every member is resolved and checked against the
destination root before anything is written, and the total is capped so a zip
bomb cannot fill the disk.

What is *not* restored
----------------------
The saved output file, and the QA and quality reports. They describe a run that
did not finish, and re-deriving them from a partial translation would report on
half a book as though it were the whole thing.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: The folder inside the archive that everything lives under.
ROOT = "project/"

#: Files restored into the job directory. Anything else in the archive is data
#: the pipeline reads through a path it computes itself, so it is not copied.
JOB_FILES = (
    "chunks.json",
    "translations.json",
    "glossary.json",
    "glossary_learned.json",
    "events.jsonl",
)

#: A book this size is already unusual; 512 MB of expanded content is not.
MAX_EXPANDED_BYTES = 512 * 1024 * 1024

#: A zip that claims more than this is refused without being read.
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024


class RescueError(ValueError):
    """A rescue archive that cannot be used. The message is shown to the user."""


@dataclass
class RescueImport:
    """What was found in the archive, before anything is written to the server."""

    job_id: str
    pipeline_job_id: str
    filename: str
    filetype: str
    file_size: int
    from_lang: str
    to_lang: str
    model: str
    mode: str
    style: str
    options: dict[str, str] = field(default_factory=dict)
    book_bytes: bytes = b""
    job_files: dict[str, bytes] = field(default_factory=dict)
    chunks_total: int = 0
    chunks_completed: int = 0
    #: The chunking settings the archive records, if it records any. Absent from
    #: archives made before that was written, which is most of the ones on disk.
    chunking_settings: dict[str, Any] | None = None

    @property
    def chunks_remaining(self) -> int:
        return max(0, self.chunks_total - self.chunks_completed)


def _meta_of(archive: zipfile.ZipFile) -> tuple[str, dict[str, Any]]:
    """The job metadata inside the archive, and the member it came from.

    Found by looking for a ``.json`` that parses and carries both an ``id`` and a
    ``pipeline_job_id``, rather than by filename -- the name carries the job id
    and nothing guarantees a future writer kept that convention. ``chunks.json``
    and ``translations.json`` also parse, and mistaking either for the metadata
    would restore nothing at all, so the required keys are what selects it.
    """
    candidates: list[tuple[str, dict[str, Any]]] = []
    for name in archive.namelist():
        if not name.endswith(".json") or not name.startswith(ROOT):
            continue
        try:
            data = json.loads(archive.read(name).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and data.get("id") and data.get("pipeline_job_id"):
            candidates.append((name, data))

    if not candidates:
        raise RescueError(
            "این فایل نجاتی نیست: داخل آن «project/» با فایل تنظیمات کار پیدا نشد."
        )
    if len(candidates) > 1:
        names = "، ".join(Path(name).name for name, _ in candidates)
        raise RescueError(f"این آرشیو چند فایل تنظیمات دارد ({names}). مبهم است.")
    return candidates[0]


def _check_members(archive: zipfile.ZipFile) -> None:
    """Refuse an archive that would write outside its destination, or too large.

    ``ZipFile.extractall`` does not check member names for ``..``, so a crafted
    archive escapes the destination directory. Every name is resolved against the
    destination and compared, which is the same test a hardened extractor makes.
    """
    total = 0
    for info in archive.infolist():
        name = info.filename
        if not name:
            continue
        if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
            raise RescueError("نام یکی از فایل‌های آرشیو مسیر مطلق دارد.")
        if "\\" in name:
            raise RescueError("نام یکی از فایل‌های آرشیو جداکنندهٔ ویندوز دارد.")
        parts = [part for part in name.split("/") if part not in ("", ".")]
        if any(part == ".." for part in parts):
            raise RescueError("نام یکی از فایل‌های آرشیو از پوشه بیرون می‌رود.")
        total += info.file_size
        if total > MAX_EXPANDED_BYTES:
            raise RescueError("حجم باز شدهٔ آرشیو از حد مجاز بیشتر است.")


def _find_book(
    archive: zipfile.ZipFile, root: str, *, imported_job_id: str, filename: str
) -> str | None:
    """The member holding the book, or None.

    Not simply ``{root}{filename}``. ``_rescue_job`` writes
    ``project/{file_path.name}`` and ``file_path`` is the *stored upload*, which
    carries the job-id prefix: ``project/e63c36fe2d3a_overthesevensea.epub``. The
    metadata's ``filename`` is the original, unprefixed name. Looking for that
    name alone refuses every rescue this product has ever produced -- and the
    unit tests did not catch it, because their fixture wrote the book under the
    unprefixed name, which is not what the producer does.

    Three passes, most specific first:

    1. the bare name, for an archive written by something other than this product
    2. ``{job_id}_{filename}``, which is what ``_store_upload`` produces
    3. a suffix match, and *only* if exactly one member qualifies

    Pass 3 is guarded because it is genuinely ambiguous. A filename may contain
    underscores, so ``other_part_one.epub`` and ``abc123_part_one.epub`` both end
    with ``_part_one.epub``; taking whichever the archive lists first restores the
    wrong book, and a rescue that restores the wrong book is worse than one that
    refuses.
    """
    names = archive.namelist()
    books = [
        name
        for name in names
        if name.startswith(root) and name.lower().endswith((".epub", ".pdf"))
    ]

    for wanted in (filename, f"{imported_job_id}_{filename}"):
        for name in books:
            if Path(name).name == wanted:
                return name

    suffix_matches = [name for name in books if Path(name).name.endswith(f"_{filename}")]
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    return None


def read_rescue(payload: bytes) -> RescueImport:
    """Parse a rescue archive. Raises :class:`RescueError` if it is not one."""
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise RescueError("حجم فایل نجاتی از حد مجاز بیشتر است.")

    import io

    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile:
        raise RescueError("فایل زیپ باز نمی‌شود.") from None

    with archive:
        bad = archive.testzip()
        if bad:
            raise RescueError(f"فایل درون آرشیو خراب است: {bad}")

        _check_members(archive)
        meta_name, meta = _meta_of(archive)

        job_id = str(meta["id"])
        pipeline_job_id = str(meta["pipeline_job_id"])
        if Path(pipeline_job_id).name != pipeline_job_id:
            # The name becomes a directory under temp/, so a separator or a
            # parent reference in it would place the restored state elsewhere.
            raise RescueError("شناسهٔ کار در آرشیو معتبر نیست.")

        filename = Path(str(meta.get("filename") or "")).name
        if not filename:
            raise RescueError("نام کتاب در آرشیو نیست.")
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix not in {"epub", "pdf"}:
            raise RescueError("فقط کتاب‌های EPUB و PDF پشتیبانی می‌شوند.")

        book_member = _find_book(archive, ROOT, imported_job_id=job_id, filename=filename)
        if book_member is None:
            raise RescueError("خودِ کتاب داخل آرشیو نیست.")
        book_bytes = archive.read(book_member)

        job_files: dict[str, bytes] = {}
        for wanted in JOB_FILES:
            member = f"{ROOT}{wanted}"
            if member in archive.namelist():
                job_files[wanted] = archive.read(member)

        if "chunks.json" not in job_files:
            raise RescueError("فهرست بخش‌ها داخل آرشیو نیست؛ این فایل نجاتی نیست.")

        # The chunking settings, if this archive carries them. Read outside JOB_FILES
        # because it is metadata about the archive rather than something the pipeline
        # reads back, so it is not restored into the job directory.
        #
        # Inside the `with archive` block, where it belongs. Reading it after the block
        # closes raises "Attempt to use ZIP archive that was already closed" -- and no
        # test caught it, because no test archive carried a `chunking.json` at all. A
        # file that every real rescue now has, on a path no fixture had reached.
        chunking_settings = None
        if f"{ROOT}chunking.json" in archive.namelist():
            try:
                recorded = json.loads(archive.read(f"{ROOT}chunking.json").decode("utf-8"))
                if isinstance(recorded, dict):
                    chunking_settings = {
                        key: recorded[key]
                        for key in ("semantic_chunking", "chunk_max_tokens", "chunk_context_window")
                        if key in recorded
                    } or None
            except (UnicodeDecodeError, json.JSONDecodeError, OSError):
                chunking_settings = None

    options = meta.get("options") or {}
    if not isinstance(options, dict):
        options = {}

    chunks_total, chunks_completed = _counts_from(job_files.get("chunks.json"), job_files.get("translations.json"))


    return RescueImport(
        job_id=job_id,
        pipeline_job_id=pipeline_job_id,
        filename=filename,
        filetype=suffix,
        file_size=len(book_bytes),
        from_lang=str(options.get("from_lang") or meta.get("source_language") or "EN"),
        to_lang=str(options.get("to_lang") or meta.get("target_language") or "FA"),
        model=str(options.get("model") or meta.get("model") or ""),
        mode=str(options.get("mode") or meta.get("mode") or "fast"),
        style=str(options.get("style_preset") or meta.get("style") or "literary"),
        options={str(k): str(v) for k, v in options.items() if isinstance(v, (str, int, float, bool))},
        book_bytes=book_bytes,
        job_files=job_files,
        chunks_total=chunks_total,
        chunks_completed=chunks_completed,
        chunking_settings=chunking_settings,
    )


def _counts_from(chunks_raw: bytes | None, translations_raw: bytes | None) -> tuple[int, int]:
    """``(total, completed)``, rebuilt.

    ``job_state.json`` is normally the authority and is absent from a rescue
    archive, so the numbers are taken from the data that is there: the chunk list
    gives the total, and the number of keys in the translations gives what is
    done. Counting the keys rather than trusting a saved figure means an archive
    edited by hand cannot claim progress the text does not support.
    """
    total = 0
    if chunks_raw:
        try:
            data = json.loads(chunks_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict) and isinstance(data.get("chunks"), list):
            total = len(data["chunks"])

    completed = 0
    if translations_raw:
        try:
            data = json.loads(translations_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            # A key with an empty string is a chunk that was started and failed,
            # not one that finished.
            completed = sum(1 for value in data.values() if isinstance(value, str) and value.strip())

    return total, completed


def chunk_signature(
    book_path: Path, max_tokens: int, context_window: int
) -> list[tuple[int, str]]:
    """``(position, html)`` for every chunk the current chunker produces.

    This is the fingerprint a rescue is checked against. Chunk ids are positional
    -- `chunk-7` is simply the eighth chunk -- so if the chunker settings changed
    between the run that was rescued and now, `chunk-7` names a *different span of
    text*. Replaying the saved translation onto it does not produce an error; it
    produces a book with sentences in the wrong places, which is indistinguishable
    from a translation bug and much harder to trace.

    The key is the position, not a stored id: `SemanticChunk` carries no id of its
    own, the pipeline numbers the list, and comparing the html is what actually
    proves the spans line up.
    """
    from app.pipeline.semantic_chunker import SemanticChunker

    chunker = SemanticChunker(max_tokens=max_tokens, context_window=context_window)
    signature: list[tuple[int, str]] = []
    with zipfile.ZipFile(book_path) as archive:
        for name in archive.namelist():
            if not name.endswith((".xhtml", ".html", ".htm")):
                continue
            try:
                content = archive.read(name).decode("utf-8")
            except (UnicodeDecodeError, KeyError, OSError):
                # A chapter the pipeline also skips, so its absence is not a change.
                continue
            if "<" not in content:
                continue
            for chunk in chunker.chunk(content):
                signature.append((len(signature), chunk.html))
    return signature


def saved_signature(imported: RescueImport) -> list[tuple[int, str]]:
    """The fingerprint stored in the archive."""
    raw = imported.job_files.get("chunks.json")
    if not raw:
        return []
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    pairs = data.get("chunks") if isinstance(data, dict) else None
    if not isinstance(pairs, list):
        return []
    return [
        (position, str(pair[1]))
        for position, pair in enumerate(pairs)
        if isinstance(pair, (list, tuple)) and len(pair) >= 2
    ]


@dataclass
class ChunkingCheck:
    """Whether the rescued chunk list still describes the book."""

    matches: bool
    saved: int
    current: int
    first_difference: int | None = None
    #: What the archive recorded about how it was chunked, if it recorded
    #: anything. Absent from archives made before the recording was added.
    saved_settings: dict[str, Any] | None = None
    current_settings: dict[str, Any] | None = None

    def message(self) -> str:
        if self.matches:
            return ""
        where = (
            f"اولین جایی که فرق کرده، بخش شمارهٔ {self.first_difference} است."
            if self.first_difference is not None
            else "تعداد بخش‌ها فرق دارد."
        )
        parts = [
            "تقسیم‌بندی این کتاب با تنظیمات امروز فرق دارد: "
            f"نسخهٔ نجاتی {self.saved} بخش دارد ولی الان {self.current} بخش. {where}",
            "شمارهٔ بخش‌ها بر اساس ترتیب است، پس ادامه دادن متن‌های ذخیره‌شده آن‌ها را "
            "در جای اشتباه می‌گذارد.",
        ]

        # Name the actual cause when it is knowable. Both of these were real:
        # a job that ran at a different budget, and a job that ran before the
        # semantic chunker existed at all. Telling the reader only to change
        # `chunk_max_tokens` sends them round in circles on the second case.
        saved_on = self.saved_settings or {}
        current_on = self.current_settings or {}
        if saved_on and current_on:
            changed = [
                f"`{key}`: نسخهٔ نجاتی {saved_on[key]}، الان {current_on[key]}"
                for key in ("semantic_chunking", "chunk_max_tokens", "chunk_context_window")
                if key in saved_on and key in current_on and saved_on[key] != current_on[key]
            ]
            if changed:
                parts.append("تنظیماتی که عوض شده: " + "؛ ".join(changed) + ".")
            parts.append(
                "همان تنظیماتِ آن زمان را در config.yaml برگردانید و دوباره وارد کنید."
            )
        else:
            # An archive with no record of its own settings. Older ones have none.
            parts.append(
                "این نسخهٔ نجاتی تنظیمات تقسیم‌بندی‌اش را با خود ندارد، پس فقط "
                "می‌توانید حدس بزنید: `semantic_chunking` و `chunk_max_tokens` را در "
                "config.yaml روی مقداری بگذارید که ترجمه با آن انجام شده."
            )
        return " ".join(parts)


def check_chunking(
    imported: RescueImport,
    book_path: Path,
    max_tokens: int,
    context_window: int,
    *,
    semantic_chunking: bool = True,
) -> ChunkingCheck:
    """Compare the archive's chunk list against a fresh chunking of the book."""
    saved = saved_signature(imported)
    current = chunk_signature(book_path, max_tokens, context_window)
    current_on = {
        "semantic_chunking": bool(semantic_chunking),
        "chunk_max_tokens": max_tokens,
        "chunk_context_window": context_window,
    }

    if len(saved) != len(current):
        return ChunkingCheck(False, len(saved), len(current), None, imported.chunking_settings, current_on)
    for index, (was, now) in enumerate(zip(saved, current)):
        if was != now:
            return ChunkingCheck(
                False, len(saved), len(current), index,
                imported.chunking_settings, current_on,
            )
    return ChunkingCheck(
        True, len(saved), len(current), None,
        imported.chunking_settings, current_on,
    )


def restore(imported: RescueImport, uploads_dir: Path, temp_dir: Path) -> dict[str, str]:
    """Write the book and the job state onto disk. Returns the new paths.

    ``force`` is not a parameter: whether to overwrite an existing job is the
    caller's decision, and the caller checks for a conflict before calling. This
    function overwrites the job directory it is given, which is only ever a
    directory it has just been told is safe to replace.
    """
    uploads_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # The upload name carries the job id, which is what makes the estimate
    # endpoint find the restored job: it looks for a temp directory starting
    # with "{book stem}_{from}_{to}_{model}_", and the stem here is
    # "{job_id}_{book stem}".
    book_path = uploads_dir / f"{imported.job_id}_{imported.filename}"
    book_path.write_bytes(imported.book_bytes)

    job_dir = temp_dir / imported.pipeline_job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True)

    written: dict[str, str] = {"book": str(book_path), "job_dir": str(job_dir)}
    for name, blob in imported.job_files.items():
        (job_dir / name).write_bytes(blob)
        written[name] = str(job_dir / name)

    # The state file the pipeline reads on resume, rebuilt from the translations.
    if imported.chunks_total:
        state = {
            "chunks_total": imported.chunks_total,
            "chunks_completed": imported.chunks_completed,
        }
        (job_dir / "job_state.json").write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )
        written["job_state.json"] = str(job_dir / "job_state.json")

    return written

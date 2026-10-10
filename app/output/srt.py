# ============================================================
# app/output/srt.py
# ============================================================
"""
OUTPUT: SRT

Subtitle translation with guaranteed timecode fidelity.

    parse_srt()            SRT text -> blocks
    serialize_srt()        blocks -> SRT text
    break_long_lines()     enforce the 42-char broadcasting limit
    validate_srt()         structural + timecode QA validator
    translate_srt()        full standalone translation flow (.srt input,
                           original timecodes preserved)
    segments_to_srt_blocks()  book segments (epub/pdf) -> blocks with
                           ESTIMATED timing (books have no timecodes)

The validator is deliberately a separate concern: it verifies the
final output (indices sequential, timecode syntax, chronological
order, line length) so timecodes are never silently altered.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.models import resolve_default_model
from app.core.paths import create_job_id, ensure_temp_structure
from app.jobs.cleanup import cleanup_files
from app.output.markers import strip_markers
from app.translation.translator import (
    load_test_translations,
    process_translations,
)

MAX_LINE_LENGTH = 42

# Reading-speed model for estimated book timings: ~17 chars/sec is the
# standard subtitle rate. Timings derived from it are estimates — book
# sources carry no timecodes — and callers must label them as such.
ESTIMATED_CHARS_PER_SECOND = 17

TIMECODE_RE = (
    r"^\s*(\d{1,2}):(\d{2}):(\d{2}),(\d{3})"
    r"\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2}),(\d{3})\s*$"
)

SRT_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "utf-16",
    "cp1256",
)


@dataclass
class SrtBlock:
    """
    One subtitle with its original timecodes.
    """

    index: int
    start: str
    end: str
    text: str


def _format_timecode(hours, minutes, seconds, millis):
    """
    Normalize a timecode to ``HH:MM:SS,mmm``.
    """

    return (
        f"{int(hours):02d}:"
        f"{int(minutes):02d}:"
        f"{int(seconds):02d},"
        f"{int(millis):03d}"
    )


def parse_srt(text):
    """
    Parse SRT text into a list of blocks.

    Returns:
        list[SrtBlock]: subtitle blocks in document order.
    """

    blocks = []

    current = None

    buffer = []

    for raw_line in str(text or "").splitlines():

        line = raw_line.strip()

        if not line:

            if current is not None:

                current.text = "\n".join(buffer).strip()

                blocks.append(current)

                current = None

                buffer = []

            continue

        if current is None:

            if line.isdigit():

                current = SrtBlock(
                    index=int(line),
                    start="",
                    end="",
                    text="",
                )

            continue

        match = __import__("re").match(
            TIMECODE_RE,
            line,
        )

        if match and not current.start:

            current.start = _format_timecode(
                match.group(1),
                match.group(2),
                match.group(3),
                match.group(4),
            )

            current.end = _format_timecode(
                match.group(5),
                match.group(6),
                match.group(7),
                match.group(8),
            )

            continue

        buffer.append(line)

    if current is not None:

        current.text = "\n".join(buffer).strip()

        blocks.append(current)

    return blocks


def serialize_srt(blocks):
    """
    Render blocks back to standard SRT text.
    """

    parts = []

    for block in blocks:

        parts.append(
            f"{block.index}\n"
            f"{block.start} --> {block.end}\n"
            f"{block.text}\n"
        )

    return "\n".join(parts)


def break_long_lines(
    text,
    max_length=MAX_LINE_LENGTH,
):
    """
    Break text into subtitle lines not longer than ``max_length``.

    Lines are split at phrase boundaries (nearest space) instead of
    hard-cutting mid-word where possible.
    """

    lines = []

    for paragraph in str(text or "").split("\n"):

        line = paragraph.strip()

        while len(line) > max_length:

            cut = line.rfind(
                " ",
                0,
                max_length + 1,
            )

            if cut <= 0:

                cut = max_length

            lines.append(line[:cut].strip())

            line = line[cut:].strip()

        if line:

            lines.append(line)

    return lines


def merge_translations(
    blocks,
    translations,
):
    """
    Rebuild subtitle blocks keeping original timecodes.

    ``translations`` is keyed by ``chunk-{position}`` (pipeline
    style, matching how ``translate_srt`` numbered the chunks) with
    a fallback to the plain subtitle index.

    Returns:
        tuple: (merged blocks, missing indices). ``missing`` lists the
        subtitle indices that had NO translation entry and fell back to
        the original text, so untranslated content is always visible to
        the caller and never silently passed off as translated.
    """

    merged = []

    missing = []

    for position, block in enumerate(blocks):

        key = f"chunk-{position}"

        index_key = str(block.index)

        if key in (translations or {}):

            translated = translations[key]

        elif index_key in (translations or {}):

            translated = translations[index_key]

        else:

            missing.append(block.index)

            translated = block.text

        clean = strip_markers(translated).strip() or block.text

        merged.append(
            SrtBlock(
                index=block.index,
                start=block.start,
                end=block.end,
                text="\n".join(
                    break_long_lines(clean)
                ),
            )
        )

    return merged, missing


def _ms_to_timecode(total_ms):
    """
    Milliseconds since 00:00:00,000 -> ``HH:MM:SS,mmm``.
    """

    total_ms = max(0, int(total_ms))

    hours, remainder = divmod(total_ms, 3600000)

    minutes, remainder = divmod(remainder, 60000)

    seconds, millis = divmod(remainder, 1000)

    return _format_timecode(hours, minutes, seconds, millis)


def segments_to_srt_blocks(
    segments,
    chars_per_second=ESTIMATED_CHARS_PER_SECOND,
):
    """
    Book segments (EPUB/PDF) -> subtitle blocks with ESTIMATED timing.

    Book sources carry no timecodes, so each block's duration is estimated
    from its translated character count at ``chars_per_second`` and blocks
    run back-to-back from 00:00:00,000. Callers must label the result as
    estimated timing (see the ``srt`` output label).

    Only segments with non-empty translated (``target``) text produce blocks;
    untranslated content is skipped, never emitted as source text.

    Returns:
        list[SrtBlock]: sequential blocks starting at index 1.
    """

    if chars_per_second is None or chars_per_second <= 0:

        raise ValueError(
            "chars_per_second must be a positive number."
        )

    blocks = []

    cursor_ms = 0

    for segment in segments or []:

        text = str((segment or {}).get("target") or "").strip()

        if not text:

            continue

        for line in break_long_lines(text):

            lines = [line]

            chars = max(len(line), 1)

            duration_ms = int(chars / chars_per_second * 1000)

            start = _ms_to_timecode(cursor_ms)

            cursor_ms += duration_ms

            end = _ms_to_timecode(cursor_ms)

            blocks.append(
                SrtBlock(
                    index=len(blocks) + 1,
                    start=start,
                    end=end,
                    text="\n".join(lines),
                )
            )

    # Re-pack pairs of single lines into two-line blocks so the file reads
    # like real subtitles instead of one line per cue. Timing stays cumulative.
    packed = []

    index = 0

    while index < len(blocks):

        first = blocks[index]

        second = (
            blocks[index + 1]
            if index + 1 < len(blocks)
            else None
        )

        if second is not None:

            packed.append(
                SrtBlock(
                    index=len(packed) + 1,
                    start=first.start,
                    end=second.end,
                    text=f"{first.text}\n{second.text}",
                )
            )

            index += 2

        else:

            packed.append(
                SrtBlock(
                    index=len(packed) + 1,
                    start=first.start,
                    end=first.end,
                    text=first.text,
                )
            )

            index += 1

    return packed


def _timecode_ms(timecode):
    """
    Convert ``HH:MM:SS,mmm`` to milliseconds or None.
    """

    parts = str(timecode or "").strip().split(":")

    if len(parts) != 3:

        return None

    tail = parts[2].split(",")

    if len(tail) != 2 or not all(
        part.isdigit()
        for part in parts[:2] + tail
    ):

        return None

    hours, minutes = int(parts[0]), int(parts[1])

    seconds, millis = int(tail[0]), int(tail[1])

    if minutes >= 60 or seconds >= 60 or millis > 999:

        return None

    return (
        (hours * 3600 + minutes * 60 + seconds) * 1000
        + millis
    )


def validate_srt(text):
    """
    Validate SRT structure and timecodes.

    Returns:
        list[str]: human-readable issues (empty when valid).
    """

    issues = []

    blocks = parse_srt(text)

    if not blocks:

        return [
            "No subtitle blocks found. "
            "The file may be empty or malformed."
        ]

    expected = list(range(1, len(blocks) + 1))

    actual = [block.index for block in blocks]

    if actual != expected:

        issues.append(
            f"Subtitle indices are not sequential "
            f"(expected 1..{len(blocks)}, "
            f"got {actual[:5]}...)."
        )

    previous_end = 0

    for block in blocks:

        start_ms = _timecode_ms(block.start)

        end_ms = _timecode_ms(block.end)

        if start_ms is None or end_ms is None:

            issues.append(
                f"Block {block.index} has an invalid "
                "timecode: "
                f"{block.start} --> {block.end}"
            )

            continue

        if end_ms < start_ms:

            issues.append(
                f"Block {block.index} ends before "
                "it starts."
            )

        if start_ms < previous_end:

            issues.append(
                f"Block {block.index} overlaps "
                "the previous subtitle."
            )

        previous_end = end_ms

        for line in block.text.splitlines():

            if len(line) > MAX_LINE_LENGTH:

                issues.append(
                    f"Block {block.index} has a line of "
                    f"{len(line)} chars (max "
                    f"{MAX_LINE_LENGTH})."
                )

    return issues


def _read_text(path):
    """
    Read an SRT file trying the most common encodings.
    """

    path = Path(path)

    last_error = None

    for encoding in SRT_ENCODINGS:

        try:

            return path.read_text(
                encoding=encoding,
            )

        except (
            UnicodeDecodeError,
            LookupError,
        ) as exc:

            last_error = exc

    raise ValueError(
        f"Could not decode subtitle file "
        f"{path}: {last_error}"
    )


def translate_srt(
    client,
    input_path,
    output_path,
    from_lang="EN",
    to_lang="FA",
    model=None,
    mode="fast",
    translation_prompt=None,
    debug=False,
    stop_event=None,
):
    """
    Translate subtitles while preserving every timecode.

    Each subtitle becomes a chunk; after translation the output is
    rebuilt, line-broken to the 42-char limit and validated.
    """

    input_path = Path(input_path)

    output_path = Path(output_path)

    if not model:

        model = resolve_default_model()

    blocks = parse_srt(_read_text(input_path))

    if not blocks:

        print(
            "No subtitle blocks found in input. "
            "[output.srt]"
        )

        return None

    print(
        f"SRT: {len(blocks)} subtitle blocks. "
        "[output.srt]"
    )

    chunks = []

    chapter_map = {}

    for position, block in enumerate(blocks):

        chunk_id = f"chunk-{position}"

        chunks.append(
            (chunk_id, block.text)
        )

        chapter_map[chunk_id] = (
            f"block-{block.index}.srt",
            position,
        )

    job_id = create_job_id(
        input_path,
        from_lang,
        to_lang,
        model,
    )

    paths = ensure_temp_structure(job_id)

    test_translations = None

    if str(mode).lower() == "test":

        test_translations = load_test_translations(
            input_path
        )

        if test_translations is None:

            print(
                "Test mode requires a companion "
                "translations JSON next to the SRT file. "
                "[output.srt]"
            )

            return None

    translations, input_file_id, status = (
        process_translations(
            client,
            chunks,
            {},
            mode,
            from_lang,
            to_lang,
            paths,
            model=model,
            test_translations=test_translations,
            debug=debug,
            chapter_map=chapter_map,
            filetype="srt",
            translation_prompt=translation_prompt,
            stop_event=stop_event,
        )
    )

    if not translations:

        print(
            "No SRT translations produced. "
            "[output.srt]"
        )

        return None

    merged, missing = merge_translations(
        blocks,
        translations,
    )

    rendered = serialize_srt(merged)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        rendered,
        encoding="utf-8",
    )

    issues = validate_srt(rendered)

    if missing:

        issues = issues + [
            f"Block {index} has no translation and "
            f"keeps the original text."
            for index in missing
        ]

    if issues:

        qa_path = output_path.with_suffix(
            ".qa.txt"
        )

        qa_path.write_text(
            "SRT QA REPORT\n"
            + "=" * 40
            + "\n"
            + "\n".join(issues)
            + "\n",
            encoding="utf-8",
        )

        print(
            f"SRT validation: {len(issues)} issue(s) "
            f"written to {qa_path} [output.srt]"
        )

    if not debug:

        cleanup_files(
            client,
            [],
            temp_dir=paths["job_dir"],
            keep_temp=False,
        )

    print(
        f"Translated SRT saved to: "
        f"{output_path} [output.srt]"
    )

    return output_path
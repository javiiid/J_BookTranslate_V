# ============================================================
# app/output/segments.py
# ============================================================
"""
Segment records shared by every output generator.

A segment is one translated chunk with:

    - id           chunk id (e.g. "chunk-3")
    - source       original plain text
    - target       translated plain text (markers removed)
    - format       input file type (epub/pdf/srt)
    - chapter      source chapter/file name
    - flagged      True when the engine emitted a QA marker
    - notes        collected ``{NOTE: ...}`` explanations
"""

from __future__ import annotations

import html as html_module
import re
from pathlib import Path

from app.output.markers import extract_markers

HTML_TAG_RE = re.compile(r"<[^>]+>")

WHITESPACE_RE = re.compile(r"[ \t\u200c]+")

SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.!?,;:،؛»\"')…-])")

TRAILING_NUMBER_RE = re.compile(r"(\d+)\s*$")


def _html_to_text(value):
    """
    Convert chunk HTML to readable plain text.
    """

    text = HTML_TAG_RE.sub(
        " ",
        str(value or ""),
    )

    text = html_module.unescape(text)

    text = WHITESPACE_RE.sub(" ", text)

    text = SPACE_BEFORE_PUNCT_RE.sub(
        r"\1",
        text,
    )

    return text.strip()


def chapter_name(chapter_map, chunk_id):
    """
    Resolve the logical chapter/file for a chunk.

    ``chapter_map`` values may be ``(filename, pos)`` tuples (as
    produced by the EPUB builder) or ``{"item": ..., "pos": ...}``
    dicts (as persisted to ``chunks.json``).
    """

    location = (chapter_map or {}).get(chunk_id)

    if isinstance(location, dict):

        return str(location.get("item", "") or "")

    if isinstance(location, (tuple, list)) and len(location) >= 1:

        return str(location[0])

    return ""


def chunk_position(chunk_id):
    """
    Numeric position of a chunk for stable ordering.
    """

    match = TRAILING_NUMBER_RE.search(str(chunk_id))

    return int(match.group(1)) if match else -1


def build_segments(
    all_chunks,
    translations,
    chapter_map=None,
    filetype="epub",
):
    """
    Build ordered segment records from translation state.

    Segments without a translation are skipped so every output
    format only ever contains completed content.
    """

    segments = []

    for chunk_id, source in all_chunks or []:

        chunk_id = str(chunk_id)

        translated = (translations or {}).get(chunk_id)

        if translated is None:

            continue

        target, flags, notes = extract_markers(
            translated
        )

        segments.append(
            {
                "id": chunk_id,
                "position": chunk_position(chunk_id),
                "source": _html_to_text(source),
                "target": target,
                "format": str(filetype).lower().lstrip("."),
                "chapter": chapter_name(
                    chapter_map,
                    chunk_id,
                ),
                "flagged": bool(flags) or bool(notes),
                "notes": notes,
            }
        )

    segments.sort(
        key=lambda item: (
            item["chapter"],
            item["position"],
        )
    )

    return segments


def chapter_title(chapter):
    """
    Human-readable heading for a chapter path.

    A filename is not a heading. Converting a PDF gives every "chapter" the name
    of the page file it came from, so a six-page PDF came out with a document
    whose navigation pane read ``page_0000.html``, ``page_0001.html``, and so on
    -- six headings, none of them meaning anything to a reader.

    A name that looks like a generated artefact returns nothing instead, and the
    caller falls back to a single heading for the whole book. That is what a PDF
    actually has: no chapters, only pages.

    The test is deliberately narrow. A real EPUB chapter is named after the book
    (``ch07.html``, ``ch03.xhtml``), which is not what a converter's page naming
    looks like -- those carry a page prefix, an index, and a known extension.
    """
    if not chapter:
        return "Chapter"

    name = Path(str(chapter)).name
    stem = Path(name).stem

    # page_0003, page-0003, page3, p003, 0003, doc_0003 -- a page, not a chapter.
    if re.fullmatch(r"(page|p|pg|doc|img)?[-_ ]?\d+", stem, re.IGNORECASE):
        return ""
    # A bare index, and the converters' own page files.
    if re.fullmatch(r"\d+(\.\w{2,4})?", stem):
        return ""
    if re.fullmatch(r"(page|p|pg)[-_ ]?\d+\.\w{2,4}", name, re.IGNORECASE):
        return ""

    return name


def _snippet(text, limit=90):
    """
    First line of a segment, truncated for QA reports.
    """

    line = (
        str(text or "")
        .strip()
        .splitlines()[0]
        if str(text or "").strip()
        else ""
    )

    if len(line) <= limit:

        return line

    return line[: limit - 1] + "…"


def build_qa_report(
    segments,
    title="",
    filetype="epub",
):
    """
    Build a plain-text QA_REPORT section.

    Segments carrying a ``quality`` record (from the
    Chunk Quality Scorer) get an extra summary block and
    per-chunk quality lines so the reviewer sees the full
    picture alongside the engine markers.
    """

    segments = segments or []

    flagged = [
        segment
        for segment in segments
        if segment["flagged"]
    ]

    has_quality = any(
        segment.get("quality")
        for segment in segments
    )

    quality_segments = [
        segment
        for segment in segments
        if segment.get("quality")
    ]

    lines = []

    lines.append("QA_REPORT")
    lines.append("=" * 60)
    lines.append(f"book       : {title}")
    lines.append(f"format     : {filetype}")
    lines.append(f"segments   : {len(segments)}")
    lines.append(f"flagged    : {len(flagged)}")

    if has_quality:

        composites = [
            float(segment["quality"]["composite"])
            for segment in quality_segments
        ]
        quality_flagged = sum(
            1
            for segment in quality_segments
            if segment["quality"]["flag_reasons"]
        )
        lines.append(
            f"quality    : {len(quality_segments)} "
            f"scored (avg {sum(composites)/len(composites):.2f}, "
            f"{quality_flagged} flagged)"
        )

    lines.append("")

    if not flagged:

        lines.append("No flagged segments.")
        lines.append("")

        return "\n".join(lines)

    lines.append("Flagged segments:")
    lines.append("")

    for index, segment in enumerate(
        flagged,
        1,
    ):

        quality = segment.get("quality") or {}
        quality_reasons = quality.get("flag_reasons") or []

        if segment["notes"]:
            markers = ", ".join(segment["notes"])
        elif quality_reasons:
            markers = ", ".join(quality_reasons)
        else:
            markers = "boundary"

        lines.append(
            f"{index}. {segment['id']} "
            f"({chapter_title(segment['chapter'])})"
        )

        lines.append(
            f"   marker : {markers}"
        )

        if quality:
            lines.append(
                f"   quality: composite {quality['composite']:.2f} — "
                f"{', '.join(quality_reasons) or 'ok'}"
            )

        lines.append(
            f"   source : {_snippet(segment['source'])}"
        )

        lines.append(
            f"   target : {_snippet(segment['target'])}"
        )

        lines.append("")

    return "\n".join(lines)
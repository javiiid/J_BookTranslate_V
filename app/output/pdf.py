# ============================================================
# app/output/pdf.py
# ============================================================
"""
OUTPUT: BILINGUAL_PDF / TRANSLATED_PDF

PDF documents generated from the translated segments with PyMuPDF.

    - translated_pdf:  translation only
    - bilingual_pdf:   original text next to the translation

Flagged segments (QA markers) are painted on a yellow background
so reviewers can spot them immediately.
"""

from __future__ import annotations

from pathlib import Path

import fitz

from app.output.docx import RTL_LANGUAGES
from app.output.typography import text_direction

PAGE_WIDTH = 595  # A4 points
PAGE_HEIGHT = 842
MARGIN = 50

BODY_RECT = fitz.Rect(
    MARGIN,
    MARGIN,
    PAGE_WIDTH - MARGIN,
    PAGE_HEIGHT - MARGIN,
)


def _escaped(value):
    """
    HTML-escape text for the MuPDF HTML renderer.
    """

    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _direction(text, fallback):
    """
    Per-paragraph direction so mixed books stay readable: an Arabic
    original is RTL even when the target language is English, and an
    English quote stays LTR inside a Persian translation.
    """

    return text_direction(str(text or ""), fallback)


# NOTE on fonts: MuPDF renders this path with its bundled Noto Naskh
# Arabic / Charis SIL faces -- deliberately, not Vazirmatn. Two
# measured reasons:
#
# 1. The WOFF2 files in ``app/library/`` cannot be used directly
#    (MuPDF's FreeType reports "unknown file format"), and the
#    fontTools-decompiled TTFs come back with corrupt glyph maps:
#    ت extracts as U+04A5, پ as U+0423. Readers would copy broken
#    text. (DOCX and the Playwright PDF path keep Vazirmatn; they
#    embed through fontTools/CSS where the mapping stays correct.)
# 2. Bold -- real face or synthetic -- corrupts Arabic-script
#    extraction the same way, so headings are sized up, never bolded.
#
# The remaining quirk (ل extracts as U+01C1/U+01C2, ZWNJ is dropped)
# predates this writer: the old one-page-per-segment output requested
# Tahoma but MuPDF embedded the same bundled Noto subset, byte for
# byte the same behavior. Glyphs render correctly; only PyMuPDF's
# own extraction is lossy there.
_CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.7; }
h1 { font-size: 20pt; margin-bottom: 12pt; }
p.label { font-size: 8pt; color: #888888; margin-bottom: 0; }
hr { border: none; border-top: 0.5pt solid #cccccc; margin: 8pt 0; }
"""


def _run_story(html, path, title=""):
    """
    Flow ``html`` across as many A4 pages as it needs and set the
    document title metadata. One story, not one page per segment:
    a 300-chunk book used to come out as 300 mostly-empty pages.

    The throwaway file lives in the system temp dir (never next to
    the output), and MuPDF objects are released explicitly: on
    Windows an open handle makes the cleanup unlink fail and the
    temp file would be left behind otherwise.
    """

    import gc
    import tempfile as _tempfile
    import uuid as _uuid

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    story = fitz.Story(html=html, user_css=_CSS)

    tmp = (
        Path(_tempfile.gettempdir())
        / f"kalima-{_uuid.uuid4().hex}.story.pdf"
    )
    writer = fitz.DocumentWriter(str(tmp))
    mediabox = fitz.Rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT)
    device = None
    try:
        while True:
            device = writer.begin_page(mediabox)
            more, _ = story.place(BODY_RECT)
            story.draw(device)
            writer.end_page()
            if not more:
                break
    finally:
        # close() flushes the file; the dels + gc release the
        # Windows handle so the cleanup unlink below succeeds.
        writer.close()
        del device
        del writer
        del story
        gc.collect()

    document = fitz.open(str(tmp))
    try:
        if title:
            metadata = dict(document.metadata or {})
            metadata["title"] = str(title)
            document.set_metadata(metadata)
        document.save(str(path), garbage=4, deflate=True)
    finally:
        document.close()
        del document
        gc.collect()
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass

    return path


def _title_html(title, rtl):
    if not str(title or "").strip():
        return ""
    direction = "rtl" if rtl else "ltr"
    return f'<h1 dir="{direction}">{_escaped(str(title).strip())}</h1>'


def _para_html(text, direction, flagged=False):
    background = (
        ' style="background-color:#fff59d;"'
        if flagged
        else ""
    )
    direction = "rtl" if direction == "rtl" else "ltr"
    return (
        f'<p dir="{direction}"{background}>'
        f"{_escaped(text)}"
        "</p>"
    )


def write_translated_pdf(
    segments,
    path,
    title="Translated book",
    to_lang="FA",
):
    """
    Write the TRANSLATED_PDF output as flowing text.

    Segments share pages: a new page starts only when the current
    one is full, so a 300-chunk book is a book, not 300 single
    paragraphs each on their own page.
    """

    default_rtl = str(to_lang).upper() in RTL_LANGUAGES

    parts = [_title_html(title, default_rtl)]

    for segment in segments or []:
        segment = segment or {}
        target = segment.get("target", "")
        parts.append(
            _para_html(
                target,
                _direction(target, "rtl" if default_rtl else "ltr"),
                flagged=bool(segment.get("flagged")),
            )
        )

    return _run_story("".join(parts), path, title=title)


def write_bilingual_pdf(
    segments,
    path,
    title="Translated book",
    to_lang="FA",
):
    """
    Write the BILINGUAL_PDF output.

    Original and translation follow each other full-width, pair by
    pair, flowing across pages with nothing lost no matter how long
    the book is.

    ## Why stacked and not side-by-side

    The first version laid each pair out as one row of a two-column
    table. Measured on an 8-pair book: 9 pages, 309 of 480 source
    paragraphs missing. MuPDF's story engine does not split an
    oversized table row across pages -- the overflow is silently
    clipped. Real chunks routinely exceed a page in a half-width
    column, so side-by-side tables lose text by design here.
    Direction is still detected per paragraph, so an Arabic original
    stays RTL even when the target language is English.
    """

    default_rtl = str(to_lang).upper() in RTL_LANGUAGES

    parts = [_title_html(title, default_rtl)]

    for segment in segments or []:
        segment = segment or {}
        source = segment.get("source", "")
        target = segment.get("target", "")
        flagged = bool(segment.get("flagged"))
        source_dir = _direction(source, "ltr")
        target_dir = _direction(
            target, "rtl" if default_rtl else "ltr"
        )
        highlight = (
            ' style="background-color:#fff59d;"'
            if flagged
            else ""
        )
        parts.append(
            f'<p class="label" dir="{source_dir}">ORIGINAL</p>'
            f'<p dir="{source_dir}">{_escaped(source)}</p>'
            f'<p class="label" dir="{target_dir}">TRANSLATION</p>'
            f'<p dir="{target_dir}"{highlight}>{_escaped(target)}</p>'
            "<hr/>"
        )

    return _run_story("".join(parts), path, title=title)
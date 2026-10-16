# ============================================================
# app/output/pdf.py
# ============================================================
"""
OUTPUT: TRANSLATED_PDF / BILINGUAL_PDF / MOBILE_PDF

PDF documents generated from the translated segments with PyMuPDF.

    - translated_pdf:  translation only, A4
    - bilingual_pdf:   original + translation, stacked pairs, A4
    - mobile_pdf:      translation only, narrow phone-width page

Flagged segments (QA markers) are painted on a yellow background
so reviewers can spot them immediately.
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz

from app.output.docx import RTL_LANGUAGES
from app.output.segments import chapter_title
from app.output.typography import text_direction

PAGE_WIDTH = 595  # A4 points
PAGE_HEIGHT = 842
MARGIN = 50

# Phone-width page: at fit-to-width on a ~360-430px phone screen the
# 13pt body below reads without pinching. Same engine and fonts as
# the A4 outputs, only geometry and type scale change.
MOBILE_WIDTH = 360
MOBILE_HEIGHT = 640
MOBILE_MARGIN = 36

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


#: Source file names that are always front matter, never body.
#: Deliberately narrow: ``foreword``/``preface``/``introduction`` are
#: NOT here -- the user asked numbering to start at the preface, so
#: they count as body.
_FRONT_FILENAMES = frozenset({
    "cover",
    "titlepage",
    "title-page",
    "toc",
    "contents",
    "nav",
    "frontmatter",
    "front-matter",
    "dedication",
    "copyright",
})

#: Front-matter lead-ins, matched against the first 80 characters of
#: the rendered text (normalized: casefolded, ZWNJ removed). A table
#: of contents without its heading word is missed and numbering then
#: starts at page one -- an accepted fallback, documented in
#: ``_body_start_index``.
_FRONT_TEXT = (
    "فهرست",
    "شناسنامه",
    "تقدیم",
    "سپاسگزاری",
    "درباره نویسنده",
    "یادداشت ناشر",
    "contents",
    "table of contents",
    "dedication",
    "acknowledgment",
    "about the author",
    "copyright",
    "all rights reserved",
    "published by",
    "inhaltsverzeichnis",
    "widmung",
    "table des matieres",
    "sommaire",
    "dedicace",
)

_WS_RE = re.compile(r"\s+")


def _normalize_lead(value):
    """
    Lowercase, de-joined comparison form for front-matter matching.
    """

    text = _WS_RE.sub(
        " ", str(value or "").casefold().replace("‌", "")
    )

    return text.strip()


def _is_front(segment):
    """
    Whether a segment is front matter (cover/TOC/dedication pages).

    Checks the source file name first -- ``toc.xhtml`` needs no
    further evidence -- then the opening words of the rendered text.
    """

    segment = segment or {}

    stem = (
        Path(str(segment.get("chapter") or "")).stem.lower()
    )

    if stem in _FRONT_FILENAMES:
        return True

    lead = _normalize_lead(
        str(segment.get("target") or segment.get("source") or "")[:80]
    )

    return any(pattern in lead for pattern in _FRONT_TEXT)


def _body_start_index(segments):
    """
    Position of the first body segment; numbering starts there.

    Anything before it (title page, table of contents, dedication)
    renders without a page number. When nothing is recognized as
    front matter the answer is 0 and numbering starts at page one --
    including the common case where the title shares its page with
    real content. Back-matter misclassification is harmless: only the
    first body position is ever used.
    """

    for pos, segment in enumerate(segments or []):
        if not _is_front(segment):
            return pos

    return 0


#: Forced page break: MuPDF honors it on an empty block.
_BREAK = '<div style="page-break-before: always"></div>'


def _chapter_breaks(segments, filetype):
    """
    Positions before which a page break goes: each EPUB chapter
    starts on a fresh page.

    Only EPUB sources have real chapters. PDF "chapters" are page
    files (``page_0003.html``) and SRT ones are subtitle blocks --
    breaking there would shred the flow, so other filetypes never
    break. Within EPUB, a change to a chapter without a real name
    (``chapter_title`` empty for generated page files) also flows.
    """

    if str(filetype or "").lower() != "epub":
        return set()

    breaks = set()
    prev = None

    for pos, segment in enumerate(segments or []):
        chapter = (segment or {}).get("chapter", "")

        if prev is None:
            prev = chapter
            continue

        if chapter != prev:
            prev = chapter

            if chapter and chapter_title(chapter):
                breaks.add(pos)

    return breaks


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

# Same face stack as _CSS (see the font NOTE above: no Vazirmatn, no
# bold for Arabic script). Larger body + looser leading because a
# 360pt line holds fewer words and Persian joining needs air.
_MOBILE_CSS = """
body { font-family: sans-serif; font-size: 13pt; line-height: 1.9; }
h1 { font-size: 22pt; margin-bottom: 14pt; }
p.label { font-size: 9pt; color: #888888; margin-bottom: 0; }
hr { border: none; border-top: 0.5pt solid #cccccc; margin: 10pt 0; }
"""


def _run_story(
    html,
    path,
    title="",
    page_width=PAGE_WIDTH,
    page_height=PAGE_HEIGHT,
    margin=MARGIN,
    css=_CSS,
    body_id="body-start",
):
    """
    Flow ``html`` across as many pages as it needs, number the body
    pages, and set the document title metadata. One story, not one
    page per segment: a 300-chunk book used to come out as 300
    mostly-empty pages.

    Page numbers start at 1 on the page where the ``body_id``
    element lands (found via ``Story.element_positions`` during
    layout); earlier pages -- title, table of contents -- carry no
    footer. Unknown position falls back to numbering from page one.

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

    body = fitz.Rect(
        margin, margin, page_width - margin, page_height - margin
    )

    story = fitz.Story(html=html, user_css=css)

    first_pages: dict[str, int] = {}
    current = [0]

    def record(position):
        # Must never raise: a callback exception aborts the layout
        # and the whole export with it.
        try:
            if (
                position.id
                and position.open_close == 1
                and position.id not in first_pages
            ):
                first_pages[position.id] = current[0]
        except Exception:
            pass

    tmp = (
        Path(_tempfile.gettempdir())
        / f"kalima-{_uuid.uuid4().hex}.story.pdf"
    )
    writer = fitz.DocumentWriter(str(tmp))
    mediabox = fitz.Rect(0, 0, page_width, page_height)
    device = None
    try:
        while True:
            device = writer.begin_page(mediabox)
            more, _ = story.place(body)
            try:
                story.element_positions(record)
            except Exception:
                pass
            story.draw(device)
            writer.end_page()
            current[0] += 1
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

    body_page = first_pages.get(body_id, 0)

    document = fitz.open(str(tmp))
    try:
        if title:
            metadata = dict(document.metadata or {})
            metadata["title"] = str(title)
            document.set_metadata(metadata)
        footer = fitz.Rect(
            margin,
            page_height - margin + 10,
            page_width - margin,
            page_height - 10,
        )
        for index in range(body_page, len(document)):
            document[index].insert_textbox(
                footer,
                str(index - body_page + 1),
                fontsize=9,
                fontname="helv",
                align=1,
            )
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


def _para_html(text, direction, flagged=False, seg_id=None):
    background = (
        ' style="background-color:#fff59d;"'
        if flagged
        else ""
    )
    direction = "rtl" if direction == "rtl" else "ltr"
    anchor = f' id="{seg_id}"' if seg_id else ""
    return (
        f'<p{anchor} dir="{direction}"{background}>'
        f"{_escaped(text)}"
        "</p>"
    )


def write_translated_pdf(
    segments,
    path,
    title="Translated book",
    to_lang="FA",
    filetype="epub",
):
    """
    Write the TRANSLATED_PDF output as flowing text.

    Segments share pages: a new page starts only when the current
    one is full, so a 300-chunk book is a book, not 300 single
    paragraphs each on their own page. Each EPUB chapter still
    starts on a fresh page. Body pages carry footer numbers from
    1; front matter (title, contents) is unnumbered.
    """

    default_rtl = str(to_lang).upper() in RTL_LANGUAGES

    items = list(segments or [])
    body_idx = _body_start_index(items)
    breaks = _chapter_breaks(items, filetype)

    parts = [_title_html(title, default_rtl)]

    for pos, segment in enumerate(items):
        if pos in breaks:
            parts.append(_BREAK)
        segment = segment or {}
        target = segment.get("target", "")
        parts.append(
            _para_html(
                target,
                _direction(target, "rtl" if default_rtl else "ltr"),
                flagged=bool(segment.get("flagged")),
                seg_id="body-start" if pos == body_idx else None,
            )
        )

    return _run_story("".join(parts), path, title=title)


def write_mobile_pdf(
    segments,
    path,
    title="Translated book",
    to_lang="FA",
    filetype="epub",
):
    """
    Write the MOBILE_PDF output: translation only on a narrow
    phone-width page (360pt) with larger type, so it reads
    fit-to-width on a phone without pinching.

    Same content, fonts and direction handling as TRANSLATED_PDF;
    only geometry and type scale differ. Numbered like the A4
    outputs: body pages from 1, front matter unnumbered.
    """

    default_rtl = str(to_lang).upper() in RTL_LANGUAGES

    items = list(segments or [])
    body_idx = _body_start_index(items)
    breaks = _chapter_breaks(items, filetype)

    parts = [_title_html(title, default_rtl)]

    for pos, segment in enumerate(items):
        if pos in breaks:
            parts.append(_BREAK)
        segment = segment or {}
        target = segment.get("target", "")
        parts.append(
            _para_html(
                target,
                _direction(target, "rtl" if default_rtl else "ltr"),
                flagged=bool(segment.get("flagged")),
                seg_id="body-start" if pos == body_idx else None,
            )
        )

    return _run_story(
        "".join(parts),
        path,
        title=title,
        page_width=MOBILE_WIDTH,
        page_height=MOBILE_HEIGHT,
        margin=MOBILE_MARGIN,
        css=_MOBILE_CSS,
    )


def write_bilingual_pdf(
    segments,
    path,
    title="Translated book",
    to_lang="FA",
    filetype="epub",
):
    """
    Write the BILINGUAL_PDF output.

    Original and translation follow each other full-width, pair by
    pair, flowing across pages with nothing lost no matter how long
    the book is. Each EPUB chapter starts on a fresh page.

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

    items = list(segments or [])
    body_idx = _body_start_index(items)
    breaks = _chapter_breaks(items, filetype)

    parts = [_title_html(title, default_rtl)]

    for pos, segment in enumerate(items):
        if pos in breaks:
            parts.append(_BREAK)
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
        anchor = ' id="body-start"' if pos == body_idx else ""
        parts.append(
            f'<p class="label"{anchor} dir="{source_dir}">ORIGINAL</p>'
            f'<p dir="{source_dir}">{_escaped(source)}</p>'
            f'<p class="label" dir="{target_dir}">TRANSLATION</p>'
            f'<p dir="{target_dir}"{highlight}>{_escaped(target)}</p>'
            "<hr/>"
        )

    return _run_story("".join(parts), path, title=title)
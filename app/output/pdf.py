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

from app.pipeline.pdf_handler import PDFHandler

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


def _segment_html(
    text,
    flagged=False,
    rtl=True,
):
    """
    Wrap translation text in a minimal HTML layout.
    """

    direction = "rtl" if rtl else "ltr"

    background = (
        ' style="background-color:#fff59d;"'
        if flagged
        else ""
    )

    return (
        f'<div dir="{direction}" '
        'style="font-family:Tahoma;font-size:11px;">'
        f'<p{background}>{_escaped(text)}</p>'
        "</div>"
    )


def _insert_safe(page, rect, html):
    """
    Insert HTML, falling back to plain text like the PDF pipeline.
    """

    try:

        return PDFHandler.insert_htmlbox_safe(
            page,
            rect,
            html,
        )

    except Exception as exc:

        # Never fail the whole export because one segment could not
        # be rendered; emit the readable text instead.
        print(
            f"PDF fallback for segment: {exc} "
            "[output.pdf]"
        )

        plain = (
            str(html)
            .replace("<p>", "\n")
            .replace("</p>", "\n")
        )

        return page.insert_textbox(
            rect,
            plain,
            fontsize=10,
            fontname="helv",
        )


def write_translated_pdf(
    segments,
    path,
    title="Translated book",
    to_lang="FA",
):
    """
    Write the TRANSLATED_PDF output (one page per segment).
    """

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rtl = str(to_lang).upper() in {
        "FA",
        "AR",
        "UR",
        "HE",
    }

    document = fitz.open()

    for segment in segments or []:

        page = document.new_page(
            width=PAGE_WIDTH,
            height=PAGE_HEIGHT,
        )

        _insert_safe(
            page,
            BODY_RECT,
            _segment_html(
                segment["target"],
                flagged=bool(segment["flagged"]),
                rtl=rtl,
            ),
        )

    document.save(path)

    document.close()

    return path


def write_bilingual_pdf(
    segments,
    path,
    title="Translated book",
    to_lang="FA",
):
    """
    Write the BILINGUAL_PDF output.

    Each page shows the original text on the left and the
    translation on the right.
    """

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rtl = str(to_lang).upper() in {
        "FA",
        "AR",
        "UR",
        "HE",
    }

    half = (PAGE_WIDTH - 2 * MARGIN - 20) / 2

    original_rect = fitz.Rect(
        MARGIN,
        MARGIN,
        MARGIN + half,
        PAGE_HEIGHT - MARGIN,
    )

    translated_rect = fitz.Rect(
        PAGE_WIDTH - MARGIN - half,
        MARGIN,
        PAGE_WIDTH - MARGIN,
        PAGE_HEIGHT - MARGIN,
    )

    document = fitz.open()

    for segment in segments or []:

        page = document.new_page(
            width=PAGE_WIDTH,
            height=PAGE_HEIGHT,
        )

        _insert_safe(
            page,
            original_rect,
            _segment_html(
                segment["source"],
                rtl=False,
            ),
        )

        _insert_safe(
            page,
            translated_rect,
            _segment_html(
                segment["target"],
                flagged=bool(segment["flagged"]),
                rtl=rtl,
            ),
        )

    document.save(path)

    document.close()

    return path
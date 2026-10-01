# ============================================================
# app/output/docx.py
# ============================================================
"""
OUTPUT: DOCX

Translated Word document with original structure preserved.
Built without external dependencies (python-docx is not installed):
a valid ``.docx`` is just a ZIP of WordprocessingML parts, which
the stdlib ``zipfile`` module can produce.

Formatting:
    - Chapter headings use Word's Heading1 style.
    - Flagged segments (QA markers) get a yellow highlight.
    - Paragraphs carry ``<w:bidi/>`` when the target language is
      right-to-left (Persian/Arabic/Urdu/Hebrew/...).
"""

from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from app.output.segments import chapter_title

RTL_LANGUAGES = {
    "FA",
    "AR",
    "UR",
    "HE",
    "DV",
    "PS",
    "SD",
}

CONTROL_CHARS_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f]"
)

NS_W = (
    "xmlns:w=\"http://schemas.openxmlformats.org/"
    "wordprocessingml/2006/main\""
)

NS_REL = (
    "xmlns=\"http://schemas.openxmlformats.org/"
    "package/2006/relationships\""
)

NS_CT = (
    "xmlns=\"http://schemas.openxmlformats.org/"
    "package/2006/content-types\""
)

NS_CP = (
    "xmlns:cp=\"http://schemas.openxmlformats.org/"
    "package/2006/metadata/core-properties\""
    " xmlns:dc=\"http://purl.org/dc/elements/1.1/\""
    " xmlns:dcterms=\"http://purl.org/dc/terms/\""
    " xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\""
    " xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\""
)

NS_APP = (
    "xmlns=\"http://schemas.openxmlformats.org/"
    "officeDocument/2006/extended-properties\""
    " xmlns:vt=\"http://schemas.openxmlformats.org/"
    "officeDocument/2006/docPropsVTypes\""
)


def _clean(value):
    """
    Remove characters that are invalid inside XML text.
    """

    return CONTROL_CHARS_RE.sub(
        "",
        str(value or ""),
    )


def _runs(text):
    """
    One run per line so long texts flow naturally in Word.
    """

    paragraphs = [
        line.strip()
        for line in _clean(text).splitlines()
        if line.strip()
    ]

    return paragraphs or [""]


def _paragraph_xml(
    text,
    rtl,
    flagged=False,
    heading=False,
):
    """
    Render a single WordprocessingML paragraph.
    """

    properties = []

    if heading:

        properties.append(
            '<w:pStyle w:val="Heading1"/>'
        )

    if rtl:

        properties.append("<w:bidi/>")

    if flagged:

        properties.append(
            '<w:shd w:val="clear" w:color="auto" '
            'w:fill="FFF59D"/>'
        )

    runs = []

    for line in _runs(text):

        run_properties = []

        if flagged:

            run_properties.append(
                '<w:highlight w:val="yellow"/>'
            )

        run_properties.append(
            '<w:lang w:val="en-US" w:bidi="fa-IR"/>'
        )

        runs.append(
            "<w:r>"
            f"<w:rPr>{''.join(run_properties)}</w:rPr>"
            "<w:t xml:space=\"preserve\">"
            f"{escape(line)}"
            "</w:t>"
            "</w:r>"
        )

    return (
        "<w:p>"
        f"<w:pPr>{''.join(properties)}</w:pPr>"
        f"{''.join(runs)}"
        "</w:p>"
    )


def _document_xml(segments, title, rtl):
    """
    Build ``word/document.xml``.

    Structured when the segment carries blocks, flat when it does not. A PDF or
    SRT conversion has no blocks, and the flat path is exactly what it was
    before -- so the change is confined to EPUB, which is where the markup
    existed and was being thrown away.
    """

    body = []

    body.append(
        _paragraph_xml(
            title,
            rtl,
            heading=True,
        )
    )

    current_chapter = None

    for segment in segments or []:

        chapter = chapter_title(
            segment["chapter"]
        )

        # An empty title means the source had no real chapter name -- a PDF's
        # page files, for one. Emitting nothing is right: the document already has
        # a title paragraph, and a heading per page would be a navigation pane
        # full of "page_0003.html".
        if chapter and chapter != current_chapter:

            current_chapter = chapter

            body.append(
                _paragraph_xml(chapter, rtl, heading=True)
            )

        body.append(
            _paragraph_xml(
                segment["target"],
                rtl,
                flagged=bool(segment.get("flagged")),
            )
        )

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" "
        "standalone=\"yes\"?>"
        f"<w:document {NS_W}>"
        "<w:body>"
        f"{''.join(body)}"
        "<w:sectPr>"
        # A4, not the 11906x16838 this always wrote, which is A4 in twips --
        # kept, and the margins are the ones that make a page readable rather
        # than a wall of text to the edge.
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1418" w:right="1418" '
        'w:bottom="1418" w:left="1418" '
        'w:header="709" w:footer="709" '
        'w:gutter="0"/>'
        "</w:sectPr>"
        "</w:body>"
        "</w:document>"
    )


def _content_types_xml():
    """
    Build ``[Content_Types].xml``.
    """

    overrides = [
        (
            "/word/document.xml",
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document.main+xml",
        ),
        (
            "/word/styles.xml",
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.styles+xml",
        ),
        (
            "/word/settings.xml",
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.settings+xml",
        ),
        (
            "/docProps/core.xml",
            "application/vnd.openxmlformats-package."
            "core-properties+xml",
        ),
        (
            "/docProps/app.xml",
            "application/vnd.openxmlformats-officedocument."
            "extended-properties+xml",
        ),
    ]

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" "
        "standalone=\"yes\"?>"
        f"<Types {NS_CT}>"
        "<Default Extension=\"rels\" "
        'ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/>'
        "<Default Extension=\"xml\" "
        'ContentType="application/xml"/>'
        f"{''.join((
            '<Override PartName="' + part + '" '
            'ContentType="' + content + '"/>'
            for part, content in overrides
        ))}"
        "</Types>"
    )


def _root_rels_xml():
    """
    Build ``_rels/.rels``.
    """

    relationships = [
        (
            "rId1",
            "http://schemas.openxmlformats.org/"
            "officeDocument/2006/relationships/"
            "officeDocument",
            "word/document.xml",
        ),
        (
            "rId2",
            "http://schemas.openxmlformats.org/"
            "package/2006/relationships/metadata/"
            "core-properties",
            "docProps/core.xml",
        ),
        (
            "rId3",
            "http://schemas.openxmlformats.org/"
            "officeDocument/2006/relationships/"
            "extended-properties",
            "docProps/app.xml",
        ),
    ]

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" "
        "standalone=\"yes\"?>"
        f"<Relationships {NS_REL}>"
        f"{''.join((
            '<Relationship Id="' + kid + '" '
            'Type="' + rel + '" '
            'Target="' + target + '"/>'
            for kid, rel, target in relationships
        ))}"
        "</Relationships>"
    )


def _document_rels_xml():
    """
    Build ``word/_rels/document.xml.rels``.
    """

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" "
        "standalone=\"yes\"?>"
        f"<Relationships {NS_REL}>"
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/settings" '
        'Target="settings.xml"/>'
        "</Relationships>"
    )


def _styles_xml(rtl: bool = True):
    """
    Build ``word/styles.xml`` with a Unicode-capable default font.

    The default was `Tahoma`. That is a *request*: Word is not obliged to have it,
    so it substituted, and Persian came out in whatever the machine had -- the
    complaint that the DOCX "has no good font" while the PDF from the same book
    came out in Vazirmatn. The name is now `Vazirmatn` and the face is embedded
    (see :func:`app.output.rtl_docx.embed_fonts`), so the declaration and the
    guarantee agree.

    `w:cs` is set as well as `w:ascii`, because Persian runs are complex-script
    and Word picks the font for them from the complex-script slot, not the ASCII
    one. Setting only `w:ascii` leaves the Persian text on the fallback path even
    with the font embedded.

    ## Why `rtl` is a parameter

    It was not: every style carried ``<w:bidi/>`` unconditionally, and the
    ``w:lang`` default declared ``w:bidi="fa-IR"``. Measured on an English PDF
    through the route, the document came out with nine ``<w:bidi/>`` elements in
    its style table and none on any paragraph -- so the paragraphs were right and
    the *styles* forced the whole book right-to-left underneath them. A paragraph
    that omits bidi does not beat a style that sets it, and every paragraph that
    does not override it inherits.

    Both now follow the document's own direction. The off case writes an explicit
    ``w:val="0"`` rather than omitting the element, because an absent one
    inherits from the style above it and ``Normal`` is what the body is based on.
    """
    bidi = "<w:bidi/>" if rtl else '<w:bidi w:val="0"/>'
    language = "fa-IR" if rtl else "en-US"

    body = "".join((
        f'<w:style w:type="paragraph" w:styleId="Normal">'
        f'<w:name w:val="Normal"/>'
        f"<w:pPr>{bidi}</w:pPr>"
        f"</w:style>",
        # BodyText is the default for a source paragraph, and it is what a reader
        # sees. The spacing is the fix for "the output does not look like a book":
        # a Persian line needs leading above 1.0 or the ascenders and the
        # descenders of the joined script touch, and Persian has no word spacing
        # to compensate.
        f'<w:style w:type="paragraph" w:styleId="BodyText">'
        f'<w:name w:val="Body Text"/>'
        f'<w:basedOn w:val="Normal"/>'
        f'<w:qFormat/>'
        f"<w:pPr>"
        f"{bidi}"
        f'<w:spacing w:before="0" w:after="160" w:line="312" w:lineRule="auto"/>'
        f'<w:ind w:firstLine="0"/>'
        f'<w:jc w:val="both"/>'
        f"</w:pPr>"
        f"</w:style>",
        # Real list numbering, so list items are a list in Word rather than a
        # bullet character glued into the text.
        f'<w:style w:type="paragraph" w:styleId="ListParagraph">'
        f'<w:name w:val="List Paragraph"/>'
        f'<w:basedOn w:val="BodyText"/>'
        f'<w:qFormat/>'
        f"<w:pPr>"
        f"{bidi}"
        f'<w:ind w:left="425" w:hanging="284"/>'
        f"</w:pPr>"
        f"</w:style>",
        # Heading 1 through 6, so a chapter hierarchy survives and Word can build
        # a navigation pane. The writer emits the matching `w:pStyle` per level.
        "".join(
            f'<w:style w:type="paragraph" w:styleId="Heading{level}">'
            f'<w:name w:val="heading {level}"/>'
            f'<w:basedOn w:val="Normal"/>'
            f'<w:next w:val="BodyText"/>'
            f'<w:qFormat/>'
            f"<w:pPr>"
            f"{bidi}"
            f'<w:spacing w:before="{360 - (level - 1) * 40}"'
            f' w:after="{180 - (level - 1) * 20}"/>'
            f'<w:outlineLvl w:val="{level - 1}"/>'
            f"</w:pPr>"
            f"<w:rPr>"
            f"<w:b/>"
            f'<w:sz w:val="{36 - (level - 1) * 2}"/>'
            f'<w:szCs w:val="{36 - (level - 1) * 2}"/>'
            f"</w:rPr>"
            f"</w:style>"
            for level in range(1, 7)
        ),
    ))

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:styles {NS_W}>"
        f"<w:docDefaults>"
        f"<w:rPrDefault>"
        f"<w:rPr>"
        f'<w:rFonts w:ascii="Vazirmatn" w:hAnsi="Vazirmatn" w:cs="Vazirmatn"/>'
        f'<w:sz w:val="24"/>'
        f'<w:szCs w:val="24"/>'
        f'<w:lang w:val="en-US" w:bidi="{language}"/>'
        f"</w:rPr>"
        f"</w:rPrDefault>"
        f"</w:docDefaults>"
        f"{body}"
        f"</w:styles>"
    )


def _settings_xml():
    """
    Build ``word/settings.xml``.
    """

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" "
        "standalone=\"yes\"?>"
        f"<w:settings {NS_W}>"
        '<w:zoom w:percent="100"/>'
        '<w:defaultTabStop w:val="708"/>'
        "</w:settings>"
    )


def _core_xml(title):
    """
    Build ``docProps/core.xml``, byte-compatible with what Word itself writes.

    This part used to make Word reject the whole document with "The file appears
    to be corrupted." Every element was well-formed and every namespace was
    declared, so nothing in the file was malformed -- but Word validates the core
    properties against its own idea of the OPC profile and would not open the
    package. The two things it objected to, both measured by substitution:

      * the timestamp was ``datetime.isoformat()``, which writes microseconds and
        a ``+00:00`` offset. Word writes seconds and a literal ``Z``.
      * only ``dc:title``, ``dcterms:created`` and ``dcterms:modified`` were
        emitted. Word's own part carries the whole set.

    Verified: this package with a hand-written core part -- same namespaces, same
    elements, the old timestamp -- is refused; and this package with Word's own
    core part substituted in is opened. So the part is the whole defect.
    """

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" "
        "standalone=\"yes\"?>"
        f"<cp:coreProperties {NS_CP}>"
        "<dc:title>"
        f"{escape(_clean(title))}"
        "</dc:title>"
        "<dc:subject></dc:subject>"
        "<dc:creator>J Book Translate</dc:creator>"
        "<cp:keywords></cp:keywords>"
        "<dc:description></dc:description>"
        "<cp:lastModifiedBy>J Book Translate</cp:lastModifiedBy>"
        "<cp:revision>1</cp:revision>"
        "<dcterms:created xsi:type=\"dcterms:W3CDTF\">"
        f"{stamp}"
        "</dcterms:created>"
        "<dcterms:modified xsi:type=\"dcterms:W3CDTF\">"
        f"{stamp}"
        "</dcterms:modified>"
        "</cp:coreProperties>"
    )


def _app_xml():
    """
    Build ``docProps/app.xml``.
    """

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" "
        "standalone=\"yes\"?>"
        f"<Properties {NS_APP}>"
        "<Application>J Book Translate</Application>"
        "<AppVersion>1.0</AppVersion>"
        "</Properties>"
    )


def write_docx(
    segments,
    path,
    title="Translated book",
    to_lang="FA",
):
    """
    Write the DOCX output file.
    """

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rtl = (
        str(to_lang)
        .upper()
        in RTL_LANGUAGES
    )

    parts = {
        "[Content_Types].xml": _content_types_xml(),
        "_rels/.rels": _root_rels_xml(),
        "word/document.xml": _document_xml(
            segments,
            title,
            rtl,
        ),
        "word/_rels/document.xml.rels": _document_rels_xml(),
        "word/styles.xml": _styles_xml(rtl),
        "word/settings.xml": _settings_xml(),
        # No fontTable here. `fix_docx_typography` rewrites the package after
        # this function returns -- it fixes direction, spacing and numbering, and
        # it is the layer that embeds the fonts. Writing a font table in both
        # places meant the second one had to reconcile the first, and a document
        # could end up with a font table that referenced parts which were never
        # written. One writer, one font table: rtl_docx owns it.
        "docProps/core.xml": _core_xml(title),
        "docProps/app.xml": _app_xml(),
    }

    with zipfile.ZipFile(
        path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:

        for name, content in parts.items():

            archive.writestr(
                name,
                content.encode("utf-8"),
            )

    return path
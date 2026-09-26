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

        if chapter != current_chapter:

            current_chapter = chapter

            body.append(
                _paragraph_xml(
                    chapter,
                    rtl,
                    heading=True,
                )
            )

        body.append(
            _paragraph_xml(
                segment["target"],
                rtl,
                flagged=bool(segment["flagged"]),
            )
        )

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" "
        "standalone=\"yes\"?>"
        f"<w:document {NS_W}>"
        "<w:body>"
        f"{''.join(body)}"
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" '
        'w:bottom="1440" w:left="1440" '
        'w:header="708" w:footer="708" '
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


def _styles_xml():
    """
    Build ``word/styles.xml`` with a Unicode-capable default font.
    """

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" "
        "standalone=\"yes\"?>"
        f"<w:styles {NS_W}>"
        "<w:docDefaults>"
        "<w:rPrDefault>"
        "<w:rPr>"
        '<w:rFonts w:ascii="Tahoma" w:hAnsi="Tahoma" '
        'w:cs="Tahoma"/>'
        '<w:sz w:val="22"/>'
        '<w:szCs w:val="22"/>'
        '<w:lang w:val="en-US" w:bidi="fa-IR"/>'
        "</w:rPr>"
        "</w:rPrDefault>"
        "</w:docDefaults>"
        '<w:style w:type="paragraph" w:styleId="Normal">'
        '<w:name w:val="Normal"/>'
        "<w:pPr><w:bidi/></w:pPr>"
        "</w:style>"
        '<w:style w:type="paragraph" w:styleId="Heading1">'
        '<w:name w:val="heading 1"/>'
        '<w:basedOn w:val="Normal"/>'
        "<w:pPr>"
        "<w:bidi/>"
        '<w:spacing w:before="280" w:after="140"/>'
        '<w:outlineLvl w:val="0"/>'
        "</w:pPr>"
        "<w:rPr>"
        "<w:b/>"
        '<w:sz w:val="30"/>'
        '<w:szCs w:val="30"/>'
        "</w:rPr>"
        "</w:style>"
        "</w:styles>"
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
    Build ``docProps/core.xml``.
    """

    stamp = datetime.now(timezone.utc).isoformat()

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" "
        "standalone=\"yes\"?>"
        f"<cp:coreProperties {NS_CP}>"
        "<dc:title>"
        f"{escape(_clean(title))}"
        "</dc:title>"
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
        "word/styles.xml": _styles_xml(),
        "word/settings.xml": _settings_xml(),
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
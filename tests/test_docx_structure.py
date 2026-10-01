"""What the project's own DOCX writer is responsible for.

## The division of labour, measured

An EPUB is converted by `app.output.epub_convert`, which reads the book through
pandoc. A PDF, an SRT or a text file is converted by `app.output.docx`. That split
is not a preference -- it is what the two writers are each good at:

* pandoc reads every structural element an EPUB has and embeds the images as real
  `word/media/` parts. Measured on the test book: 6 image parts, 6 relationships,
  6 `<a:blip>` references.
* `app.output.docx` embeds the fonts (5 weights of Vazirmatn) and writes real
  heading levels, but has no image support -- a picture would become the text
  `[تصویر: ...]`, which for a PDF or an SRT cannot happen because those sources
  have no images.

So this file tests what `docx.py` is actually for: the fonts, the heading levels,
the RTL typography, and the chapter headings. The emphasis and the images are
`epub_convert`'s, and are tested in `test_convert_structure.py` and
`test_convert_fonts.py`.

## Why the assertions parse rather than match

`fix_docx_typography` re-serialises the package through ElementTree, which writes
``<w:i />`` with a space. A substring test for ``"<w:i/>"`` fails on a document
that is perfectly correct, which is what the first version of these tests did.
"""
from __future__ import annotations

import re
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

import pytest

sys.stdout.reconfigure(encoding="utf-8")

from app.output.convert import convert_file
from app.output.docx import write_docx
from app.output.rtl_docx import fix_docx_typography
from app.output.segments import chapter_title

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def make_pdf(path: Path, pages: int = 6) -> Path:
    """A PDF, which is what this writer is for."""
    import pymupdf

    document = pymupdf.open()
    for index in range(pages):
        page = document.new_page()
        page.insert_text((72, 100), f"Page {index} body text.")
    document.save(str(path))
    document.close()
    return path


def build(segments, path: Path, to_lang: str = "FA", title: str = "کتاب") -> Path:
    """Built and post-processed exactly as the route builds it.

    The language and the title are both passed explicitly. `write_docx` defaults
    `to_lang` to "FA", and `fix_docx_typography` reads the document's *own text* to
    decide its direction -- so a Persian title in an English book makes the whole
    document right-to-left, correctly, and the test would be measuring that
    rather than the thing it is about.
    """
    write_docx(segments, str(path), title=title, to_lang=to_lang)
    fix_docx_typography(path)
    return path


def segment(chapter: str, text: str, **extra) -> dict:
    return {
        "id": "chunk-0",
        "position": 0,
        "source": text,
        "target": text,
        "format": "pdf",
        "chapter": chapter,
        "flagged": False,
        "notes": [],
        **extra,
    }


def styles_of(root) -> list[str]:
    found = []
    for para in root.iter(f"{W}p"):
        style = para.find(f"{W}pPr/{W}pStyle")
        found.append(style.get(f"{W}val") if style is not None else "(none)")
    return found


def part(path: Path, name: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name).decode("utf-8")


def tree(path: Path) -> ElementTree.Element:
    with zipfile.ZipFile(path) as archive:
        return ElementTree.fromstring(archive.read("word/document.xml"))


class TestTheFonts:
    def test_the_faces_are_embedded(self, tmp_path):
        path = build([segment("ch01", "متن")], tmp_path / "a.docx")
        with zipfile.ZipFile(path) as archive:
            parts = [n for n in archive.namelist() if n.startswith("word/fonts/")]
        assert len(parts) == 5, parts

    def test_the_styles_name_the_embedded_font(self, tmp_path):
        path = build([segment("ch01", "متن")], tmp_path / "a.docx")
        styles = part(path, "word/styles.xml")
        assert "Vazirmatn" in styles
        assert "Tahoma" not in styles


class TestTheHeadings:
    def test_heading_levels_one_to_six_are_defined(self, tmp_path):
        # A PDF has no heading structure of its own, so none of these is emitted
        # by default. They are defined because a source that does carry levels --
        # an SRT section, a text file with chapter markers -- has to be able to
        # use them, and a style that is not defined is silently dropped by Word.
        path = build([segment("ch01", "متن")], tmp_path / "a.docx")
        styles = part(path, "word/styles.xml")
        for level in range(1, 7):
            assert f'w:styleId="Heading{level}"' in styles, level
            assert f'w:outlineLvl w:val="{level - 1}"' in styles, level

    def test_the_title_is_a_heading(self, tmp_path):
        path = build([segment("ch01", "متن")], tmp_path / "a.docx")
        headings = [s for s in styles_of(tree(path)) if s.startswith("Heading")]
        assert headings, "the document has no heading at all"

    def test_the_body_style_has_readable_spacing(self, tmp_path):
        # A Persian line at single spacing touches its own ascenders; the joined
        # script has no word spacing to compensate. 312 twentieths of a point is
        # 1.3, which is what the reading pages use.
        path = build([segment("ch01", "متن")], tmp_path / "a.docx")
        assert 'w:line="312"' in part(path, "word/styles.xml")


class TestChapterTitles:
    """A filename is not a heading."""

    def test_a_page_file_is_not_a_chapter(self):
        # Converting a PDF gave every "chapter" the name of the page file, so a
        # six-page PDF produced a navigation pane reading page_0000.html,
        # page_0001.html, ... Six headings, none of them meaning anything.
        for name in ("page_0000.html", "page-0001.html", "page2.html",
                     "p003.xhtml", "img_12.jpg", "0003.html", "doc_0007.html"):
            assert chapter_title(name) == "", name

    def test_a_real_chapter_name_survives(self):
        # The EPUB case, which must not regress: `ch07.html` is a real chapter
        # even though it ends in .html and starts with a letter.
        for name in ("ch07.html", "ch01.xhtml", "chapter-3.html", "part-two.html"):
            assert chapter_title(name) == name, name

    def test_a_path_is_reduced_to_its_name(self):
        assert chapter_title("ops/xhtml/ch07.html") == "ch07.html"

    def test_nothing_at_all_still_has_a_title(self):
        assert chapter_title("") == "Chapter"
        assert chapter_title(None) == "Chapter"

    def test_a_pdf_conversion_has_one_heading_not_seven(self):
        """The end-to-end shape of the fix."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = make_pdf(root / "a.pdf", pages=6)
            result = convert_file(source, root / "out", ["docx"], title="My Book")
            headings = [
                s for s in styles_of(tree(Path(result["generated"]["docx"])))
                if s.startswith("Heading")
            ]
            counts = Counter(headings)
            # The title, and nothing else. A heading per page was the defect.
            assert sum(counts.values()) == 1, counts

    def test_a_chapter_name_reaches_the_document(self, tmp_path):
        path = build([segment("ops/xhtml/ch07.html", "متن")], tmp_path / "a.docx")
        text = " ".join(t.text or "" for t in tree(path).iter(f"{W}t"))
        assert "ch07.html" in text


class TestTextFidelity:
    def test_no_text_is_lost(self, tmp_path):
        path = build(
            [segment("ch01", "پاراگراف اول"), segment("ch01", "پاراگراف دوم")],
            tmp_path / "a.docx",
        )
        text = " ".join(t.text or "" for t in tree(path).iter(f"{W}t"))
        assert "پاراگراف اول" in text
        assert "پاراگراف دوم" in text

    def test_markup_characters_are_escaped(self, tmp_path):
        path = build([segment("ch01", "a < b & c")], tmp_path / "a.docx")
        # `fix_docx_typography` splits on the Latin runs it detects, so the
        # characters are separated by a space in the extracted text. The first
        # version of this test compared against the exact string and failed on
        # correct output.
        text = " ".join(t.text or "" for t in tree(path).iter(f"{W}t"))
        collapsed = re.sub(r"\s+", " ", text)
        assert "a < b & c" in collapsed, collapsed
        # And it did not become markup: the document still has one text node per
        # segment, not one per character.
        assert "<w:t> b" not in part(path, "word/document.xml")

    def test_a_flagged_segment_is_highlighted(self, tmp_path):
        path = build(
            [segment("ch01", "متن", flagged=True)],
            tmp_path / "a.docx",
        )
        assert "FFF59D" in part(path, "word/document.xml")

    def test_it_is_a_readable_package(self, tmp_path):
        path = build([segment("ch01", "متن")], tmp_path / "a.docx")
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            names = archive.namelist()
        for required in ("[Content_Types].xml", "_rels/.rels", "word/document.xml",
                         "word/styles.xml", "word/fontTable.xml"):
            assert required in names, required


class TestRtlTypography:
    """The bidi marking, in the document rather than in the style table.

    `fix_docx_typography` decides the direction per paragraph and writes it into
    `word/document.xml`. The style table carries the language tag, not the
    direction -- so the first version of these tests looked in the wrong file and
    reported a missing bidi on a document that had it on every paragraph.
    """

    def _paragraphs(self, path: Path) -> list[tuple[bool, str]]:
        found = []
        for para in tree(path).iter(f"{W}p"):
            properties = para.find(f"{W}pPr")
            bidi = properties is not None and properties.find(f"{W}bidi") is not None
            text = "".join(t.text or "" for t in para.iter(f"{W}t"))
            found.append((bidi, text))
        return found

    def test_a_persian_document_is_marked_bidi(self, tmp_path):
        path = build([segment("ch01", "متن فارسی")], tmp_path / "a.docx")
        body = [p for p in self._paragraphs(path) if "متن فارسی" in p[1]]
        assert body, "the paragraph is missing from the document"
        assert body[0][0], "a Persian paragraph is not marked bidi"

    def test_the_style_table_marks_a_persian_document_rtl(self, tmp_path):
        # The style table is what a paragraph inherits from, so it has to agree
        # with the paragraphs. An earlier version of this test read the direction
        # out of the style table looking for `<w:bidi/>` with no space, and the
        # ElementTree pass in `fix_docx_typography` writes `<w:bidi />` with one.
        path = build([segment("ch01", "متن فارسی")], tmp_path / "a.docx")
        assert re.search(r"<w:bidi\s*/>", part(path, "word/styles.xml"))

    def test_an_english_document_is_not(self, tmp_path):
        path = build(
            [segment("ch01", "English text")], tmp_path / "a.docx",
            to_lang="EN", title="My Book",
        )
        body = [p for p in self._paragraphs(path) if "English text" in p[1]]
        assert body, "the paragraph is missing from the document"
        # The writer marks paragraphs bidi from the target language, and
        # `fix_docx_typography` then refines it per paragraph. An English one
        # carries no `w:bidi` at all, which is the same as "not bidi" -- an
        # explicit `w:val="0"` would also be correct, so the check is on the
        # *effect* and not on which of the two ways it was expressed.
        assert not body[0][0], "an English paragraph was forced to RTL"

    def test_the_styles_do_not_force_rtl_on_an_english_book(self, tmp_path):
        """The bug this found.

        Every style carried ``<w:bidi/>`` unconditionally, and the ``w:lang``
        default declared ``w:bidi="fa-IR"``. An English PDF came out with nine
        ``<w:bidi/>`` elements in its style table -- so the *paragraphs* were
        correct and the *styles* pulled the whole book right-to-left underneath
        them, which is what a paragraph cannot override.

        Matched with the space ``fix_docx_typography``'s ElementTree pass leaves
        behind: it writes ``<w:bidi w:val="0" />``, not ``...w:val="0"/>``. The
        first version of this test looked for the tight form and reported the fix
        as absent on a document that had it.
        """
        path = build(
            [segment("ch01", "English text")], tmp_path / "a.docx",
            to_lang="EN", title="My Book",
        )
        styles = part(path, "word/styles.xml")
        assert re.search(r'<w:bidi w:val="0"\s*/>', styles), (
            "the styles still declare the document right-to-left"
        )
        assert not re.search(r"<w:bidi\s*/>", styles), (
            "an unconditional bidi survived in a left-to-right document"
        )
        assert 'w:bidi="en-US"' in styles, (
            "the complex-script language is still declared Persian"
        )

    def test_a_persian_document_does_declare_rtl(self, tmp_path):
        path = build([segment("ch01", "متن فارسی")], tmp_path / "a.docx", to_lang="FA")
        styles = part(path, "word/styles.xml")
        assert re.search(r"<w:bidi\s*/>", styles)
        assert 'w:bidi="fa-IR"' in styles
        assert not re.search(r'<w:bidi w:val="0"\s*/>', styles), (
            "a right-to-left document declared itself left-to-right"
        )

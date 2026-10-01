"""Does the emphasis survive the conversion route?

## The bug

An EPUB conversion builds its DOCX through `pypandoc`, not through
`app.output.docx`. Pandoc reads `<i>`, `<b>` and `<em>`. It does not read
`<span class="txit">` -- a class, not a tag -- so every run of interior voice in
a generation of e-books arrived as plain text.

Measured through the real route on a real book, before the fix:

    italic runs    0      (37 <span class="txit"> in the source)
    smallCaps runs 10     (this one pandoc happens to keep)
    headings       4      (kept -- these are real <h2> tags)

So only one of the three structure kinds was being lost, and only for the
inline emphasis. That is worth stating precisely, because "the structure is not
preserved" sounds like everything was flattened and almost nothing was.

## Why this was not found earlier

`app.output.docx` writes a correct document with the emphasis intact, and there
are tests for it. The conversion route does not use that writer for an EPUB. A
test on the writer passes while the product is broken -- the same shape as the
font bug, in the same feature, one layer further along.
"""
from __future__ import annotations

import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

import pytest

sys.stdout.reconfigure(encoding="utf-8")

from app.output.convert import convert_file

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

HTML = (
    "<h1>فصل یک</h1>"
    '<p>بابی گفت <span class="txit">فکر می‌کنم</span> بله.</p>'
    '<p>مارگارت کی. ام<span class="smallcaps">س</span>الری</p>'
    '<p>او <b>فریاد</b> زد و <span class="txit">دوباره</span> ساکت شد.</p>'
    '<p>توجه: <span class="txit">این مهم</span> است.</p>'
)


def make_epub(path: Path) -> Path:
    import io

    opf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
        'unique-identifier="id"><metadata '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:title>کتاب</dc:title><dc:identifier id="id">x</dc:identifier>'
        '<dc:language>fa</dc:language></metadata>'
        '<manifest><item id="c1" href="ch1.xhtml" '
        'media-type="application/xhtml+xml"/></manifest>'
        '<spine><itemref idref="c1"/></spine></package>'
    )
    container = (
        '<?xml version="1.0"?>'
        '<container version="1.0" '
        'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
        '<rootfile full-path="OEBPS/book.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/book.opf", opf)
        archive.writestr("OEBPS/ch1.xhtml", f"<html><body>{HTML}</body></html>")
    path.write_bytes(buffer.getvalue())
    return path


def runs_with(root, flag: str) -> list[str]:
    found = []
    for run in root.iter(f"{W}r"):
        properties = run.find(f"{W}rPr")
        if properties is None or properties.find(f"{W}{flag}") is None:
            continue
        found.append("".join(t.text or "" for t in run.iter(f"{W}t")))
    return found


def italic_text(root) -> str:
    """Every italic run, concatenated.

    Not the run list. Pandoc splits one emphasised span across several runs --
    the markup boundary itself becomes a run -- so asserting that a run contains
    a phrase fails on correct output. The property that matters is "this text is
    italic somewhere", which is what the concatenation expresses.
    """
    return "".join(runs_with(root, "i"))


def document(path: Path) -> ElementTree.Element:
    with zipfile.ZipFile(path) as archive:
        return ElementTree.fromstring(archive.read("word/document.xml"))


@pytest.fixture(scope="module")
def docx(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("route")
    book = make_epub(root / "book.epub")
    result = convert_file(book, root / "out", ["docx"], title="کتاب")
    return Path(result["generated"]["docx"])


@pytest.fixture(scope="module")
def markdown(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("route-md")
    book = make_epub(root / "book.epub")
    result = convert_file(book, root / "out", ["markdown"], title="کتاب")
    return Path(result["generated"]["markdown"])


class TestTheRoute:
    def test_the_italic_runs_survive(self, docx):
        italic = italic_text(document(docx))
        assert "فکر می‌کنم" in italic, (
            "the interior voice was flattened; pandoc does not read a class"
        )
        # Every emphasis span in the source, not just the first.
        for phrase in ("دوباره", "این مهم"):
            assert phrase in italic, (phrase, italic)

    def test_the_emphasis_does_not_leak_onto_the_prose(self, docx):
        # A whole-paragraph italic would take the surrounding prose with it.
        italic = italic_text(document(docx))
        for phrase in ("بابی گفت", "بله", "او", "ساکت شد", "است"):
            assert phrase not in italic, f"the emphasis leaked onto {phrase!r}: {italic!r}"

    def test_the_bold_survives_too(self, docx):
        bold = runs_with(document(docx), "b")
        assert any("فریاد" in text for text in bold), bold

    def test_the_smallcaps_survives(self, docx):
        assert runs_with(document(docx), "smallCaps")

    def test_the_headings_survive(self, docx):
        styles = []
        for para in document(docx).iter(f"{W}p"):
            style = para.find(f"{W}pPr/{W}pStyle")
            styles.append(style.get(f"{W}val") if style is not None else "")
        assert any(s.startswith("Heading") for s in styles), styles

    def test_no_text_is_lost(self, docx):
        text = " ".join(t.text or "" for t in document(docx).iter(f"{W}t"))
        for phrase in ("فصل یک", "بابی گفت", "فکر می‌کنم", "مارگارت",
                       "فریاد", "دوباره", "توجه"):
            assert phrase in text, phrase


class TestTheMarkdownOutput:
    def test_it_is_emphasised(self, markdown):
        """The same class problem, the same reader -- so the fix has to cover it.

        Pandoc writes real markdown emphasis once the markup is well formed:
        ``*فکر می‌کنم*``. Two earlier versions of this assertion failed for
        opposite reasons -- one looked for ``<i>`` (which pandoc emits only when
        the span is malformed), the other for ``_text_`` (which is not the
        delimiter pandoc chooses). Checking for *any* emphasis delimiter around
        the phrase is the property; the exact character is pandoc's business.
        """
        text = markdown.read_text(encoding="utf-8")
        emphasised = [
            delimiter + "فکر می‌کنم" + delimiter
            for delimiter in ("*", "_")
        ]
        assert any(form in text for form in emphasised), (
            f"no emphasis in the markdown:\n{text[:400]}"
        )
        # Every emphasis span, not just the first.
        for phrase in ("دوباره", "این مهم"):
            assert any(
                f"{d}{phrase}{d}" in text for d in ("*", "_")
            ), (phrase, text[:400])

    def test_the_text_is_there(self, markdown):
        text = markdown.read_text(encoding="utf-8")
        for phrase in ("فصل یک", "بابی گفت", "فکر می‌کنم", "دوباره", "این مهم"):
            assert phrase in text, phrase


class TestTheRewriteItself:
    """`_normalise_emphasis` is the piece that does the work."""

    def test_it_turns_a_known_class_into_a_tag(self, tmp_path):
        from app.output.epub_convert import _normalise_emphasis

        book = make_epub(tmp_path / "book.epub")
        result = _normalise_emphasis(book, tmp_path / "out")
        with zipfile.ZipFile(result) as archive:
            content = archive.read("OEBPS/ch1.xhtml").decode("utf-8")
        assert "<i>" in content, "the emphasis class was not rewritten"
        assert 'class="txit"' in content, "the original class should be kept too"

    def test_the_text_stays_inside_the_emphasis(self, tmp_path):
        """The bug the parser was written to avoid.

        A substitution over the *opening* tag produces
        ``<span class="txit"><i></span>text</i>``: the text is outside the
        italic, the markup is unbalanced, and pandoc drops the run -- so the
        document comes out with no emphasis at all. Three attempts at this used a
        regex; each one looked right and each one removed the thing it was
        adding.
        """
        from app.output.epub_convert import _rewrite_emphasis

        phrase = "فکر می‌کنم"
        source = f'<p>گفت <span class="txit">{phrase}</span> بله.</p>'
        rewritten, changed = _rewrite_emphasis(source)
        assert changed is True
        assert phrase in rewritten, "the text was lost"

        # Sliced around the whole phrase, not its first character. An earlier
        # version used `find` as the start index and then asserted
        # `after.startswith("</i>")`, which fails on any phrase longer than one
        # character -- including the correct output.
        start = rewritten.index(phrase)
        end = start + len(phrase)
        before = rewritten[:start]
        after = rewritten[end:]
        # The opening <i> is before the text, the closing </i> is after it.
        assert before.rstrip().endswith("<i>"), before[-40:]
        assert after.lstrip().startswith("</i>"), after[:40]
        # And the markup is balanced.
        assert rewritten.count("<i>") == rewritten.count("</i>")
        assert rewritten.count("<span") == rewritten.count("</span>")

    def test_no_text_is_lost_by_the_rewrite(self, tmp_path):
        import re as _re

        from app.output.epub_convert import _rewrite_emphasis

        source = (
            '<p>یک <span class="txit">دو</span> سه</p>'
            '<p><b>چهار</b> و <span class="smallcaps">پنج</span></p>'
        )
        rewritten, _changed = _rewrite_emphasis(source)
        for word in ("یک", "دو", "سه", "چهار", "پنج"):
            assert word in rewritten, (word, rewritten)

    def test_it_leaves_an_unknown_class_alone(self, tmp_path):
        from app.output.epub_convert import _normalise_emphasis

        opf = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
            'unique-identifier="id"><metadata '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:title>x</dc:title><dc:identifier id="id">x</dc:identifier>'
            '<dc:language>fa</dc:language></metadata>'
            '<manifest><item id="c1" href="ch1.xhtml" '
            'media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="c1"/></spine></package>'
        )
        container = (
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            '<rootfile full-path="OEBPS/book.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>'
        )
        import io

        body = '<p><span class="pagebreak">صفحه</span> و ' \
               '<span class="txit">فکر</span></p>'
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("META-INF/container.xml", container)
            archive.writestr("OEBPS/book.opf", opf)
            archive.writestr("OEBPS/ch1.xhtml", f"<html><body>{body}</body></html>")
        book = tmp_path / "unknown.epub"
        book.write_bytes(buffer.getvalue())

        result = _normalise_emphasis(book, tmp_path / "out")
        with zipfile.ZipFile(result) as archive:
            content = archive.read("OEBPS/ch1.xhtml").decode("utf-8")
        # The unknown class is untouched; the known one is still rewritten.
        assert '<span class="pagebreak">صفحه</span>' in content
        assert "<i>" in content

    def test_a_book_with_nothing_to_rewrite_is_passed_through(self, tmp_path):
        from app.output.epub_convert import _normalise_emphasis

        opf = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
            'unique-identifier="id"><metadata '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:title>x</dc:title><dc:identifier id="id">x</dc:identifier>'
            '<dc:language>en</dc:language></metadata>'
            '<manifest><item id="c1" href="ch1.xhtml" '
            'media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="c1"/></spine></package>'
        )
        container = (
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            '<rootfile full-path="OEBPS/book.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>'
        )
        import io

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("META-INF/container.xml", container)
            archive.writestr("OEBPS/book.opf", opf)
            archive.writestr("OEBPS/ch1.xhtml", "<html><body><p>Plain.</p></body></html>")
        book = tmp_path / "plain.epub"
        book.write_bytes(buffer.getvalue())

        result = _normalise_emphasis(book, tmp_path / "out")
        # Same path, not a rewritten copy: nothing changed, so nothing is copied.
        assert result == book
        assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())

    def test_the_rewritten_book_is_still_a_valid_epub(self, tmp_path):
        from app.output.epub_convert import _normalise_emphasis

        book = make_epub(tmp_path / "book.epub")
        result = _normalise_emphasis(book, tmp_path / "out")
        with zipfile.ZipFile(result) as archive:
            names = archive.namelist()
            assert names[0] == "mimetype", names[:3]
            assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
            for required in ("META-INF/container.xml", "OEBPS/book.opf"):
                assert required in names
            assert archive.testzip() is None

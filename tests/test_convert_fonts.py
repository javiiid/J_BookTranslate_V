"""The font has to reach a real EPUB conversion, not just the writer.

## Where this bug actually lived

The first attempt at this put the font embedding in `docx.py`, the function that
writes `word/document.xml`. Every test passed -- and a real conversion still came
out with no embedded font, because `convert.convert_file` calls
`fix_docx_typography` on the finished file, and that function rewrites the whole
package. Its `embed_fonts` replaced the font table this code had written.

And it only ran at all for non-EPUB sources:

    if suffix != "epub" and "docx" in result["generated"]:
        fix_docx_typography(...)

The reasoning was that an EPUB's own markup was already suitable. It is not: the
DOCX writer flattens markup to text, so an EPUB conversion needs the same
direction, spacing and font treatment as anything else. Measured on a real
three-chapter book, the DOCX came out with **0 font parts in 1.3 MB**.

So these tests go through `convert_file` with an EPUB, which is the only path
that was broken. A test on the writer alone passes while the product is broken,
which is the general shape of this project's worst bugs.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

sys.stdout.reconfigure(encoding="utf-8")

from app.output.convert import convert_file
from app.output.rtl_docx import EMBEDDED_FACES

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def make_epub(path: Path, *, rtl: bool = True) -> Path:
    """A minimal but *valid* EPUB.

    Two things this fixture had to get right, both of which made it look like a
    font bug rather than a fixture bug:

    * The container and the OPF are not optional. The chunker reads the spine, so
      a zip holding only an xhtml file produces no chunks and the conversion
      raises instead of writing a document to inspect.
    * The text is Persian by default. ``fix_docx_typography`` returns early for a
      document with no RTL in it -- correctly, since there is no direction to fix
      -- and that early return skips the font embedding. So an English fixture
      produced a document with no embedded font and the test reported the very bug
      it was written to catch.

    The English case is kept as its own test, because an LTR book should still
    get a usable font; see `test_an_english_book_still_names_a_font`.
    """
    import io

    body = (
        "<h1>فصل یک</h1>"
        '<p>بابی گفت <span class="txit">فکر می‌کنم</span> بله.</p>'
        '<p>مارگارت کی. ام<span class="smallcaps">س</span>الری</p>'
    ) if rtl else (
        "<h1>Chapter One</h1>"
        '<p>Barney said <span class="txit">I think so</span> aloud.</p>'
        "<p>MARGARET K. M<span class=\"smallcaps\">C</span>ELDERRY</p>"
    )
    opf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
        'unique-identifier="id"><metadata '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:title>{"کتاب" if rtl else "Book"}</dc:title>'
        '<dc:identifier id="id">x</dc:identifier>'
        f'<dc:language>{"fa" if rtl else "en"}</dc:language></metadata>'
        '<manifest><item id="c1" href="ch1.xhtml" '
        'media-type="application/xhtml+xml"/></manifest>'
        '<spine><itemref idref="c1"/></spine></package>'
    )
    container = (
        '<?xml version="1.0"?>'
        '<container version="1.0" '
        'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/book.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/book.opf", opf)
        archive.writestr("OEBPS/ch1.xhtml", f"<html><body>{body}</body></html>")
    path.write_bytes(buffer.getvalue())
    return path


@pytest.fixture(scope="module")
def converted(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("convert")
    book = make_epub(root / "book.epub")
    result = convert_file(book, root / "out", ["docx"], title="کتاب")
    return Path(result["generated"]["docx"])


class TestTheFontReachesAnEpubConversion:
    def test_the_font_parts_are_in_the_file(self, converted):
        with zipfile.ZipFile(converted) as archive:
            parts = [n for n in archive.namelist() if n.startswith("word/fonts/")]
        assert len(parts) == len(EMBEDDED_FACES), parts
        for name in parts:
            assert name.endswith(".odttf"), name

    def test_each_part_is_a_real_font(self, converted):
        # A DOCX font part is an obfuscated TTF, so the first four bytes are
        # noise. The check that matters is the size: a WOFF2 is about 50 KB and a
        # TTF about 123 KB, and a font part of 50 KB means the conversion was
        # never actually de-compressed -- which is what "no good font" looks like
        # from the reader's side.
        with zipfile.ZipFile(converted) as archive:
            for name in archive.namelist():
                if name.startswith("word/fonts/"):
                    size = archive.getinfo(name).file_size
                    assert size > 100_000, (name, size)

    def test_the_font_table_exists_and_names_the_font(self, converted):
        from xml.etree import ElementTree

        with zipfile.ZipFile(converted) as archive:
            assert "word/fontTable.xml" in archive.namelist()
            fonts = ElementTree.fromstring(archive.read("word/fontTable.xml"))
        names = {f.get(f"{W}name") for f in fonts.iter(f"{W}font")}
        assert "Vazirmatn" in names, names

    def test_every_face_is_marked_embedded(self, converted):
        from xml.etree import ElementTree

        with zipfile.ZipFile(converted) as archive:
            fonts = ElementTree.fromstring(archive.read("word/fontTable.xml"))
        entry = next(f for f in fonts.iter(f"{W}font") if f.get(f"{W}name") == "Vazirmatn")
        families = {f.get(f"{W}name"): f for f in fonts.iter(f"{W}font")}
        for _weight, element, family_name in EMBEDDED_FACES:
            embed = families[family_name].find(f"{W}{element}")
            assert embed is not None, (family_name, element)
            assert embed.get(f"{W}fontKey"), element
            assert embed.get(f"{R}id"), element

    def test_only_the_four_schema_slots_are_used(self, converted):
        """``CT_Font`` has exactly four embedded-font children, and no more.

        The table this replaces used ``embedMedium``, ``embedSemiBold`` and
        ``embedBlack``. None of them are in ECMA-376, and Word validates the part
        rather than ignoring what it does not recognise: the whole document came
        back as "The file appears to be corrupted". A weight the schema has no
        slot for is filed as its own family instead.
        """
        from xml.etree import ElementTree

        legal = {"embedRegular", "embedBold", "embedItalic", "embedBoldItalic"}
        with zipfile.ZipFile(converted) as archive:
            fonts = ElementTree.fromstring(archive.read("word/fontTable.xml"))
        for font in fonts.iter(f"{W}font"):
            for child in font:
                name = child.tag.replace(W, "")
                if name.startswith("embed"):
                    assert name in legal, (font.get(f"{W}name"), name)

    def test_every_relationship_points_at_a_part_that_exists(self, converted):
        from xml.etree import ElementTree

        with zipfile.ZipFile(converted) as archive:
            names = set(archive.namelist())
            rels = ElementTree.fromstring(archive.read("word/_rels/fontTable.xml.rels"))
            for rel in rels:
                if not rel.get("Type", "").endswith("/font"):
                    continue
                target = f"word/{rel.get('Target')}"
                # A relationship with no part is dropped by Word silently, which
                # is indistinguishable from no embedding at all.
                assert target in names, f"{rel.get('Id')} -> {target}"

    def test_the_content_type_declares_the_font_extension(self, converted):
        with zipfile.ZipFile(converted) as archive:
            content_types = archive.read("[Content_Types].xml").decode("utf-8")
        assert 'Extension="odttf"' in content_types
        assert "obfuscatedFont" in content_types

    def test_the_obfuscated_bytes_decode_back_to_a_font(self, converted):
        import re
        import uuid
        from xml.etree import ElementTree

        with zipfile.ZipFile(converted) as archive:
            fonts = ElementTree.fromstring(archive.read("word/fontTable.xml"))
            rels = ElementTree.fromstring(archive.read("word/_rels/fontTable.xml.rels"))
            by_id = {r.get("Id"): r.get("Target") for r in rels}

        families = {f.get(f"{W}name"): f for f in fonts.iter(f"{W}font")}
        for _weight, element, family_name in EMBEDDED_FACES:
            embed = families[family_name].find(f"{W}{element}")
            assert embed is not None, (family_name, element)
            # `w:fontKey` is an `ST_Guid`, whose pattern is the canonical GUID
            # form: braces *and* dashes. It was written as 32 bare hex digits on
            # the reasoning that the dashes were a mistake, but Word validates the
            # pattern and refuses the whole document when it does not match --
            # reporting only "The file appears to be corrupted".
            key_text = embed.get(f"{W}fontKey")
            assert re.fullmatch(
                r"\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}",
                key_text,
            ), key_text
            # The key is that GUID's bytes, reversed. The dashes are dropped only
            # here, for the XOR.
            key = uuid.UUID(key_text.strip("{}")).bytes[::-1]
            with zipfile.ZipFile(converted) as archive:
                data = bytearray(archive.read(f"word/{by_id[embed.get(f'{R}id')]}"))
            for index in range(32):
                data[index] ^= key[index % 16]
            # The TrueType signature, after de-obfuscation. If this is wrong Word
            # sees garbage and uses no font -- the exact complaint.
            assert bytes(data[:4]) == b"\x00\x01\x00\x00", (element, data[:4].hex())

    def test_the_styles_name_the_embedded_font(self, converted):
        with zipfile.ZipFile(converted) as archive:
            styles = archive.read("word/styles.xml").decode("utf-8")
        assert "Vazirmatn" in styles
        assert "Tahoma" not in styles, "the fallback is still the declared default"


class TestAnEnglishBook:
    """A Latin-script book still gets a usable font.

    `fix_docx_typography` returns early when there is no RTL text, which is
    right -- there is no direction to fix -- but the early return also skipped the
    font embedding. So an LTR conversion came out declaring a font it did not
    carry, which is the same complaint from a reader who cannot read the
    characters.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def english(cls, tmp_path_factory):
        root = tmp_path_factory.mktemp("english")
        book = make_epub(root / "book.epub", rtl=False)
        result = convert_file(book, root / "out", ["docx"], title="Book")
        return Path(result["generated"]["docx"])

    def test_the_font_is_still_named(self, english):
        with zipfile.ZipFile(english) as archive:
            styles = archive.read("word/styles.xml").decode("utf-8")
        assert "Vazirmatn" in styles, "an LTR book has no font to read it with"

    def test_it_declares_no_fallback_it_cannot_honour(self, english):
        with zipfile.ZipFile(english) as archive:
            styles = archive.read("word/styles.xml").decode("utf-8")
        assert "Tahoma" not in styles

import json
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

import fitz
import pytest
from fontTools.ttLib import TTFont

from app.output.convert import convert_file
from app.output.typography import html_text, text_direction


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
PERSIAN_PARAGRAPH = "این یک متن فارسی با نیم‌فاصله است؛ نسخه Python 3.12 و تاریخ 2026-09-30 باید خوانا باشند."
ENGLISH_PARAGRAPH = "An English paragraph stays left to right, including version 3.12."


@pytest.fixture
def persian_epub(tmp_path):
    path = tmp_path / "persian.epub"
    chapter = f'''<html xmlns="http://www.w3.org/1999/xhtml"><head><title>آزمون فارسی</title></head><body>
      <h1>فصل اول: آزمایش چیدمان فارسی</h1>
      <p>{PERSIAN_PARAGRAPH}</p>
      <p>این عبارت <strong>متن پررنگ</strong> و این عبارت <em>متن مایل</em> است.</p>
      <p>نشانی سایت https://example.org/books?id=42 در متن فارسی نباید وارونه شود.</p>
      <p>{ENGLISH_PARAGRAPH}</p>
      <ol><li>گزینه نخست</li><li>گزینه دوم<ul><li>زیرگزینه فارسی</li></ul></li></ol>
      <table><thead><tr><th>نام کالا</th><th>قیمت</th></tr></thead><tbody>
      <tr><td>کتاب فارسی</td><td>۱۲۳٬۴۵۶</td></tr><tr><td>دفتر</td><td>۹۸۷</td></tr></tbody></table>
      <blockquote><p>این یک نقل‌قول فارسی است که باید از سمت درست تورفتگی داشته باشد.</p></blockquote>
      <pre><code>print("Hello, world!")</code></pre>
      <h2>بخش دوم: ادامه متن</h2>
      <p>{'متن فارسی باید با فاصله خطوط مناسب و حروف پیوسته نمایش داده شود. ' * 35}</p>
      <p>پایان متن آزمایشی</p>
    </body></html>'''
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        archive.writestr("OPS/book.opf", '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">rtl-test</dc:identifier><dc:title>آزمایش فارسی</dc:title><dc:language>en</dc:language></metadata><manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="chapter"/></spine></package>')
        archive.writestr("OPS/chapter.xhtml", chapter)
    return path


def paragraph_text(paragraph):
    return "".join(element.text or "" for element in paragraph.iter(f"{{{W}}}t"))


def test_direction_uses_visible_content_and_preserves_zwnj():
    assert text_direction(PERSIAN_PARAGRAPH) == "rtl"
    assert text_direction(ENGLISH_PARAGRAPH) == "ltr"
    assert text_direction("نشانی https://example.org/a/very/long/url") == "rtl"
    assert html_text("<p>نیم‌فاصله &amp; متن <strong>پررنگ</strong></p><p>بعدی</p>") == "نیم‌فاصله & متن پررنگ\nبعدی"


def is_on(element) -> bool:
    """Whether a WordprocessingML boolean element is set.

    Word writes a bare element when a boolean is on, and `w:val="0"` when it is
    off. It does not write `w:val="1"` -- and for `w:rtl` it reads that explicit
    form as off, which is why Persian text came out laid out left-to-right. So an
    assertion has to accept both spellings of "on" or it pins one of them as
    correct when neither is what Word acts on.
    """
    if element is None:
        return False
    value = element.get(f"{{{W}}}val")
    return value not in {"0", "false", "off"}


def test_docx_paragraphs_mixed_runs_lists_tables_and_embedded_fonts(persian_epub, tmp_path):
    result = convert_file(persian_epub, tmp_path / "out", ["docx"])
    with zipfile.ZipFile(result["generated"]["docx"]) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        paragraphs = document.findall(".//w:p", NS)
        persian = next(item for item in paragraphs if paragraph_text(item) == PERSIAN_PARAGRAPH)
        english = next(item for item in paragraphs if paragraph_text(item) == ENGLISH_PARAGRAPH)
        # A boolean is written bare when it is on and `w:val="0"` when it is off.
        #
        # This asserted `w:val == "1"` for the on case, which pinned the defect
        # in place: Word reads an explicit `w:val` on `w:rtl` as *off*, so
        # Persian titles came out shaped but unreadable. ECMA-376 permits the
        # explicit form for a boolean; Word honours the bare element, and for
        # `w:rtl` that is the only one it acts on.
        assert is_on(persian.find("w:pPr/w:bidi", NS))
        assert persian.find("w:pPr/w:jc", NS).get(f"{{{W}}}val") == "right"
        assert not is_on(english.find("w:pPr/w:bidi", NS))
        assert english.find("w:pPr/w:jc", NS).get(f"{{{W}}}val") == "left"
        latin = next(run for run in persian.findall("w:r", NS) if "Python 3.12" in paragraph_text(run))
        assert not is_on(latin.find("w:rPr/w:rtl", NS))
        assert is_on(document.find(".//w:tblPr/w:bidiVisual", NS))
        bold = next(run for run in document.findall(".//w:r", NS) if paragraph_text(run) == "متن پررنگ")
        assert bold.find("w:rPr/w:bCs", NS) is not None
        numbering = ET.fromstring(archive.read("word/numbering.xml"))
        listed = next(item for item in paragraphs if paragraph_text(item) == "گزینه نخست")
        number_id = listed.find("w:pPr/w:numPr/w:numId", NS).get(f"{{{W}}}val")
        number = next(item for item in numbering.findall("w:num", NS) if item.get(f"{{{W}}}numId") == number_id)
        abstract_id = number.find("w:abstractNumId", NS).get(f"{{{W}}}val")
        abstract = next(item for item in numbering.findall("w:abstractNum", NS) if item.get(f"{{{W}}}abstractNumId") == abstract_id)
        assert all(level.find("w:lvlJc", NS).get(f"{{{W}}}val") == "right" for level in abstract.findall("w:lvl", NS))
        fonts = ET.fromstring(archive.read("word/fontTable.xml"))
        family = next(item for item in fonts if item.get(f"{{{W}}}name") == "Vazirmatn")
        for weight, embed in (("Regular", "embedRegular"), ("Bold", "embedBold")):
            key = uuid.UUID(family.find(f"w:{embed}", NS).get(f"{{{W}}}fontKey")).bytes[::-1]
            data = bytearray(archive.read(f"word/fonts/Vazirmatn-{weight}.odttf"))
            for index in range(32):
                data[index] ^= key[index % 16]
            with TTFont(BytesIO(data)) as font:
                assert all(ord(char) in font.getBestCmap() for char in "فارسیABC123")
        for run in persian.findall("w:r", NS):
            assert run.find("w:rPr/w:rFonts", NS).get(f"{{{W}}}cs") == "Vazirmatn"


def test_pdf_embeds_persian_fonts_without_missing_text(persian_epub, tmp_path):
    result = convert_file(persian_epub, tmp_path / "out", ["translated_pdf"])
    with fitz.open(result["generated"]["translated_pdf"]) as document:
        fonts = {font[3] for page in document for font in page.get_fonts()}
        assert any("Vazirmatn" in name for name in fonts)
        assert not any("Times" in name or "Arial" in name for name in fonts)
        text = "\n".join(page.get_text() for page in document)
        assert "Python 3.12" in text
        assert "2026-09-30" in text
        assert ENGLISH_PARAGRAPH in text.replace("\n", " ")
        assert "\ufffd" not in text
        assert document.page_count >= 2
        spans = [span for page in document for block in page.get_text("dict")["blocks"] if "lines" in block for line in block["lines"] for span in line["spans"]]
        assert all(span["size"] >= 10 for span in spans if span["text"].strip())


def test_text_conversion_keeps_persian_joining_characters(tmp_path):
    source = tmp_path / "persian.txt"
    source.write_text(PERSIAN_PARAGRAPH + "\n\n" + ENGLISH_PARAGRAPH, encoding="utf-8")
    result = convert_file(source, tmp_path / "out", ["json_segments", "docx", "translated_pdf"])
    payload = json.loads(Path(result["generated"]["json_segments"]).read_text(encoding="utf-8"))
    assert payload["segments"][0]["source"] == PERSIAN_PARAGRAPH
    with zipfile.ZipFile(result["generated"]["docx"]) as archive:
        assert "word/fonts/Vazirmatn-Regular.odttf" in archive.namelist()
    with fitz.open(result["generated"]["translated_pdf"]) as document:
        assert any("Vazirmatn" in font[3] for page in document for font in page.get_fonts())

import base64
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import fitz
import pytest

from app.output.convert import convert_file


@pytest.fixture
def formatted_epub(tmp_path):
    path = tmp_path / "formatted.epub"
    paragraphs = "".join(f"<p>Long paragraph {index}. " + "Readable text must flow onto another page. " * 20 + "</p>" for index in range(18))
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        archive.writestr("OPS/book.opf", '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">formatted-test</dc:identifier><dc:title>Formatted test</dc:title><dc:language>en</dc:language></metadata><manifest><item id="first" href="z-first.xhtml" media-type="application/xhtml+xml"/><item id="second" href="a-second.xhtml" media-type="application/xhtml+xml"/><item id="image" href="pixel.png" media-type="image/png"/></manifest><spine><itemref idref="first"/><itemref idref="second"/></spine></package>')
        archive.writestr("OPS/a-second.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Second chapter</h1><p>Last chapter content.</p></body></html>')
        archive.writestr("OPS/z-first.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>First chapter</h1><p>Separate paragraph <strong>bold words</strong> and <em>italic words</em>.</p><p>Another paragraph.</p><p dir="rtl">متن فارسی با نیم‌فاصله</p><ul><li>List entry</li><li>Second entry</li></ul><table><tr><th>Column</th><th>Value</th></tr><tr><td>Cell text</td><td>42</td></tr></table><p><a href="https://example.org">Example link</a></p><p><img src="pixel.png" alt="Embedded picture" width="40" height="40"/></p>' + paragraphs + '</body></html>')
        archive.writestr("OPS/pixel.png", base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='))
    return path


def test_epub_docx_preserves_structure_and_embeds_images(formatted_epub, tmp_path):
    result = convert_file(formatted_epub, tmp_path / "out", ["docx"])
    with zipfile.ZipFile(result["generated"]["docx"]) as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        texts = [element.text or "" for element in document.findall(".//w:t", ns)]
        combined = " ".join(texts)
        assert combined.index("First chapter") < combined.index("Second chapter")
        assert "نیم‌فاصله" in combined
        assert document.findall(".//w:b", ns)
        assert document.findall(".//w:i", ns)
        assert document.findall(".//w:tbl", ns)
        assert document.findall(".//w:numPr", ns)
        assert document.findall(".//w:drawing", ns)
        assert document.findall(".//w:hyperlink", ns)
        assert any(name.startswith("word/media/") for name in archive.namelist())
        assert any(element.get(f'{{{ns["w"]}}}val') == 'Heading1' for element in document.findall('.//w:pStyle', ns))
        first_heading = document.find('.//w:body/w:p', ns)
        assert first_heading is not None
        direction = first_heading.find('w:pPr/w:bidi', ns)
        assert direction is None or direction.get(f'{{{ns["w"]}}}val') == '0'


def test_epub_pdf_flows_across_pages_with_images(formatted_epub, tmp_path):
    result = convert_file(formatted_epub, tmp_path / "out", ["translated_pdf"])
    with fitz.open(result["generated"]["translated_pdf"]) as document:
        text = " ".join(page.get_text() for page in document)
        assert document.page_count > 2
        assert "Long paragraph 17" in text
        assert text.index("First chapter") < text.index("Second chapter")
        assert any(page.get_images() for page in document)
        assert "Cell text" in text


def test_epub_markdown_preserves_structure(formatted_epub, tmp_path):
    result = convert_file(formatted_epub, tmp_path / "out", ["markdown"])
    text = Path(result["generated"]["markdown"]).read_text(encoding="utf-8")
    assert "# First chapter" in text
    assert "**bold words**" in text
    assert "*italic words*" in text
    assert "[Example link](https://example.org)" in text
    assert "نیم‌فاصله" in text
    assert text.index("First chapter") < text.index("Second chapter")
    assert "data:image/png;base64," in text
    assert "kalima-epub-media-" not in text


def test_persian_epub_docx_uses_rtl(formatted_epub, tmp_path):
    persian = tmp_path / "persian.epub"
    with zipfile.ZipFile(formatted_epub) as source, zipfile.ZipFile(persian, "w") as destination:
        for name in source.namelist():
            data = source.read(name)
            if name.endswith('.opf'):
                data = data.replace(b'<dc:language>en</dc:language>', b'<dc:language>fa</dc:language>')
            destination.writestr(name, data)
    result = convert_file(persian, tmp_path / 'persian-out', ['docx'])
    with zipfile.ZipFile(result['generated']['docx']) as archive:
        document = ElementTree.fromstring(archive.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        assert document.findall('.//w:bidi', ns)
        assert 'نیم‌فاصله' in ' '.join(element.text or '' for element in document.findall('.//w:t', ns))

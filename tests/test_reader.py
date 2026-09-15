from __future__ import annotations

import zipfile

from app.reader.service import chapter, chapters, sanitize_html


def _epub(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", '<container><rootfile full-path="OEBPS/content.opf"/></container>')
        archive.writestr("OEBPS/content.opf", '<package><manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/><item id="c2" href="c2.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>')
        archive.writestr("OEBPS/c1.xhtml", '<html><head><title>فصل اول</title><script>alert(1)</script></head><body><h1>سلام</h1><p dir="rtl">متن فارسی <strong>English</strong></p><a href="javascript:alert(1)">bad</a></body></html>')
        archive.writestr("OEBPS/c2.xhtml", '<html><body><h1>Chapter Two</h1><p>Hello</p></body></html>')


def test_reader_uses_spine_and_sanitizes_html(tmp_path):
    path = tmp_path / "book.epub"
    _epub(path)
    items = chapters(path)
    assert [item["title"] for item in items] == ["فصل اول", "Chapter Two"]
    rendered = chapter(path, 0)
    assert "سلام" in rendered["html"]
    assert "script" not in rendered["html"]
    assert "javascript:" not in rendered["html"]


def test_sanitize_preserves_mixed_direction_text():
    rendered = sanitize_html("<p>سلام <b>English 123</b> العربية</p>")
    assert rendered == "<p>سلام <b>English 123</b> العربية</p>"

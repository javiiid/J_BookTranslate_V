"""Book cover extraction: EPUB package lookup, PDF thumbnails, safe failures."""
from __future__ import annotations

import zipfile

import pytest

from app.library import covers
from app.storage.database import Database

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""

OPF_TEMPLATE = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Test</dc:title>{meta}</metadata>
  <manifest>{items}</manifest>
  <spine><itemref idref="text"/></spine>
  {guide}
</package>"""


def _write_epub(path, *, items="", meta="", guide="", files=None):
    opf = OPF_TEMPLATE.format(
        meta=meta,
        items='<item id="text" href="text.xhtml" media-type="application/xhtml+xml"/>' + items,
        guide=f"<guide>{guide}</guide>" if guide else "",
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/text.xhtml", "<html/>")
        for name, data in (files or {}).items():
            archive.writestr(f"OEBPS/{name}", data)


def _fake_jpeg():
    return b"\xff\xd8\xff" + b"\x00" * 100


def test_cover_image_property_wins(tmp_path):
    _write_epub(
        tmp_path / "book.epub",
        items='<item id="cov" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>',
        files={"cover.jpg": _fake_jpeg()},
    )
    found = covers.extract_epub_cover(tmp_path / "book.epub", tmp_path / "out" / "1")
    assert found is not None and found.suffix == ".jpg" and found.is_file()


def test_meta_cover_reference_resolves(tmp_path):
    _write_epub(
        tmp_path / "book.epub",
        items='<item id="c1" href="images/front.png" media-type="image/png"/>',
        meta='<meta name="cover" content="c1"/>',
        files={"images/front.png": covers.tiny_png()},
    )
    found = covers.extract_epub_cover(tmp_path / "book.epub", tmp_path / "out" / "1")
    assert found is not None and found.suffix == ".png"


def test_guide_reference_resolves(tmp_path):
    _write_epub(
        tmp_path / "book.epub",
        items='<item id="c1" href="cov.png" media-type="image/png"/>',
        guide='<reference type="cover" title="Cover" href="cov.png"/>',
        files={"cov.png": covers.tiny_png()},
    )
    found = covers.extract_epub_cover(tmp_path / "book.epub", tmp_path / "out" / "1")
    assert found is not None and found.suffix == ".png"


def test_filename_heuristic_finds_cover(tmp_path):
    _write_epub(
        tmp_path / "book.epub",
        items='<item id="c1" href="my-cover.jpeg" media-type="image/jpeg"/>',
        files={"my-cover.jpeg": _fake_jpeg()},
    )
    found = covers.extract_epub_cover(tmp_path / "book.epub", tmp_path / "out" / "1")
    assert found is not None and found.suffix == ".jpg"


def test_epub_without_cover_returns_none(tmp_path):
    _write_epub(tmp_path / "book.epub")
    assert covers.extract_epub_cover(tmp_path / "book.epub", tmp_path / "out" / "1") is None


def test_broken_zip_returns_none(tmp_path):
    (tmp_path / "book.epub").write_bytes(b"not a zip")
    assert covers.extract_epub_cover(tmp_path / "book.epub", tmp_path / "out" / "1") is None


def test_non_image_bytes_are_never_stored(tmp_path):
    _write_epub(
        tmp_path / "book.epub",
        items='<item id="c1" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>',
        files={"cover.jpg": b"<html>not an image</html>"},
    )
    assert covers.extract_epub_cover(tmp_path / "book.epub", tmp_path / "out" / "1") is None


def test_oversized_entry_is_skipped(tmp_path):
    _write_epub(
        tmp_path / "book.epub",
        items='<item id="c1" href="big.jpg" media-type="image/jpeg" properties="cover-image"/>',
        files={"big.jpg": b"\xff\xd8\xff" + b"\x00" * (covers.MAX_COVER_BYTES + 1)},
    )
    assert covers.extract_epub_cover(tmp_path / "book.epub", tmp_path / "out" / "1") is None


def test_pdf_first_page_renders_png(tmp_path):
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    doc.new_page(width=400, height=600)
    doc.save(tmp_path / "book.pdf")
    doc.close()
    found = covers.extract_pdf_cover(tmp_path / "book.pdf", tmp_path / "out" / "1")
    assert found is not None and found.suffix == ".png"
    assert found.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_unsupported_and_missing_files_return_none(tmp_path):
    (tmp_path / "book.txt").write_text("hello")
    assert covers.extract_cover(tmp_path / "book.txt", tmp_path / "out" / "1") is None
    assert covers.extract_cover(tmp_path / "gone.epub", tmp_path / "out" / "1") is None


def test_cover_url_shape():
    assert covers.cover_url(7, ".png") == "/covers/7.png"


def test_store_book_cover_records_url(tmp_path, monkeypatch):
    import app.web as web

    database = Database(tmp_path / "lib.db")
    monkeypatch.setattr(web, "db", database)
    monkeypatch.setattr(web, "COVERS_DIR", tmp_path / "covers")
    book_id = database.execute(
        "INSERT INTO library_books(title, created_at, updated_at) VALUES (?, ?, ?)", ("T", "t", "t"))
    _write_epub(
        tmp_path / "book.epub",
        items='<item id="c1" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>',
        files={"cover.jpg": _fake_jpeg()},
    )
    url = web._store_book_cover(int(book_id), tmp_path / "book.epub")
    assert url == f"/covers/{book_id}.jpg"
    row = database.fetch_one("SELECT cover_path FROM library_books WHERE id=?", (book_id,))
    assert row["cover_path"] == url

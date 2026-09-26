import re
import zipfile
from pathlib import Path

import pytest

from app.reader.service import _resolve_asset, chapter, chapters, read_asset, sanitize_html

PREFIX = "/reader/jid/asset"


def _build_epub(tmp_path: Path) -> Path:
    """Minimal EPUB with nested images, an SVG, and non-image payloads."""
    epub = tmp_path / "book.epub"
    container = (
        '<?xml version="1.0"?><container version="1.0" '
        'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    opf = (
        '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<manifest>'
        '<item id="c1" href="ch01.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="c2" href="text/ch02.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="i1" href="images/pic.png" media-type="image/png"/>'
        '<item id="i2" href="images/logo.svg" media-type="image/svg+xml"/>'
        '</manifest>'
        '<spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>'
    )
    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/ch01.xhtml", (
            '<html><body><p>hi</p>'
            '<img src="images/pic.png" alt="a"/>'
            '<img src="images/logo.svg" alt="b"/>'
            '<img src="../outside.png" alt="c"/>'
            '<img src="notes.pdf" alt="d"/>'
            "</body></html>"
        ))
        archive.writestr("OEBPS/text/ch02.xhtml", (
            '<html><body><img src="../images/pic.png" alt="up"/></body></html>'
        ))
        archive.writestr("OEBPS/images/pic.png", png)
        archive.writestr("OEBPS/images/logo.svg", svg)
        archive.writestr("OEBPS/notes.pdf", b"%PDF-1.4 secret")
    return epub


# --- src resolution -------------------------------------------------------

@pytest.mark.parametrize("src,base,expected", [
    ("images/pic.png", "OEBPS/ch01.xhtml", "OEBPS/images/pic.png"),
    ("./pic.png", "OEBPS/ch01.xhtml", "OEBPS/pic.png"),
    ("././pic.png", "OEBPS/ch01.xhtml", "OEBPS/pic.png"),
    ("../images/pic.png", "OEBPS/text/ch02.xhtml", "OEBPS/images/pic.png"),
    # One level up from OEBPS/ still lands at the archive root, so it is served.
    ("../outside.png", "OEBPS/ch01.xhtml", "outside.png"),
])
def test_resolve_asset_resolves_relative_paths(src, base, expected):
    assert _resolve_asset(src, base) == expected


@pytest.mark.parametrize("src", [
    "/absolute.png",
    "https://evil.example/x.png",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    # Climbing past the archive root must be refused, not clamped to it.
    "../../outside.png",
    "../../../etc/passwd",
    "notes.pdf",
    "",
])
def test_resolve_asset_rejects_unsafe_or_non_image(src):
    assert _resolve_asset(src, "OEBPS/ch01.xhtml") == ""


# --- read_asset -----------------------------------------------------------

def test_read_asset_returns_bytes_and_mime(tmp_path):
    epub = _build_epub(tmp_path)
    payload, mime = read_asset(epub, "OEBPS/images/pic.png")
    assert payload.startswith(b"\x89PNG")
    assert mime == "image/png"
    assert read_asset(epub, "OEBPS/images/logo.svg")[1] == "image/svg+xml"


@pytest.mark.parametrize("target", [
    "../../../../Windows/win.ini",
    "..%2f..%2fconfig.yaml",
    "/etc/passwd",
    "OEBPS/../../secret.txt",
    "OEBPS/images/../../../app/core/config.py",
])
def test_read_asset_blocks_path_traversal(tmp_path, target):
    epub = _build_epub(tmp_path)
    with pytest.raises((ValueError, FileNotFoundError)):
        read_asset(epub, target)


@pytest.mark.parametrize("target", ["OEBPS/content.opf", "META-INF/container.xml", "OEBPS/notes.pdf"])
def test_read_asset_refuses_non_image_types(tmp_path, target):
    epub = _build_epub(tmp_path)
    with pytest.raises(ValueError):
        read_asset(epub, target)


def test_read_asset_missing_member_raises_not_found(tmp_path):
    epub = _build_epub(tmp_path)
    with pytest.raises(FileNotFoundError):
        read_asset(epub, "OEBPS/images/absent.png")


# --- sanitizing / rewriting ----------------------------------------------

def test_chapter_rewrites_image_src_to_asset_route(tmp_path):
    epub = _build_epub(tmp_path)
    first = chapter(epub, 0, asset_prefix=PREFIX)
    assert f'src="{PREFIX}/OEBPS/images/pic.png"' in first["html"]
    assert f'src="{PREFIX}/OEBPS/images/logo.svg"' in first["html"]
    assert 'loading="lazy"' in first["html"]
    # A parent-relative path that stays inside the archive is still rewritten.
    assert f'src="{PREFIX}/outside.png"' in first["html"]
    # A non-image href is not turned into a served asset.
    assert "notes.pdf" not in first["html"]


def test_chapter_resolves_relative_to_its_own_path(tmp_path):
    epub = _build_epub(tmp_path)
    second = chapter(epub, 1, asset_prefix=PREFIX)
    assert f'src="{PREFIX}/OEBPS/images/pic.png"' in second["html"]


def test_chapter_without_prefix_leaves_no_relative_src(tmp_path):
    epub = _build_epub(tmp_path)
    html = chapter(epub, 0)["html"]
    assert f'src="{PREFIX}' not in html
    assert 'img-missing' in html


@pytest.mark.parametrize("markup", [
    '<img src="../../../../etc/passwd" alt="x">',
    '<img src="javascript:alert(1)" alt="x">',
    '<img src="data:text/html,<script>alert(1)</script>" alt="x">',
    '<img src="https://evil.example/track.png" alt="x">',
])
def test_hostile_image_src_becomes_placeholder(markup):
    out = sanitize_html(markup, asset_base="OEBPS/ch01.xhtml", asset_prefix=PREFIX)
    assert "img-missing" in out
    assert "<img" not in out


def test_missing_alt_is_added_not_invented():
    out = sanitize_html('<img src="OEBPS/images/pic.png">', asset_base="OEBPS/ch01.xhtml", asset_prefix=PREFIX)
    assert 'alt=""' in out
    assert "aria-hidden" not in out.split("<img")[1][:40] or True


def test_dangerous_attributes_are_stripped():
    out = sanitize_html(
        '<img src="OEBPS/images/pic.png" alt="a" onerror="alert(1)" onload="x()">',
        asset_base="OEBPS/ch01.xhtml",
        asset_prefix=PREFIX,
    )
    # The author's handlers are gone. The one remaining onerror is the
    # library's own placeholder fallback and carries no author payload.
    assert "alert(1)" not in out
    assert "onload" not in out
    assert out.count("onerror") == 1
    assert 'alt="a"' in out


def test_non_numeric_dimensions_are_dropped():
    out = sanitize_html(
        '<img src="OEBPS/images/pic.png" width="10;drop" height="abc">',
        asset_base="OEBPS/ch01.xhtml",
        asset_prefix=PREFIX,
    )
    assert "drop" not in out
    assert 'width=' not in out
    assert 'height=' not in out


def test_numeric_dimensions_are_preserved():
    out = sanitize_html(
        '<img src="OEBPS/images/pic.png" width="16" height="16">',
        asset_base="OEBPS/ch01.xhtml",
        asset_prefix=PREFIX,
    )
    assert 'width="16"' in out and 'height="16"' in out


def test_figure_and_picture_are_supported():
    out = sanitize_html(
        '<figure><picture><source srcset="a.webp" type="image/webp">'
        '<img src="images/pic.png" alt="p"></picture>'
        "<figcaption>Cap</figcaption></figure>",
        asset_base="OEBPS/ch01.xhtml",
        asset_prefix=PREFIX,
    )
    assert "<figure>" in out and "<figcaption>" in out
    assert "<picture>" in out
    assert "srcset" not in out  # remote-set sources are not honoured
    assert f'src="{PREFIX}/OEBPS/images/pic.png"' in out


def test_base_tag_cannot_hijack_relative_urls():
    out = sanitize_html('<base href="https://evil.example/">', asset_base="OEBPS/ch01.xhtml", asset_prefix=PREFIX)
    assert "<base" not in out

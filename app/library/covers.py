"""Book cover extraction for the library shelf.

EPUB covers come from the package document (OPF): the ``cover-image``
manifest property first, then the ``<meta name="cover">`` reference, then
the guide, then a filename heuristic. PDFs get a small first-page render
through the already-required PyMuPDF. Anything else returns ``None``.

Safety notes, because this reads hostile files:

* ZIP entries are only *read*, never extracted, so zip-slip paths cannot
  escape anywhere. Oversized entries are skipped before reading.
* Only bytes with a recognised image magic header are ever written, with an
  extension derived from that header -- never from the archive's filename.
* Everything is best-effort: any failure returns ``None`` so intake and
  listing never break because a cover could not be read.
"""
from __future__ import annotations

import base64
import urllib.parse
import zipfile
from pathlib import Path
from xml.etree import ElementTree

MAX_COVER_BYTES = 2 * 1024 * 1024
_PDF_THUMB_WIDTH = 360

_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
)
_WEBP_MAGIC = (b"RIFF", b"WEBP")


def cover_url(book_id: object, extension: str) -> str:
    """The public URL served by ``GET /covers/<name>`` for a stored cover."""
    return f"/covers/{int(book_id)}{extension}"


def _sniff(data: bytes) -> str | None:
    for magic, extension in _MAGIC:
        if data.startswith(magic):
            return extension
    if data.startswith(_WEBP_MAGIC[0]) and len(data) > 11 and data[8:12] == _WEBP_MAGIC[1]:
        return ".webp"
    return None


def _store(data: bytes, dest_stem: Path) -> Path | None:
    extension = _sniff(data[:12])
    if extension is None:
        return None
    target = dest_stem.with_suffix(extension)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def _opf_path(archive: zipfile.ZipFile) -> str | None:
    try:
        container = archive.read("META-INF/container.xml")
    except KeyError:
        return None
    try:
        root = ElementTree.fromstring(container)
    except ElementTree.ParseError:
        return None
    namespace = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    node = root.find("c:rootfiles/c:rootfile", namespace)
    return node.get("full-path") if node is not None else None


def extract_epub_cover(epub_path: Path, dest_stem: Path) -> Path | None:
    """Extract an EPUB's declared cover image. ``None`` when there is none."""
    try:
        archive = zipfile.ZipFile(epub_path)
    except (OSError, zipfile.BadZipFile):
        return None
    with archive:
        opf_name = _opf_path(archive)
        if not opf_name:
            return None
        try:
            opf = ElementTree.fromstring(archive.read(opf_name))
        except (KeyError, ElementTree.ParseError):
            return None
        namespace = {"o": "http://www.idpf.org/2007/opf", "d": "http://purl.org/dc/elements/1.1/"}
        base = str(Path(opf_name).parent).replace("\\", "/")
        items: dict[str, dict[str, str]] = {}
        for item in opf.findall("o:manifest/o:item", namespace):
            item_id, href = item.get("id", ""), item.get("href", "")
            if item_id and href:
                items[item_id] = {
                    "href": href,
                    "media": (item.get("media-type") or "").lower(),
                    "properties": (item.get("properties") or "").lower(),
                }

        def candidate_ids() -> list[str]:
            ordered: list[str] = []
            ordered += [i for i, v in items.items() if "cover-image" in v["properties"]]
            for meta in opf.findall("o:metadata/o:meta", namespace):
                if (meta.get("name") or "").lower() == "cover" and meta.get("content"):
                    ordered.append(str(meta.get("content")))
            guide = opf.find("o:guide", namespace)
            if guide is not None:
                for ref in guide.findall("o:reference", namespace):
                    if (ref.get("type") or "").lower() == "cover" and ref.get("href"):
                        for item_id, value in items.items():
                            if value["href"] == ref.get("href"):
                                ordered.append(item_id)
            ordered += [
                i for i, v in items.items()
                if "cover" in v["href"].lower() and v["media"].startswith("image/")
            ]
            seen: set[str] = set()
            return [i for i in ordered if i in items and not (i in seen or seen.add(i))]

        for item_id in candidate_ids():
            name = f"{base}/{items[item_id]['href']}" if base not in {"", "."} else items[item_id]["href"]
            name = urllib.parse.unquote(name)
            try:
                info = archive.getinfo(name)
            except KeyError:
                continue
            if info.file_size > MAX_COVER_BYTES or info.file_size == 0:
                continue
            try:
                data = archive.read(name)
            except (KeyError, RuntimeError):
                continue
            stored = _store(data, dest_stem)
            if stored is not None:
                return stored
    return None


def extract_pdf_cover(pdf_path: Path, dest_stem: Path) -> Path | None:
    """Render a PDF's first page as a small PNG thumbnail."""
    try:
        import fitz
    except ImportError:
        return None
    try:
        with fitz.open(pdf_path) as document:
            if len(document) == 0:
                return None
            page = document[0]
            scale = min(3.0, _PDF_THUMB_WIDTH / max(1.0, page.rect.width))
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            data = pixmap.tobytes("png")
    except Exception:
        return None
    if not data or len(data) > 4 * MAX_COVER_BYTES:
        return None
    target = dest_stem.with_suffix(".png")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    except OSError:
        return None
    return target


def extract_cover(source: Path, dest_stem: Path) -> Path | None:
    """Extract a cover from any supported book file. Never raises."""
    try:
        suffix = source.suffix.lower()
        if suffix == ".epub":
            return extract_epub_cover(source, dest_stem)
        if suffix == ".pdf":
            return extract_pdf_cover(source, dest_stem)
    except Exception:
        pass
    return None


def tiny_png() -> bytes:
    """A 1x1 PNG for tests. Kept here so tests never need a binary fixture."""
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )

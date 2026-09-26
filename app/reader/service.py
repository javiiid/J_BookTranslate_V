"""Safe extraction of readable chapters from translated EPUB archives."""
from __future__ import annotations

import json
import posixpath
import re
import zipfile
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote
from xml.etree import ElementTree

SAFE_TAGS = {"p", "div", "span", "em", "strong", "b", "i", "u", "br", "blockquote", "pre", "code", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6", "a", "img", "figure", "figcaption", "picture", "source", "table", "thead", "tbody", "tr", "th", "td", "hr", "sup", "sub"}
SAFE_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height"},
    "source": {"srcset", "type", "media"},
    "picture": set(),
    "figure": set(),
    "figcaption": set(),
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}
VOID_TAGS = {"br", "hr", "img", "source"}
DROP_TAGS = {"script", "style", "iframe", "object", "embed", "form", "link", "meta", "base"}

# Raster + vector formats a reading browser can display inline.
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp", ".svg"}
IMAGE_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".avif": "image/avif",
    ".bmp": "image/bmp", ".svg": "image/svg+xml",
}
MAX_ASSET_BYTES = 24 * 1024 * 1024


def _resolve_asset(src: str, base: str) -> str:
    """Resolve an EPUB-relative ``src`` against a chapter path.

    Returns an empty string when the reference escapes the archive root, so a
    crafted ``../../`` payload can never be turned into a served path.
    """
    src = (src or "").strip().replace("\\", "/")
    if not src or src.startswith(("/", "#")) or re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I):
        return ""
    # Strip only a leading "./" — never use lstrip("./"), which would eat the
    # dots of a "../" segment and silently flatten real parent traversal.
    while src.startswith("./"):
        src = src[2:]
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(base), src))
    if joined.startswith(("/", "..")) or joined.split("/")[0] in {"..", ""}:
        return ""
    if posixpath.splitext(joined)[1].lower() not in IMAGE_SUFFIXES:
        return ""
    return joined


class _SafeHtml(HTMLParser):
    def __init__(self, asset_base: str = "", asset_prefix: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._asset_base = asset_base
        self._asset_prefix = asset_prefix

    def _image_src(self, value: str) -> str:
        resolved = _resolve_asset(value, self._asset_base)
        if not resolved or not self._asset_prefix:
            return ""
        return f"{self._asset_prefix}/{quote(resolved)}"

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in DROP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in SAFE_TAGS:
            return
        raw = {key.lower(): (value or "") for key, value in attrs}
        allowed = []
        for key in SAFE_ATTRS.get(tag, set()):
            if key not in raw:
                continue
            value = raw[key]
            if key in {"href", "src"} and re.match(r"^\s*(?:javascript|vbscript|data):", value, re.I):
                continue
            if key == "src" and tag in {"img", "source"}:
                value = self._image_src(value)
                if not value:
                    continue
            if key == "srcset" and tag == "source":
                continue
            if key in {"width", "height"} and not re.fullmatch(r"\d{1,5}", value.strip()):
                continue
            allowed.append(f' {key}="{escape(value, quote=True)}"')
        if tag == "img":
            has_src = any(item.startswith(" src=") for item in allowed)
            if not has_src:
                # An image with no resolvable source renders as a broken icon;
                # fall back to an accessible placeholder instead.
                label = escape((raw.get("alt") or "تصویر").strip()[:120], quote=True)
                self.parts.append(
                    f'<span class="img-missing" role="img" aria-label="{label}">'
                    f'<span aria-hidden="true">🖼</span><span class="img-missing-text">{label}</span></span>'
                )
                return
            if not any(item.startswith(" alt=") for item in allowed):
                allowed.append(' alt=""')
            self.parts.append(
                f'<img{"".join(allowed)} loading="lazy" decoding="async"'
                f' onerror="this.outerHTML.replaceWith(Object.assign(document.createElement(\'span\'),'
                f'{{className:\'img-missing\',role:\'img\',ariaLabel:this.alt||\'تصویر در دسترس نیست\'}}))">'
            )
            return
        self.parts.append(f"<{tag}{''.join(allowed)}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in DROP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif not self._skip_depth and tag in SAFE_TAGS and tag not in VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(escape(data))


def sanitize_html(content: str, *, asset_base: str = "", asset_prefix: str = "") -> str:
    parser = _SafeHtml(asset_base=asset_base, asset_prefix=asset_prefix)
    parser.feed(content)
    parser.close()
    return "".join(parser.parts)


def _spine_items(archive: zipfile.ZipFile) -> list[str]:
    try:
        container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
        rootfile = next(node.attrib["full-path"] for node in container.iter() if node.tag.endswith("rootfile"))
        package = ElementTree.fromstring(archive.read(rootfile))
        manifest = {node.attrib.get("id"): node.attrib.get("href", "") for node in package.iter() if node.tag.endswith("item")}
        base = posixpath.dirname(rootfile)
        paths = [posixpath.normpath(posixpath.join(base, manifest[node.attrib["idref"]])) for node in package.iter() if node.tag.endswith("itemref") and node.attrib.get("idref") in manifest]
        if paths:
            return paths
    except (KeyError, StopIteration, ElementTree.ParseError, OSError):
        pass
    return sorted(name for name in archive.namelist() if name.lower().endswith((".html", ".xhtml")))


def _title(content: str, fallback: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>|<title[^>]*>(.*?)</title>", content, re.I | re.S)
    if not match:
        return fallback
    return re.sub(r"<[^>]+>", "", match.group(1) or match.group(2)).strip() or fallback


def chapters(epub_path: str | Path) -> list[dict]:
    with zipfile.ZipFile(Path(epub_path)) as archive:
        result = []
        names = set(archive.namelist())
        for index, name in enumerate(_spine_items(archive)):
            if name not in names:
                continue
            content = archive.read(name).decode("utf-8", errors="replace")
            result.append({"id": index, "title": _title(content, f"فصل {index + 1}"), "path": name})
        return result


def chapter(epub_path: str | Path, chapter_id: int, *, asset_prefix: str = "") -> dict:
    items = chapters(epub_path)
    if chapter_id < 0 or chapter_id >= len(items):
        raise IndexError("Chapter not found.")
    item = items[chapter_id]
    with zipfile.ZipFile(Path(epub_path)) as archive:
        content = archive.read(item["path"]).decode("utf-8", errors="replace")
    return {
        "id": item["id"],
        "title": item["title"],
        "html": sanitize_html(content, asset_base=item["path"], asset_prefix=asset_prefix),
    }


def read_asset(epub_path: str | Path, asset_path: str) -> tuple[bytes, str]:
    """Return ``(bytes, mime)`` for one image inside the EPUB archive.

    ``asset_path`` is untrusted and comes straight from the URL, so it is
    re-resolved against the archive root and rejected when it escapes. SVG is
    returned with a sandboxing-friendly mime so callers must add CSP headers.
    """
    candidate = unquote(asset_path or "").replace("\\", "/").lstrip("/")
    resolved = posixpath.normpath(candidate)
    if not resolved or resolved.startswith(("/", "..")) or resolved.split("/")[0] == "..":
        raise ValueError("Asset path escapes the archive.")
    suffix = posixpath.splitext(resolved)[1].lower()
    mime = IMAGE_MIME.get(suffix)
    if mime is None:
        raise ValueError("Unsupported asset type.")
    with zipfile.ZipFile(Path(epub_path)) as archive:
        try:
            info = archive.getinfo(resolved)
        except KeyError as exc:
            raise FileNotFoundError(resolved) from exc
        if info.is_dir():
            raise FileNotFoundError(resolved)
        if info.file_size > MAX_ASSET_BYTES:
            raise ValueError("Asset too large.")
        with archive.open(info) as handle:
            return handle.read(MAX_ASSET_BYTES + 1)[:MAX_ASSET_BYTES], mime


def chapter_blocks(paths: dict, epub_path: str | Path, chapter_id: int, *, asset_prefix: str = "") -> list[dict]:
    """Pair original chunks with their translations for one EPUB chapter."""
    items = chapters(epub_path)
    if chapter_id < 0 or chapter_id >= len(items):
        raise IndexError("Chapter not found.")

    chunks_path = Path(paths["chunks_file"])
    translations_path = Path(paths["translations_file"])
    chunks_data = json.loads(chunks_path.read_text(encoding="utf-8"))
    translations = (
        json.loads(translations_path.read_text(encoding="utf-8"))
        if translations_path.is_file()
        else {}
    )

    chapter_path = posixpath.normpath(items[chapter_id]["path"])
    chapter_map = chunks_data.get("chapter_map", {})
    blocks = []
    for chunk_id, original in chunks_data.get("chunks", []):
        chunk_id = str(chunk_id)
        mapping = chapter_map.get(chunk_id, {})
        mapped_path = posixpath.normpath(str(mapping.get("item", "")).replace("\\", "/"))
        same_chapter = (
            mapped_path == chapter_path
            or chapter_path.endswith(f"/{mapped_path}")
            or mapped_path.endswith(f"/{chapter_path}")
        )
        if not same_chapter:
            continue
        blocks.append({
            "id": chunk_id,
            "position": int(mapping.get("pos", len(blocks))),
            "original": str(original),
            "translation": str(translations.get(chunk_id, "")),
            "original_html": sanitize_html(str(original), asset_base=mapped_path, asset_prefix=asset_prefix),
            "translation_html": sanitize_html(str(translations.get(chunk_id, "")), asset_base=mapped_path, asset_prefix=asset_prefix),
        })

    return sorted(blocks, key=lambda item: item["position"])

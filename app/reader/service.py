"""Safe extraction of readable chapters from translated EPUB archives."""
from __future__ import annotations

import posixpath
import re
import zipfile
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

SAFE_TAGS = {"p", "div", "span", "em", "strong", "b", "i", "u", "br", "blockquote", "pre", "code", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6", "a", "img", "table", "thead", "tbody", "tr", "th", "td", "hr", "sup", "sub"}
SAFE_ATTRS = {"a": {"href", "title"}, "img": {"src", "alt", "title"}, "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"}}
VOID_TAGS = {"br", "hr", "img"}


class _SafeHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "embed", "form"}:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in SAFE_TAGS:
            return
        allowed = []
        for key, value in attrs:
            key, value = key.lower(), value or ""
            if key not in SAFE_ATTRS.get(tag, set()):
                continue
            if key in {"href", "src"} and re.match(r"^\s*(?:javascript|data):", value, re.I):
                continue
            allowed.append(f' {key}="{escape(value, quote=True)}"')
        self.parts.append(f"<{tag}{''.join(allowed)}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "embed", "form"} and self._skip_depth:
            self._skip_depth -= 1
        elif not self._skip_depth and tag in SAFE_TAGS and tag not in VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(escape(data))


def sanitize_html(content: str) -> str:
    parser = _SafeHtml()
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


def chapter(epub_path: str | Path, chapter_id: int) -> dict:
    items = chapters(epub_path)
    if chapter_id < 0 or chapter_id >= len(items):
        raise IndexError("Chapter not found.")
    item = items[chapter_id]
    with zipfile.ZipFile(Path(epub_path)) as archive:
        content = archive.read(item["path"]).decode("utf-8", errors="replace")
    return {"id": item["id"], "title": item["title"], "html": sanitize_html(content)}

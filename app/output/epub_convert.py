import base64
import json
import mimetypes
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

import pypandoc

from app.output.rtl_docx import fix_docx_typography
from app.output.rtl_pdf import write_html_pdf
from app.output.structure import CLASS_EMPHASIS

#: The tags the rewrite can introduce, and the ones it must not duplicate.
_EMPHASIS_TAGS = frozenset({"i", "b"})
def _epub_language(input_path, fallback):
    with zipfile.ZipFile(input_path) as archive:
        container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
        rootfile = container.find(".//{*}rootfile")
        if rootfile is not None:
            package = ElementTree.fromstring(archive.read(rootfile.attrib["full-path"]))
            language = package.find(".//{http://purl.org/dc/elements/1.1/}language")
            if language is not None and language.text:
                return language.text.strip().split("-")[0].upper()
    return fallback.upper()


def _embed_markdown_images(node, media_root):
    if isinstance(node, dict):
        if node.get("t") == "Image":
            target = node["c"][-1]
            image_path = Path(target[0]).resolve()
            if image_path.is_relative_to(media_root) and image_path.is_file():
                media_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
                encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
                target[0] = f"data:{media_type};base64,{encoded}"
        for value in node.values():
            _embed_markdown_images(value, media_root)
    elif isinstance(node, list):
        for value in node:
            _embed_markdown_images(value, media_root)


class _EmphasisRewriter(HTMLParser):
    """Emit the document with emphasis classes expressed as real tags.

    ## Why a parser and not a substitution

    The first three attempts used a regular expression over the *opening* tag, and
    each one dropped the span's text on the floor -- because the text is not in
    the tag. Replacing ``<span class="txit">`` with ``<span class="txit"><i>``
    leaves the closing ``</span>`` orphaned and the emphasis wrapping nothing:

        <span class="txit"><i></span>فکر می‌کنم</i>

    Pandoc reads that as a broken inline, drops the run, and the output has
    *zero* italic runs. A rewrite that silently removes the thing it adds is
    worse than one that does nothing, and it is invisible unless the output is
    read back.

    An element's text lives between its tags, so rewriting an element means
    rewriting the whole element. That is what this does: it re-emits every start
    and end tag, and passes the data through untouched.

    Nesting is tracked so the real tags are closed at the right place and in the
    right order, and so a span already inside an ``<i>`` does not get a second
    one.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self.changed = False
        #: Open real tags pushed by each class-emphasis span, innermost last.
        self._open: list[tuple[str, list[str]]] = []
        #: Tags currently open in the source, so a redundant one is not added.
        self._tags_in_force: list[str] = []

    def _tags_for(self, classes: str) -> list[str]:
        # Folded, because a publisher may write .TXIT. The table is lower case,
        # so a plain lookup misses half the books -- and misses them silently,
        # which is the whole failure this module exists to prevent.
        flags = {
            CLASS_EMPHASIS[name.lower()]
            for name in classes.split()
            if name.lower() in CLASS_EMPHASIS
        }
        if not flags:
            return []
        tags = []
        if flags & {"italic", "bold-italic"}:
            tags.append("i")
        if flags & {"bold", "bold-italic"}:
            tags.append("b")
        return tags

    def handle_starttag(self, tag: str, attrs) -> None:
        # Every tag is recorded, not just the ones this class adds. A span inside
        # an <i> is already italic, and adding a second <i> inside the first is
        # markup nobody asked for -- and the check has to know what the *source*
        # already had open, which is why the stack holds all of it.
        if tag in _EMPHASIS_TAGS:
            self._tags_in_force.append(tag)
        self.out.append(self._render_start(tag, attrs))

    def handle_startendtag(self, tag: str, attrs) -> None:
        # `<span class="txit"/>` has no content to emphasise, so it is left as it
        # is rather than given an empty pair of tags.
        self.out.append(self._render_start(tag, attrs, self_closing=True))

    def _render_start(self, tag: str, attrs, self_closing: bool = False) -> str:
        attributes = dict(attrs)
        pieces = []
        for name, value in attrs:
            if value is None:
                pieces.append(name)
            else:
                pieces.append(f'{name}="{value}"')
        opening = f"<{tag}" + ("".join(f" {p}" for p in pieces)) + ("/>" if self_closing else ">")

        if tag != "span":
            return opening
        tags = self._tags_for(attributes.get("class", ""))
        if not tags:
            return opening
        # Already inside one of these -- in the source, or from an outer span this
        # rewriter opened. Either way the class is redundant here.
        wanted = [tag for tag in tags if tag not in self._tags_in_force]
        if not wanted:
            return opening
        self.changed = True
        for tag in wanted:
            self._tags_in_force.append(tag)
        self._open.append((attributes.get("class", ""), list(wanted)))
        return opening + "".join(f"<{t}>" for t in wanted)

    def handle_endtag(self, tag: str) -> None:
        # Close what this span opened, before the span itself, in mirror order:
        # `<i><b>` closes as `</b></i>`.
        closers = ""
        if self._open and tag == "span":
            _classes, tags = self._open.pop()
            for opened in tags:
                if opened in self._tags_in_force:
                    self._tags_in_force.remove(opened)
            closers = "".join(f"</{t}>" for t in reversed(tags))
        elif tag in _EMPHASIS_TAGS and tag in self._tags_in_force:
            # The source closing one of its own. Removed from the innermost
            # occurrence, so a mismatched close cannot empty the whole stack.
            self._tags_in_force.remove(tag)
        self.out.append(closers + f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.out.append(data)

    def handle_entityref(self, name: str) -> None:
        self.out.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.out.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.out.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.out.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.out.append(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        self.out.append(f"<![{data}]>")


def _rewrite_emphasis(content: str) -> tuple[str, bool]:
    """The chapter with its emphasis classes turned into tags."""
    parser = _EmphasisRewriter()
    try:
        parser.feed(content)
        parser.close()
    except Exception:
        # A malformed chapter must not lose the document. Returning it untouched
        # means the reader sees the same emphasis problem they had, rather than a
        # chapter that has lost its markup.
        return content, False
    return "".join(parser.out), parser.changed


def _normalise_emphasis(input_path: Path, destination: Path) -> Path:
    """A copy of the book with publisher classes rewritten as real markup.

    ## Why

    Pandoc reads ``<i>``, ``<b>`` and ``<em>``. It does not read
    ``<span class="txit">`` -- a class, not a tag -- so every run of interior
    voice in a generation of e-books arrives as plain text.

    Measured on a real three-chapter book, through the conversion route:

    * ``<span class="txit">``  -- 37 occurrences -- **0 italic runs** in the DOCX
    * ``<span class="smallcaps">`` -- 10 -- 10 small-caps runs, because
      `app.output.structure.CLASS_EMPHASIS` maps that one and pandoc does not
      mind the rest of the class list

    Rewriting the class to a tag before pandoc sees the file fixes it, and fixes
    the Markdown and PDF outputs too, since they go through the same reader. The
    parser that knows the convention is `app.output.structure`; this only
    applies it to a file on disk.

    The rewrite is byte-for-byte elsewhere: only the class attribute of a known
    emphasis span is touched, and the class list is left intact so a style that
    carries other meaning is not narrowed.
    """
    if not CLASS_EMPHASIS:
        return input_path

    with zipfile.ZipFile(input_path) as source:
        entries = {name: source.read(name) for name in source.namelist()}

    changed = False
    rewritten: dict[str, bytes] = {}
    for name, blob in entries.items():
        if not name.lower().endswith((".xhtml", ".html", ".htm")):
            rewritten[name] = blob
            continue
        try:
            content = blob.decode("utf-8")
        except UnicodeDecodeError:
            # A chapter the converter skips too, so leaving it alone is right.
            rewritten[name] = blob
            continue

        updated, touched = _rewrite_emphasis(content)
        changed = changed or touched
        rewritten[name] = updated.encode("utf-8")

    if not changed:
        return input_path

    destination.mkdir(parents=True, exist_ok=True)
    # A *file* inside the directory, named after the book. The first version
    # passed the directory straight to ZipFile, which tries to open it as a file
    # and raises PermissionError -- on every book that had emphasis to rewrite,
    # which is the case the function exists for.
    target_path = destination / input_path.name
    with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as target:
        # mimetype first and stored, or the result is not a valid EPUB and
        # pandoc's reader may reject it.
        target.writestr(
            zipfile.ZipInfo("mimetype"), entries["mimetype"],
            compress_type=zipfile.ZIP_STORED,
        )
        for name, blob in rewritten.items():
            if name == "mimetype":
                continue
            target.writestr(name, blob)
    return target_path


def write_epub_output(input_path: Path, path: Path, output_format: str, to_lang: str):
    # The emphasis-normalised copy is built once and used by every branch below,
    # so the DOCX, the Markdown and the PDF all see the same text. Built inside a
    # TemporaryDirectory because it is a throwaway: it exists only to be read.
    with TemporaryDirectory(prefix="kalima-epub-") as scratch:
        normalised = _normalise_emphasis(input_path, Path(scratch))
        return _write_with(input_path, normalised, path, output_format, to_lang)


def _write_with(input_path: Path, normalised: Path, path: Path, output_format: str, to_lang: str):
    if output_format == "translated_pdf":
        html = pypandoc.convert_file(
            str(normalised), "html5", format="epub",
            extra_args=["--standalone", "--embed-resources"], sandbox=True,
        )
        return write_html_pdf(html, path)

    if output_format == "markdown":
        with TemporaryDirectory(prefix="kalima-epub-media-") as temporary:
            media_root = Path(temporary).resolve()
            document = json.loads(pypandoc.convert_file(
                str(normalised), "json", format="epub",
                extra_args=[f"--extract-media={media_root}"], sandbox=True,
            ))
            _embed_markdown_images(document, media_root)
            pypandoc.convert_text(
                json.dumps(document), "markdown", format="json", outputfile=str(path),
                extra_args=["--wrap=none"], sandbox=True,
            )
        return path

    language = _epub_language(input_path, to_lang)
    direction = "rtl" if language in {"FA", "AR", "UR", "HE", "PS", "SD"} else "ltr"
    pypandoc.convert_file(
        str(normalised),
        "docx" if output_format == "docx" else "markdown",
        format="epub",
        outputfile=str(path),
        extra_args=["--wrap=none", f"--metadata=dir:{direction}"],
        sandbox=True,
    )
    return fix_docx_typography(path)

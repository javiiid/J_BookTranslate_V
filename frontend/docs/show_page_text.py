"""Turn a rendered page into the text a reader would actually see.

An HTML dump is hard to read past tags, and the question is "can a person read
this", which is a question about the text and its sizes, not about the markup.
This prints the page as a plain outline with the computed font size beside each
line, using the built stylesheet to resolve the sizes.

It is the closest thing to a screenshot available without a browser, and it is
what settled the 11px caption question.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

UI = Path(r"D:\J_BookTranslate_V\frontend\ui")
PREVIEW = UI / "scripts" / "preview"

# --- the built stylesheet, reduced to a size lookup -----------------------
css_file = next(p for p in (UI / "dist" / "assets").iterdir() if p.name.endswith(".css"))
css = css_file.read_text(encoding="utf-8")

SCALE = {f"--text-{n}": float(v) * 16 for n, v in re.findall(r"--text-([a-z0-9-]+):\s*([\d.]+)rem", css)}


def rem(value: str):
    match = re.fullmatch(r"([\d.]+)rem", value.strip())
    return float(match.group(1)) * 16 if match else None


def size_of(value: str):
    """A font-size declaration to pixels, whether it is a rem or a token."""
    value = value.strip()
    pixels = rem(value)
    if pixels is not None:
        return pixels
    token = re.fullmatch(r"var\((--text-[a-z0-9-]+)\)", value)
    if token:
        return SCALE.get(token.group(1))
    return None


# Every single-class rule that sets a font size: the component classes as well as
# the utilities. Reading only the `text-[length:…]` utilities made table cells
# report the size of the heading above them, because nothing inside a <td>
# carries a utility and the size was simply inherited -- 20px for a table that
# actually renders at 14px. The component classes are declared with
# `var(--text-small)` rather than a rem, so both forms are resolved.
CLASS_SIZE: dict[str, float] = {}
for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
    if "," in selector or " " in selector or not selector.startswith("."):
        continue
    size = re.search(r"font-size:\s*([^;}]+)", body)
    if not size:
        continue
    name = selector[1:].replace("\\", "")
    if name in CLASS_SIZE:
        continue
    pixels = size_of(size.group(1))
    if pixels:
        CLASS_SIZE[name] = pixels

for token, pixels in SCALE.items():
    CLASS_SIZE[f"text-[length:var({token})]"] = pixels

DEFAULT_PX = 15.0

# Tags that start a new visual line. Text inside one of these is its own run:
# without this, a table cell at the same size as the heading above it merged into
# the heading, and the report showed one long line where the page has a table.
BLOCK = {
    "address", "article", "aside", "blockquote", "div", "dl", "dd", "dt",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
    "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
    "section", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
}


class Outline(HTMLParser):
    """Collect text with the nearest declared font size."""

    # <head> is removed before parsing, so only these can still appear inline.
    SKIP = {"script", "style", "svg", "path", "rect", "g"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = []
        self.stack = []
        self.size = None
        self.skipping = 0
        self.block = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
            self.stack.append(None)
            return
        if self.skipping:
            self.stack.append(None)
            return
        attributes = dict(attrs)
        # Carry the inherited size down, so a cell with no size class of its own
        # still reports the size it actually renders at. Dropping it to None --
        # which an earlier version did -- silently deleted every table row from
        # the output, because nothing inside a <td> carries a size class.
        self.size = self.size or DEFAULT_PX
        for cls in (attributes.get("class") or "").split():
            if cls in CLASS_SIZE:
                self.size = CLASS_SIZE[cls]
                break
        if attributes.get("style"):
            match = re.search(r"font-size:\s*([\d.]+)px", attributes["style"])
            if match:
                self.size = float(match.group(1))
        self.stack.append(self.size)
        self.block = tag in BLOCK

    def handle_startendtag(self, tag, attrs):
        # A self-closing tag never has text, and counting it as an open skip
        # would swallow the rest of the document. <link>, <img> and <input> are
        # written without a slash in this markup, which is what made the earlier
        # counter drift: <meta> is void, never closed, and pushed the skip count
        # up by one with nothing to bring it back down.
        self.stack.append(None)

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        if self.stack:
            self.size = self.stack.pop()

    def handle_data(self, data):
        if self.skipping:
            return
        text = " ".join(data.split())
        if not text:
            return
        # A run inside a block element always starts a new line in the report.
        # The merge below only joins what the browser would render inline.
        if self.block:
            self.lines.append((self.size or DEFAULT_PX, text))
        else:
            self.lines.append((self.size or DEFAULT_PX, text, True))


def strip_head(html: str) -> str:
    """Drop <head> entirely: the inlined stylesheet is not page copy."""
    return re.sub(r"<head\b[^>]*>[\s\S]*?</head>", "", html, flags=re.I)


for name in sys.argv[1:] or ["reader", "account"]:
    path = PREVIEW / f"{name}-light.html"
    if not path.is_file():
        print(f"  missing {path}")
        continue
    parser = Outline()
    parser.feed(strip_head(path.read_text(encoding="utf-8")))

    # Merge only the fragments the browser renders inline, so the report reads
    # like the page instead of one line per element.
    merged = []
    for entry in parser.lines:
        size, text = entry[0], entry[1]
        inline = len(entry) > 2
        if (
            inline
            and merged
            and merged[-1][0] == size
            and len(merged[-1][1]) < 220
            and not merged[-1][1].endswith((".", ":", "؟"))
        ):
            merged[-1] = (size, f"{merged[-1][1]} {text}")
        else:
            merged.append((size, text))

    print()
    print("=" * 78)
    print(f"  {name} — light theme, as the reader sees it")
    print("=" * 78)
    smallest = min((s for s, _ in merged), default=0)
    for size, text in merged:
        flag = "  <-- SMALL" if size < 12 else ""
        print(f"  {size:>5.1f}px  {text[:66]}{flag}")
    print("-" * 78)
    print(f"  {len(merged)} text run(s), smallest {smallest:.1f}px")

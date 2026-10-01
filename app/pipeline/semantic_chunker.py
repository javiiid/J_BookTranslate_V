"""
Semantic chunking for EPUB and HTML sources.

Why this exists
---------------
The chunker this replaces, ``html_processor.split_html_by_paragraph``, splits on
the literal string ``"</p>"``. That has three consequences, all measured against
the real function in ``docs/probe_chunker.py``:

1. **It does not round-trip.** ``EPUBHandler.save_translated_epub`` reassembles a
   document by re-running the splitter and overwriting chunks by position, then
   joining with ``"".join(chunks)``. So the split has to be lossless. It is not:
   a ``<div class="para">`` had a ``</p>`` appended to it, and a paragraph over the
   limit lost characters -- 1196 became 1193, 996 became 974 -- because the
   sentence path rejoined with a single space and the pieces had no wrapper.

2. **It only sees ``<p>``.** Most EPUBs are written with ``<div>``, ``<li>`` or no
   wrapper at all. For those, the whole chapter is one pseudo-paragraph, the limit
   never applies per paragraph, and the cut lands wherever the character count
   happens to fall -- which is the mid-dialogue cut this module is meant to fix.

3. **It counts characters.** The limit is a token budget on the provider's side.
   10,000 characters is roughly 2,500 tokens of English and roughly 8,000 of
   Persian, so the effective chunk size varied by a factor of three with the
   source language and nobody was told.

What this does instead
----------------------
Blocks are found by scanning tags, not by matching a closing string, and every
block is a *slice* of the original document. Markup is never rewritten, so
``"".join(chunk.html for chunk in chunks) == html`` holds exactly, which is the
invariant the save path depends on. Size is measured in estimated tokens. A block
too large for the budget is divided at sentence boundaries *in the text nodes
only*, so a cut never lands inside a tag and never welds two words together.

Context
-------
``context_window`` attaches the plain text of the preceding blocks to each chunk.
The model sees them; only the chunk itself is stored and translated. This is what
lets a pronoun or a repeated term resolve, and it costs no extra API call -- the
context rides in the same request.

A note on tokens
----------------
There is no tokenizer in this environment (no tiktoken, no transformers), so
:func:`estimate_tokens` is a documented heuristic rather than a measurement. It is
deliberately biased high, because underestimating a chunk means the provider
rejects the request and the whole chunk is lost, while overestimating only makes
chunks slightly smaller. :func:`set_token_counter` exists so a real tokenizer can
replace it without touching the chunker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable, Iterable


# ============================================================
# Token estimation
# ============================================================

# Characters per token, by script. These are the ratios that matter for the
# languages this project is used with, taken from how BPE tokenizers behave on
# each script rather than from a single average:
#
#   Latin     ~4 chars/token. English prose with spaces.
#   Arabic    ~2 chars/token. Persian and Arabic letters are multi-byte and a
#             word is several tokens; under-counting here is what overruns a
#             provider's context window.
#   CJK       ~1.5 chars/token. Nearly every ideograph is its own token.
#
# Markup is counted separately and conservatively: a tag is not natural language
# but it is still sent, and `<span class="x">` is easily 10 tokens.
_CHARS_PER_TOKEN = {"cjk": 1.5, "arabic": 2.0, "latin": 4.0}
_MARKUP_CHARS_PER_TOKEN = 3.0

_TOKEN_COUNTER: Callable[[str], int] | None = None


def set_token_counter(counter: Callable[[str], int] | None) -> None:
    """Replace the heuristic with a real tokenizer.

    ``counter`` maps text to a token count. Passing ``None`` restores the
    heuristic. Called once at startup if a tokenizer is available; the chunker
    itself does not care which is in use.
    """
    global _TOKEN_COUNTER
    _TOKEN_COUNTER = counter


_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]")
_ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_TAG = re.compile(r"<[^>]*>")
_ENTITY = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);")
_WHITESPACE = re.compile(r"\s+")


def estimate_tokens(text: str) -> int:
    """Estimated token count for a string of markup and prose."""
    if _TOKEN_COUNTER is not None:
        return _TOKEN_COUNTER(text)

    if not text:
        return 0

    markup = _TAG.findall(text)
    markup_tokens = sum(len(part) for part in markup) / _MARKUP_CHARS_PER_TOKEN

    # An entity is one or two tokens but many characters, so it is priced as
    # tokens rather than characters. Dropping it from the prose count is what
    # keeps `&nbsp;` from being read as fifteen characters of text.
    prose = _TAG.sub(" ", text)
    prose = _ENTITY.sub(" x ", prose)

    cjk = len(_CJK.findall(prose))
    arabic = len(_ARABIC.findall(prose))
    latin = len(prose) - cjk - arabic

    prose_tokens = (
        cjk / _CHARS_PER_TOKEN["cjk"]
        + arabic / _CHARS_PER_TOKEN["arabic"]
        + latin / _CHARS_PER_TOKEN["latin"]
    )

    return int(markup_tokens + prose_tokens) + 1


# ============================================================
# Plain text
# ============================================================

_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>[\s\S]*?</\1\s*>", re.IGNORECASE)
_COMMENT = re.compile(r"<!--[\s\S]*?-->")
_DOCTYPE = re.compile(r"<![^>]*>")
_BR = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_BLOCK_END = re.compile(
    r"</\s*(p|div|li|h[1-6]|blockquote|section|article|tr|td|th|dd|dt)\s*>",
    re.IGNORECASE,
)

_ENTITIES = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&apos;": "'",
    "&hellip;": "…",
    "&mdash;": "—",
    "&ndash;": "–",
    "&rsquo;": "’",
    "&lsquo;": "‘",
    "&rdquo;": "”",
    "&ldquo;": "“",
}


def strip_tags(html: str) -> str:
    """The visible text of a fragment, for measuring and for model context.

    Block-level tags become spaces so that ``<p>a</p><p>b</p>`` does not read as
    ``ab``, and a numeric character reference is decoded rather than dropped, so a
    Persian string full of ``&#1585;`` still counts as Persian.
    """
    if not html:
        return ""

    text = _SCRIPT_STYLE.sub(" ", html)
    text = _COMMENT.sub(" ", text)
    text = _DOCTYPE.sub(" ", text)
    text = _BR.sub(" ", text)
    text = _TAG.sub(" ", text)

    for entity, replacement in _ENTITIES.items():
        text = text.replace(entity, replacement)

    def _numeric(match: re.Match) -> str:
        # The capture group holds the digits only -- the "#" is outside it. An
        # earlier version stripped the first character as if it were a "#", so
        # `&#1585;` decoded 585, which is "ɹ", and the Persian came out as Latin
        # Extended glyphs. The token estimate then read Persian as Latin text and
        # under-counted it by a factor of two.
        body = match.group(1)
        try:
            if body[:1] in {"x", "X"}:
                return chr(int(body[1:], 16))
            return chr(int(body))
        except (ValueError, OverflowError):
            return match.group(0)

    text = re.sub(r"&#([0-9]+|[xX][0-9a-fA-F]+);", _numeric, text)
    return _WHITESPACE.sub(" ", text).strip()


# ============================================================
# Block segmentation
# ============================================================

# Elements that carry a paragraph's worth of meaning and so make sensible
# boundaries. Everything else -- <span>, <em>, <a>, <sup> -- is inline and must
# never cause a split.
#
# The container elements are here so that a list stays whole. Leaving `ul` out
# meant each `<li>` opened its own top-level block while the `<ul>` went to the
# loose-text run beside it, so the opening tag and its items landed in different
# chunks -- and chunks are translated concurrently and reassembled by position.
# A wrapper in one chunk and its contents in another is how a book loses its
# list.
BLOCK_TAGS = frozenset({
    # leaf blocks
    "p", "li", "dd", "dt", "blockquote", "pre", "figcaption",
    "h1", "h2", "h3", "h4", "h5", "h6",
    # containers, so their children stay inside them
    "div", "section", "article", "aside", "header", "footer", "nav", "main",
    "ul", "ol", "dl", "table", "figure", "details", "summary",
    "tr", "td", "th", "tbody", "thead", "tfoot", "caption",
})

# Elements with no closing tag. Splitting the document on one of these, or
# tracking depth through one, produces nonsense.
VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

# Block-level voids: each is its own tiny block rather than being glued to a
# neighbour.
BLOCK_VOID_TAGS = frozenset({"hr", "br"})

# Tags that wrap other blocks and are therefore *transparent*: the segmenter
# descends through them rather than stopping, because a chapter wrapper is not a
# paragraph. Making them boundaries is what produced 97.7% mid-block cuts on a
# real book, where every chapter sits inside <section><div class="chapter">.
TRANSPARENT_TAGS = frozenset({
    "html", "body", "div", "section", "article", "main", "aside",
    "header", "footer", "nav", "figure", "center", "address",
    "blockquote", "q", "cite",
    "ul", "ol", "dl", "table", "thead", "tbody", "tfoot", "tr", "colgroup",
})

# The leaves: they hold text that belongs together and can stand alone as a unit
# of work. `li`, `td` and `th` are here and their containers are transparent, so a
# list item is a boundary while the `<ul>` around it is not.
BLOCK_TAGS = frozenset({
    "p", "li", "dd", "dt", "pre", "figcaption", "caption",
    "h1", "h2", "h3", "h4", "h5", "h6", "td", "th",
})

# Elements with no closing tag.
VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

# Block-level voids: each is its own tiny block rather than glued to a neighbour.
BLOCK_VOID_TAGS = frozenset({"hr", "br"})

# Elements whose content is never prose. Descended into so their bytes are seen,
# but what is inside is never promoted to a block: a `<title>` is not a paragraph,
# and treating its text as one opened a block at the enclosing `<html>` and
# emitted the head of the document twice.
METADATA_TAGS = frozenset({"head", "title", "meta", "link", "base"})


@dataclass(frozen=True)
class _Tok:
    """One token, with its exact span in the source."""

    kind: str
    """open | close | empty | text | other"""

    name: str
    start: int
    end: int


class _Scanner(HTMLParser):
    """Collects the token stream. Nothing is interpreted here."""

    def __init__(self, html: str) -> None:
        # convert_charrefs=False keeps entity references as their own text, so an
        # entity can never be silently decoded and then lost on the way out.
        super().__init__(convert_charrefs=False)
        self.html = html
        self.tokens: list[tuple[str, str, int]] = []
        self._line_starts = [0]
        for index, char in enumerate(html):
            if char == "\n":
                self._line_starts.append(index + 1)

    def _at(self) -> int:
        line, column = self.getpos()
        if 1 <= line <= len(self._line_starts):
            return min(self._line_starts[line - 1] + column, len(self.html))
        return len(self.html)

    def handle_starttag(self, tag, attrs):
        self.tokens.append(("open", tag, self._at()))

    def handle_startendtag(self, tag, attrs):
        self.tokens.append(("empty", tag, self._at()))

    def handle_endtag(self, tag):
        self.tokens.append(("close", tag, self._at()))

    def handle_data(self, data):
        if data:
            self.tokens.append(("text", "", self._at()))

    def handle_entityref(self, name):
        self.tokens.append(("text", "", self._at()))

    def handle_charref(self, name):
        self.tokens.append(("text", "", self._at()))

    def handle_comment(self, data):
        self.tokens.append(("other", "", self._at()))

    def handle_decl(self, decl):
        self.tokens.append(("other", "", self._at()))

    def handle_pi(self, data):
        self.tokens.append(("other", "", self._at()))

    def unknown_decl(self, data):
        self.tokens.append(("other", "", self._at()))


def _token_stream(html: str) -> list[_Tok]:
    """The document as tokens whose spans provably tile it.

    Each token's end is the *next* token's start, and the last one ends at the end
    of the document. The parser walks the source contiguously, so this is exact
    and it means no byte can fall between two tokens and be dropped -- which is
    the property the save path depends on and the thing a regex scanner kept
    losing.
    """
    scanner = _Scanner(html)
    try:
        scanner.feed(html)
        scanner.close()
    except Exception:  # noqa: BLE001
        # A malformed document still has to come back intact. Whatever was
        # tokenised so far is used, and the remainder becomes one text token.
        pass

    raw = scanner.tokens
    tokens: list[_Tok] = []
    for index, (kind, name, start) in enumerate(raw):
        if start > len(html):
            continue
        end = raw[index + 1][2] if index + 1 < len(raw) else len(html)
        if end < start:
            continue
        tokens.append(_Tok(kind, name.lower(), start, end))
    return tokens


@dataclass(frozen=True)
class Block:
    """One leaf block, as an exact slice of the source."""

    html: str
    """The source markup, byte for byte. Never rewritten."""

    text: str
    """Visible text, for token counting and for model context."""

    tag: str
    """The element that opened it, or ``""`` for loose text."""

    start: int
    """Offset in the document, so a caller can map a chunk back to the source."""

    def __len__(self) -> int:
        return len(self.html)


def segment_blocks(html: str) -> list[Block]:
    """Split a document into leaf blocks, preserving every byte.

    A block is a leaf element -- a paragraph, a heading, a list item, a table cell
    -- from its opening tag to its matching close, together with any markup that
    was pending when it started and had nowhere else to go: a chapter's
    ``<section>``, a list's ``<ul>``, the whitespace between two paragraphs. That
    is what keeps a wrapper from landing in a different chunk from its contents.

    Transparent containers are descended through rather than treated as blocks: a
    ``<section>`` holding a chapter is not a unit of translation, and treating it
    as one is what reduced a real book to 97.7% mid-block cuts.

    Elements in :data:`METADATA_TAGS` are descended into but their content is
    never promoted to a block.

    ``"".join(b.html for b in segment_blocks(doc)) == doc`` holds for any input.
    """
    if not html:
        return []

    tokens = _token_stream(html)
    if not tokens:
        return [
            Block(html=html, text=strip_tags(html), tag="", start=0)
        ]

    blocks: list[Block] = []
    stack: list[str] = []
    block_start: int | None = None
    block_tag = ""
    # Bytes seen outside any block that must travel with the next one.
    lead_start: int | None = None

    def emit(start: int, end: int, tag: str) -> None:
        if end <= start:
            return
        piece = html[start:end]
        blocks.append(
            Block(html=piece, text=strip_tags(piece), tag=tag, start=start)
        )

    def open_block(at: int, name: str) -> None:
        """Start a block at ``at``, or earlier if markup is pending."""
        nonlocal block_start, block_tag, lead_start
        block_start = lead_start if lead_start is not None else at
        block_tag = name
        lead_start = None

    def close_block(end: int) -> None:
        nonlocal block_start, block_tag
        if block_start is not None:
            emit(block_start, end, block_tag)
        block_start = None
        block_tag = ""

    for index, tok in enumerate(tokens):
        # A token with no element around it and no block open: decide whether it
        # is a boundary or something to carry.
        inside_block = any(name in BLOCK_TAGS for name in stack)
        in_metadata = any(name in METADATA_TAGS for name in stack)
        # The end of the run of tokens that starts here and is outside any block.
        # A block ends at the first token that is not part of it, so this is where
        # the previous slice stops.
        run_end = tokens[index].start

        if tok.kind == "text":
            if inside_block or in_metadata:
                continue
            if not strip_tags(html[tok.start:tok.end]):
                # Whitespace or an entity between blocks: carry it.
                if lead_start is None:
                    lead_start = tok.start
                continue

            # Prose with no leaf block around it, whether at the very top of the
            # document or inside a transparent wrapper. The block starts at the
            # container's opening tag when there is one, so
            # `<div class="para">text</div>` is not split into a text block and a
            # separate closing-tag block -- the model would be handed the text
            # without the element that gives it meaning.
            #
            # A container's closing tag is not absorbed into the same block. Doing
            # so needed a second emit, and the pending-markup bookkeeping after it
            # was off by one, which cost 176,850 characters across the book. It
            # stays a separate zero-text block instead, which the packer joins to
            # its neighbour, and the round trip is exact either way.
            start = lead_start if lead_start is not None else tok.start
            stop = tok.end
            while stop < len(html) and html[stop] not in "<":
                stop += 1
            emit(start, stop, "")
            lead_start = None
            # Everything consumed up to `stop` belongs to that block.
            while index + 1 < len(tokens) and tokens[index + 1].start < stop:
                index += 1
            continue

        if tok.kind == "other":
            if inside_block:
                continue
            if lead_start is None:
                lead_start = tok.start
            continue

        if tok.kind == "empty":
            name = tok.name
            if not inside_block and name in BLOCK_VOID_TAGS:
                open_block(tok.start, name)
                close_block(tok.end)
                continue
            if inside_block:
                continue
            if lead_start is None:
                lead_start = tok.start
            continue

        if tok.kind == "open":
            name = tok.name
            if not inside_block and name in BLOCK_VOID_TAGS:
                open_block(tok.start, name)
                close_block(tok.end)
                continue
            if not inside_block and name in BLOCK_TAGS:
                open_block(tok.start, name)
                stack.append(name)
                continue
            if lead_start is None and not inside_block:
                lead_start = tok.start
            if name not in VOID_TAGS:
                stack.append(name)
            continue

        # close
        name = tok.name
        if name in stack:
            depth = len(stack)
            while stack:
                popped = stack.pop()
                if popped == name:
                    break
            emptied = not stack
        else:
            depth = 0
            emptied = not stack

        if any(item in BLOCK_TAGS for item in stack):
            # Still inside a leaf block: this close is part of its slice.
            continue

        if block_start is not None:
            close_block(tok.end)
        elif emptied and depth and not in_metadata:
            # A transparent container that held no block of its own --
            # `<div class="para">Some text.</div>`, which is how a great many EPUBs
            # mark a paragraph. The container is the unit here.
            open_block(tok.start, name)
            close_block(tok.end)
        elif lead_start is None:
            lead_start = tok.start

    # Tail. An unterminated block takes the remainder; otherwise whatever is left
    # over becomes a final slice, so the last paragraph's trailing markup and
    # whitespace are not dropped.
    if block_start is not None:
        close_block(len(html))
    elif lead_start is not None:
        emit(lead_start, len(html), "")

    return blocks


# ============================================================
# Sentence splitting, in text nodes only
# ============================================================

# A sentence ends at ., ! or ? (or the Persian equivalents) followed by space and
# something that can start a sentence. Abbreviations and decimals are protected
# the same way the existing splitter protects them, because a chapter full of
# "Dr." and "3.14" is the normal case, not the exception.
_ABBREVIATIONS = (
    "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.", "St.",
    "etc.", "vs.", "viz.", "cf.", "al.",
    "e.g.", "i.e.", "ex.", "no.", "vol.", "pp.", "p.", "ch.",
)
_DOT_SENTINEL = "\x00DOT\x00"
_SENTENCE_BREAK = re.compile(r"(?<=[.!?؟!۔])\s+(?=[\"'«“(\[]?[A-ZÀ-ɏ؀-ۿ])")


def _plain_with_offsets(html: str) -> tuple[str, list[int]]:
    """The visible text, plus where each of its characters sits in the markup.

    Every character of the result maps to exactly one index in ``html``, so a
    position in the text can be turned back into a position in the markup. The
    tag text itself is not included: a sentence boundary is a property of prose,
    and letting the splitter reason about ``class="indent"`` is how a cut ends up
    inside an attribute.
    """
    characters: list[str] = []
    offsets: list[int] = []
    for tok in _token_stream(html):
        if tok.kind != "text":
            continue
        for offset in range(tok.start, tok.end):
            characters.append(html[offset])
            offsets.append(offset)
    return "".join(characters), offsets


def _sentence_ends(plain: str) -> list[int]:
    """Indices in ``plain`` just past the end of each sentence.

    Found on the protected copy for the *test* only -- a cut must not be
    suggested after "Dr." or inside "3.14" -- and then reported as positions in
    the original. Working on the protected copy and slicing the original is what
    broke the offsets: the sentinel is longer than what it replaced, so every
    position after the first substitution was wrong.
    """
    protected = plain
    for abbreviation in _ABBREVIATIONS:
        protected = re.sub(
            re.escape(abbreviation),
            abbreviation.replace(".", _DOT_SENTINEL),
            protected,
            flags=re.IGNORECASE,
        )
    protected = re.sub(r"(?<=\d)\.(?=\d)", _DOT_SENTINEL, protected)

    # Walk the two strings together, tracking how many sentinel characters have
    # been substituted, so a match position in `protected` can be expressed as a
    # position in `plain`.
    ends: list[int] = []
    shift = 0
    pi = 0
    pj = 0
    for match in _SENTENCE_BREAK.finditer(protected):
        target = match.start()
        while pi < len(plain) and pj < target:
            if protected[pj] == _DOT_SENTINEL[0] and plain[pi] == ".":
                # A run of sentinel characters standing in for one dot.
                pj += 1
                while pj < len(protected) and protected[pj] == _DOT_SENTINEL[0]:
                    pj += 1
                shift -= 1
                continue
            pi += 1
            pj += 1
        # `match.start()` is on the whitespace. The sentence ends before it, so
        # back off to the last non-space character -- that is the cut.
        end = pi
        while end > 0 and plain[end - 1].isspace():
            end -= 1
        if end > 0 and (not ends or ends[-1] < end):
            ends.append(end)
    return ends


def split_markup_sentences(html: str) -> list[str]:
    """Split a fragment at sentence ends, never inside a tag.

    A cut is only ever made at a position in a *text node*, and each piece keeps
    the tags that opened before it, so ``"".join(split_markup_sentences(x)) == x``
    exactly -- whitespace at the cut included. That equality is the whole point:
    the chunker packs pieces back together with ``"".join`` and the save path
    reassembles the document from the chunks, so anything a cut drops is gone for
    good. It is what welded "A. B." into "A.B." in a shipped book.
    """
    if not html:
        return []

    plain, offsets = _plain_with_offsets(html)
    if not plain:
        return [html]

    ends = _sentence_ends(plain)
    if not ends:
        return [html]

    pieces: list[str] = []
    previous = 0
    for end in ends:
        if end <= previous:
            continue
        # The piece runs from the last boundary to the end of this sentence's
        # text. The whitespace that follows stays with the *next* piece, which is
        # where it belongs -- the source had it there, and the source is what the
        # reassembled document has to match.
        stop = offsets[end]
        # Extend past any closing tags that follow immediately, so the element is
        # closed in the piece that opened it.
        while stop < len(html) and html[stop] == "<":
            close = html.find(">", stop)
            if close == -1:
                break
            stop = close + 1
        pieces.append(html[previous:stop])
        previous = stop

    pieces.append(html[previous:])
    return [piece for piece in pieces if piece]


# ============================================================
# The chunker
# ============================================================

@dataclass(frozen=True)
class SemanticChunk:
    """A unit of work: what to translate, and what came before it."""

    index: int
    """Position in the document, from 0."""

    html: str
    """Exactly the source markup. This is what gets stored and translated."""

    text: str
    """Visible text of :attr:`html`."""

    context_before: str = ""
    """Plain text of the preceding blocks. Sent to the model, never translated."""

    block_range: tuple[int, int] = (0, 0)
    """Which blocks this chunk covers, half-open."""

    estimated_tokens: int = 0

    split_from_single_block: bool = False
    """True when one oversized block had to be divided. Worth reporting: it is
    the only case where a paragraph boundary was not available."""

    @property
    def has_context(self) -> bool:
        return bool(self.context_before)


@dataclass
class SemanticChunker:
    """Paragraph-first chunking with a context window.

    ``max_tokens`` is a budget on estimated tokens, not characters.
    ``context_window`` is how many preceding blocks of plain text to attach; 0
    disables context entirely, which is the old behaviour.

    The chunker holds no state between calls. That matters because
    :meth:`chunk` is called once per document while a book has hundreds, and an
    earlier version accumulated sentence pieces on ``self``, which leaked one
    document's fragments into the next.
    """

    max_tokens: int = 1200
    context_window: int = 2

    def tokens(self, text: str) -> int:
        # Resolved through the module global every time, so `set_token_counter`
        # takes effect without re-constructing the chunker.
        return estimate_tokens(text)

    # -- public API ----------------------------------------------------

    def chunk(self, html: str) -> list[SemanticChunk]:
        """Chunk one document.

        Guarantees:

        * ``"".join(c.html for c in chunks) == html`` for any non-empty input.
          The save path depends on this; it reassembles by re-splitting and
          overwriting by position.
        * no chunk is empty, and no block is dropped.
        * a cut only ever falls on a block boundary, or -- when a single block is
          over budget on its own -- on a sentence boundary inside it.
        """
        if not html:
            return []

        blocks = segment_blocks(html)
        if not blocks:
            return []

        # Each entry is one contiguous slice of the source, with the block it
        # starts in, so context can be recovered without re-parsing.
        pieces: list[_Piece] = []
        for position, block in enumerate(blocks):
            cost = self.tokens(block.html)

            if cost <= self.max_tokens:
                pieces.append(_Piece(block.html, position, position, False))
                continue

            # Over budget on its own. Cut it at sentence boundaries, and record
            # that this block could not stay paragraph-aligned.
            sentences = split_markup_sentences(block.html)
            if len(sentences) <= 1:
                # No sentence boundary to cut on. Emitting it whole is better than
                # cutting mid-word, and `split_from_single_block` reports it.
                pieces.append(_Piece(block.html, position, position, True))
                continue
            for sentence in sentences:
                if sentence:
                    pieces.append(_Piece(sentence, position, position, True))

        return self._pack(blocks, pieces)

    def chunk_document(
        self,
        documents: Iterable[str],
    ) -> list[SemanticChunk]:
        """Chunk several documents, renumbering the result from zero.

        A chapter boundary is a real boundary for the reader but not for the
        narrative: a pronoun at the top of chapter two often refers back to
        chapter one. Context is *not* carried across the join, because each
        document is chunked on its own; carry it explicitly with
        :func:`carry_context` if a book needs it.
        """
        merged: list[SemanticChunk] = []
        for html in documents:
            for chunk in self.chunk(html):
                merged.append(
                    SemanticChunk(
                        index=len(merged),
                        html=chunk.html,
                        text=chunk.text,
                        context_before=chunk.context_before,
                        block_range=chunk.block_range,
                        estimated_tokens=chunk.estimated_tokens,
                        split_from_single_block=chunk.split_from_single_block,
                    )
                )
        return merged

    # -- internals -----------------------------------------------------

    def _pack(
        self,
        blocks: list[Block],
        pieces: list[_Piece],
    ) -> list[SemanticChunk]:
        """Fill chunks up to the budget.

        The budget is the only thing that closes a chunk.

        There was a ``min_tokens`` parameter here, meant to stop a chapter ending
        in a one-line paragraph from costing a whole request. It was removed
        because with correct packing it has nothing to do: a chunk can only come
        out undersized at the very end of a document, and its predecessor is by
        construction full or within one block of the budget, so there is never
        room to fold it back. Measuring a real book across six budgets from 800
        to 8,000 tokens, the merge fired zero times.

        An earlier version of it was worse than inert: it closed a chunk as soon
        as the running total *reached* the floor, so every chunk came out at
        exactly 200 tokens and a 1,200-token budget was never used. That alone
        turned 470 chunks into 1,376.
        """
        groups: list[list[_Piece]] = []
        current: list[_Piece] = []
        current_cost = 0

        for piece in pieces:
            cost = self.tokens(piece.html)

            if current and current_cost + cost > self.max_tokens:
                groups.append(current)
                current = []
                current_cost = 0

            current.append(piece)
            current_cost += cost

        if current:
            groups.append(current)

        chunks: list[SemanticChunk] = []
        for group in groups:
            html_piece = "".join(piece.html for piece in group)
            chunks.append(
                SemanticChunk(
                    index=len(chunks),
                    html=html_piece,
                    text=strip_tags(html_piece),
                    context_before=self._context_for(
                        blocks, group[0].block_start
                    ),
                    block_range=(
                        group[0].block_start,
                        group[-1].block_end + 1,
                    ),
                    estimated_tokens=self.tokens(html_piece),
                    split_from_single_block=any(
                        piece.split for piece in group
                    ),
                )
            )
        return chunks

    def _context_for(self, blocks: list[Block], start: int) -> str:
        """Plain text of up to ``context_window`` blocks before ``start``.

        Walks backwards over blocks with text, so a run of whitespace or a rule
        does not consume one of the window slots.
        """
        if self.context_window <= 0:
            return ""

        parts: list[str] = []
        remaining = self.context_window
        position = start - 1
        while position >= 0 and remaining > 0:
            text = blocks[position].text
            if text:
                parts.append(text)
                remaining -= 1
            position -= 1
        return " ".join(reversed(parts))


@dataclass(frozen=True)
class _Piece:
    """A contiguous slice of the source, tagged with the block it came from."""

    html: str
    block_start: int
    block_end: int
    split: bool


def carry_context(
    chunks: list[SemanticChunk],
    window: int,
) -> list[SemanticChunk]:
    """Re-derive each chunk's context from the chunks before it.

    For a book assembled from several documents, where each document was chunked
    in isolation and the first chunks of a chapter have no context of their own.
    Uses the already-extracted plain text, so no re-parsing.
    """
    if window <= 0:
        return chunks

    out: list[SemanticChunk] = []
    for position, chunk in enumerate(chunks):
        parts: list[str] = []
        remaining = window
        cursor = position - 1
        while cursor >= 0 and remaining > 0:
            text = chunks[cursor].text
            if text:
                parts.append(text)
                remaining -= 1
            cursor -= 1
        context = " ".join(reversed(parts)) or chunk.context_before
        out.append(
            SemanticChunk(
                index=chunk.index,
                html=chunk.html,
                text=chunk.text,
                context_before=context,
                block_range=chunk.block_range,
                estimated_tokens=chunk.estimated_tokens,
                split_from_single_block=chunk.split_from_single_block,
            )
        )
    return out


# ============================================================
# Rendering a chunk for the model
# ============================================================

CONTEXT_HEADER = (
    "The passage above is context from earlier in the same document. "
    "Use it to resolve pronouns, tone and recurring names. "
    "Do not translate it and do not include it in your answer. "
    "Translate only the passage below."
)


def render_for_model(chunk: SemanticChunk) -> tuple[str, str]:
    """Return ``(context, payload)`` for a chunk.

    Split rather than concatenated so the caller can put the context in its own
    message. Concatenating it into the payload would work too, but it makes the
    boundary between "translate this" and "this is only for you" invisible to
    anyone reading a transcript of the request.
    """
    context = chunk.context_before.strip()
    if not context:
        return "", chunk.html
    return f"{CONTEXT_HEADER}\n\n{context}", chunk.html

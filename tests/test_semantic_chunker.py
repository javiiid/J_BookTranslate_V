"""Tests for the semantic chunker.

The invariant that matters most is round-trip fidelity. ``
EPUBHandler.save_translated_epub`` reassembles a document by re-running the
splitter and overwriting chunks by position, then joining with ``"".join``. So
the split has to be lossless, and the chunker this replaces was not: a ``<div
class="para">`` gained a ``</p>``, and an over-budget paragraph lost 22 characters
with its words welded together.

The round-trip property is therefore asserted over every fixture, not just
described. A chunker that quietly drops a space is a data-loss bug that shows up
as a broken book, months later, with nothing pointing back here.
"""
import re
import sys

import pytest

from app.pipeline.semantic_chunker import (
    SemanticChunker,
    carry_context,
    estimate_tokens,
    render_for_model,
    segment_blocks,
    split_markup_sentences,
    strip_tags,
)


# ============================================================
# Fixtures
# ============================================================

DIV_PARAGRAPHS = (
    '<div class="para">First sentence. Second one.</div>\n'
    '<div class="para">Third sentence here.</div>'
)

HEADING_AND_RULE = (
    "<h1>The Chapter</h1><p>Body text.</p><hr/><p>More body.</p>"
)

MIXED = (
    "<h1>Chapter One</h1>"
    "<p>The cartographer unrolled the map.</p>"
    "<blockquote><p>A map is an argument.</p></blockquote>"
    "<ul><li>One.</li><li>Two.</li></ul>"
    "<p>She weighed the corners.</p>"
)

PERSIAN = (
    "<p>نقشه را گشود — شکننده و نمک‌زده — و گوشه‌هایش را سنگین کرد.</p>"
    "<p>خط ساحلی اشتباه بود. نه اشتباهی جزئی.</p>"
)

INLINE_MARKUP = (
    "<p>He said <em>loudly</em> that it mattered. "
    'Then she replied <a href="#fn1">"not yet"</a>. '
    "The map stayed folded.</p>"
)

SCRIPT_AND_STYLE = (
    "<style>p{color:red}</style>"
    "<script>var a = 1 < 2;</script>"
    "<p>Real prose.</p>"
)

ENTITIES = "<p>Caf&eacute; &amp; bazaar &#1585;&#1608;&#1583;</p>"


def _big_paragraph(sentences: int = 60) -> str:
    body = " ".join(f"Sentence number {n} is here." for n in range(sentences))
    return f"<p>{body}</p>"


@pytest.fixture
def semantic_free_chunker():
    """A chunker with a budget no fixture exceeds, so nothing is split.

    Used to assert properties of *packing* rather than of sentence splitting.
    """
    return SemanticChunker(max_tokens=4000)


def _big_list(items: int = 8, words: int = 200) -> str:
    """A list too large for a small budget, so the packer has to divide it."""
    return (
        "<ul>"
        + "".join(
            f"<li>{'word ' * words}Item {n} of the list.</li>"
            for n in range(items)
        )
        + "</ul>"
    )


# ============================================================
# strip_tags
# ============================================================

class TestStripTags:

    def test_empty(self):
        assert strip_tags("") == ""

    def test_drops_inline_markup(self):
        assert strip_tags("<p>Hello <em>there</em></p>") == "Hello there"

    def test_block_tags_become_spaces(self):
        # Without this, <p>a</p><p>b</p> reads as "ab" and the token count is
        # wrong by one character in a way that only shows up on dense pages.
        assert strip_tags("<p>a</p><p>b</p>") == "a b"

    def test_ignores_script_and_style_content(self):
        text = strip_tags(SCRIPT_AND_STYLE)
        assert "Real prose." in text
        assert "color:red" not in text
        assert "var a" not in text

    def test_decodes_named_entities(self):
        assert strip_tags("<p>a &amp; b</p>") == "a & b"

    def test_decodes_numeric_entities(self):
        # A Persian string written as numeric references must still count as
        # Persian, or the token estimate is wrong by a factor of four.
        text = strip_tags("<p>&#1585;&#1608;&#1583;</p>")
        assert "رود" in text

    def test_leaves_an_unknown_entity_alone(self):
        assert "&notarealentity;" in strip_tags("<p>&notarealentity;</p>")

    def test_collapses_whitespace(self):
        assert strip_tags("<p>a\n\n   b</p>") == "a b"


# ============================================================
# estimate_tokens
# ============================================================

class TestEstimateTokens:

    def test_empty_is_zero(self):
        assert estimate_tokens("") == 0

    def test_is_monotonic(self):
        short = estimate_tokens("one two three")
        long = estimate_tokens("one two three " * 10)
        assert long > short

    def test_persian_costs_more_than_latin(self):
        # 40 characters of Persian is far more tokens than 40 of English. The
        # old chunker treated them as equal, which is how a Persian book
        # overran the provider's window while looking within budget.
        latin = "word " * 8
        persian = "کلمه " * 8
        assert estimate_tokens(persian) > estimate_tokens(latin)

    def test_markup_is_counted(self):
        assert estimate_tokens('<span class="a">' * 20) > 20

    def test_a_real_counter_replaces_the_heuristic(self):
        from app.pipeline import semantic_chunker as module

        try:
            module.set_token_counter(lambda text: 7)
            assert estimate_tokens("anything at all") == 7
        finally:
            module.set_token_counter(None)
        assert estimate_tokens("anything at all") != 7


# ============================================================
# segment_blocks
# ============================================================

class TestSegmentBlocks:

    def test_empty(self):
        assert segment_blocks("") == []

    def test_finds_div_paragraphs(self):
        # The defect this replaces: splitting on "</p>" cannot see these at all.
        #
        # `div` is a *transparent* container, so the scan descends through it --
        # otherwise a <div> wrapping a whole chapter became one 53,000-token block.
        # A div holding no leaf block therefore contributes its text as a block in
        # its own right, and its closing tag as a zero-text block beside it.
        #
        # Known limitation, asserted deliberately: the closing tag is not merged
        # into the text block. Absorbing it needs a second emit, and the
        # pending-markup bookkeeping after that was off by one and cost 176,850
        # characters across a real book. The packer joins the zero-text block to
        # its neighbour, so the model still sees the element and its text
        # together, and the round trip is exact.
        blocks = segment_blocks(DIV_PARAGRAPHS)
        assert [b.text for b in blocks if b.text] == [
            "First sentence. Second one.",
            "Third sentence here.",
        ]
        assert "".join(b.html for b in blocks) == DIV_PARAGRAPHS

    def test_a_div_paragraph_keeps_its_opening_tag(self):
        blocks = segment_blocks('<div class="para">Some text.</div>')
        # The element the text belongs to travels with it, so the model is not
        # handed a bare sentence stripped of its container.
        assert blocks[0].html.startswith('<div class="para">')
        assert blocks[0].text == "Some text."

    def test_heading_is_its_own_block(self):
        blocks = segment_blocks(HEADING_AND_RULE)
        assert [b.tag for b in blocks if b.tag] == ["h1", "p", "hr", "p"]

    def test_nested_inline_stays_inside_its_block(self):
        blocks = segment_blocks(INLINE_MARKUP)
        assert len(blocks) == 1
        assert "<em>loudly</em>" in blocks[0].html

    def test_nested_blocks_do_not_break(self):
        blocks = segment_blocks(MIXED)
        # blockquote and ul are transparent, so what is found is the leaves: the
        # heading, the paragraph, the paragraph inside the blockquote, the two
        # list items, the `</ul>` that wraps no block of its own, and the last
        # paragraph. Nothing is swallowed -- which a depth counter got wrong, and
        # which treating `<ul>` as a boundary would have got wrong in the other
        # direction by separating the list from its items.
        assert [b.tag for b in blocks] == [
            "h1", "p", "p", "blockquote", "li", "li", "ul", "p",
        ]
        assert "".join(b.html for b in blocks) == MIXED
        # The <p> inside the <blockquote> still travels with it.
        assert any("<blockquote>" in b.html for b in blocks)

    def test_a_multi_paragraph_blockquote_is_not_one_block(self):
        # The reason blockquote is transparent: a quotation of five paragraphs
        # treated as a single leaf would exceed the budget and then be cut at
        # sentence boundaries, losing the paragraph structure inside it.
        html = "<blockquote>" + "".join(f"<p>Quoted {n}.</p>" for n in range(3)) + "</blockquote>"
        blocks = segment_blocks(html)
        assert [b.tag for b in blocks] == ["p", "p", "p", "blockquote"]
        assert "".join(b.html for b in blocks) == html
    def test_a_container_never_lands_in_a_different_chunk(self):
        # The reason transparent containers travel with their first child: a
        # wrapper in one chunk and its contents in another is how a book loses
        # its list.
        big = _big_list()
        chunker = SemanticChunker(max_tokens=400)
        chunks = chunker.chunk(big)
        assert len(chunks) > 1, "the budget should divide this"
        for chunk in chunks:
            opened = chunk.html.count("<ul>")
            closed = chunk.html.count("</ul>")
            # A chunk may open the list or close it, never both.
            assert not (opened and closed), chunk.html
        assert "".join(c.html for c in chunks) == big

    def test_a_list_and_its_items_reassemble(self):
        big = _big_list()
        chunks = SemanticChunker(max_tokens=400).chunk(big)
        # Every item is present exactly once, whatever the chunk boundaries were.
        for n in range(8):
            assert sum(f"Item {n} of the list." in c.text for c in chunks) == 1
        assert "".join(c.html for c in chunks) == big

    def test_script_tags_do_not_unbalance_depth(self):
        # "<" inside a script would otherwise be read as a tag.
        blocks = segment_blocks(SCRIPT_AND_STYLE)
        assert "".join(b.html for b in blocks) == SCRIPT_AND_STYLE
        assert any("Real prose." in b.text for b in blocks)

    def test_unclosed_block_is_taken_to_the_end(self):
        html = "<p>One<p>Two"
        blocks = segment_blocks(html)
        assert "".join(b.html for b in blocks) == html

    def test_stray_close_tag_does_not_unbalance_depth(self):
        html = "<div>a</span>b</div><p>after</p>"
        blocks = segment_blocks(html)
        assert "".join(b.html for b in blocks) == html
        assert any("after" in b.text for b in blocks)

    def test_void_tags_do_not_open_a_block(self):
        html = '<p>a<br/>b<img src="x.png"/>c</p>'
        blocks = segment_blocks(html)
        assert "".join(b.html for b in blocks) == html
        assert len([b for b in blocks if b.tag]) == 1


# ============================================================
# split_markup_sentences
# ============================================================

class TestSplitMarkupSentences:

    def test_empty(self):
        assert split_markup_sentences("") == []

    def test_single_sentence(self):
        assert split_markup_sentences("<p>One.</p>") == ["<p>One.</p>"]

    def test_splits_between_sentences(self):
        pieces = split_markup_sentences("<p>One. Two. Three.</p>")
        assert len(pieces) == 3
        assert "".join(pieces) == "<p>One. Two. Three.</p>"

    def test_never_cuts_inside_a_tag(self):
        html = '<p title="a. b">One. Two.</p>'
        for piece in split_markup_sentences(html):
            # Every piece must have balanced angle brackets, or the output
            # document is malformed.
            assert piece.count("<") == piece.count(">")

    def test_keeps_inline_markup_with_its_text(self):
        html = "<p>He said <em>loudly</em>. She agreed. They left.</p>"
        pieces = split_markup_sentences(html)
        assert "".join(pieces) == html
        assert any("<em>loudly</em>" in p for p in pieces)

    def test_does_not_split_a_decimal(self):
        html = "<p>The value is 3.14 exactly. Next one.</p>"
        pieces = split_markup_sentences(html)
        assert len(pieces) == 2
        assert "3.14" in pieces[0]

    def test_does_not_split_an_abbreviation(self):
        html = "<p>Dr. Smith arrived. He was late.</p>"
        pieces = split_markup_sentences(html)
        assert len(pieces) == 2
        assert "Dr. Smith arrived." in pieces[0]

    def test_splits_persian(self):
        html = "<p>این جمله کوتاه است. این جمله بلندتر است. پایان.</p>"
        assert len(split_markup_sentences(html)) == 3

    def test_keeps_the_space_at_every_cut(self):
        """The bug this file was missing.

        `_SENTENCE_BREAK` consumes the whitespace, so slicing on
        `match.start()` dropped it, and the chunker rejoins with `"".join`. The
        result came out of the pipeline with words welded together.

        Every earlier round-trip assertion passed because the fixtures were small
        enough that no block was over budget, so the sentence splitter never ran.
        This one is deliberately over budget.
        """
        html = "<p>" + " ".join(f"Sentence number {n} is here." for n in range(40)) + "</p>"
        chunks = SemanticChunker(max_tokens=120).chunk(html)
        assert len(chunks) > 1, "the budget should force a sentence split"
        # The joined output has to be byte-identical to the input.
        assert "".join(c.html for c in chunks) == html
        # And no seam may weld a word to a tag.
        joined = "".join(c.html for c in chunks)
        assert "</p>" + "<p>" not in joined
        import re as _re

        welded = _re.findall(r"</[a-zA-Z][^>]*>(?=[^\s<])", joined)
        assert not welded, f"{len(welded)} seam(s) with no space: {welded[:3]}"

    def test_a_cut_between_two_sentences_keeps_the_space(self):
        # The smallest possible reproduction, so the failure mode is unmistakable.
        #
        # The space is *kept*, and it leads the following piece rather than
        # trailing the previous one. That is the only arrangement that survives
        # `"".join`: a space at the end of a piece is just as easy to strip in
        # transit as one in the middle, and putting it first means the source's
        # own layout is reproduced exactly.
        pieces = split_markup_sentences("<p>One. Two. Three.</p>")
        assert len(pieces) == 3
        assert pieces[0] == "<p>One."
        assert pieces[1] == " Two."
        assert pieces[2] == " Three.</p>"
        assert "".join(pieces) == "<p>One. Two. Three.</p>"

    def test_newlines_at_a_cut_survive(self):
        # A real book separates paragraphs with a newline, so a cut there has to
        # keep it -- this is the shape the shipped book had.
        html = "<p>First one here. Second one here. Third one here.</p>"
        pieces = split_markup_sentences(html)
        assert "".join(pieces) == html

    def test_keeps_the_outer_tags_in_the_first_piece(self):
        # The old path emitted "<p>a. b." then "c. d.</p>" -- a <p> with no
        # closing tag followed by a </p> with no opening tag.
        pieces = split_markup_sentences("<p>One. Two.</p>")
        assert pieces[0].startswith("<p>")
        assert pieces[-1].rstrip().endswith("</p>")


# ============================================================
# SemanticChunker: the invariants
# ============================================================

class TestRoundTrip:

    """The property the save path depends on."""

    @pytest.mark.parametrize(
        "html",
        [
            DIV_PARAGRAPHS,
            HEADING_AND_RULE,
            MIXED,
            PERSIAN,
            INLINE_MARKUP,
            SCRIPT_AND_STYLE,
            ENTITIES,
            _big_paragraph(),
            "<p>only one</p>",
            "   ",
            "<div>a</div><div>b</div><div>c</div>",
        ],
    )
    def test_join_reproduces_the_document(self, html):
        chunker = SemanticChunker(max_tokens=200, context_window=2)
        chunks = chunker.chunk(html)
        assert "".join(c.html for c in chunks) == html

    def test_nothing_is_lost_on_a_realistic_chapter(self):
        chapter = "".join(
            f"<p>{'word ' * 60}Paragraph {n} here.</p>"
            for n in range(8)
        )
        chunker = SemanticChunker(max_tokens=300, context_window=2)
        chunks = chunker.chunk(chapter)
        assert "".join(c.html for c in chunks) == chapter

        # Compared as words, not as one string. `strip_tags` runs per chunk and
        # cannot know that a chunk boundary falls where a space belongs, so
        # joining the per-chunk text gives "Paragraph 2 here.word". That is a
        # property of the reporting, not a lost character: the HTML -- which is
        # what is stored and translated -- still carries the `</p><p>`.
        assert (
            " ".join(c.text for c in chunks).split()
            == strip_tags(chapter).split()
        )


class TestChunking:

    def test_empty_document(self):
        assert SemanticChunker().chunk("") == []

    def test_no_empty_chunks(self):
        chunks = SemanticChunker(max_tokens=150).chunk(MIXED)
        assert all(c.html for c in chunks)

    def test_indices_are_sequential(self):
        chunks = SemanticChunker(max_tokens=150).chunk(MIXED)
        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_respects_the_budget(self):
        chunks = SemanticChunker(max_tokens=250).chunk(_big_paragraph(60))
        assert len(chunks) > 1
        for chunk in chunks:
            # The last chunk of an over-budget block is allowed to exceed nothing;
            # no chunk should be wildly over.
            assert chunk.estimated_tokens <= 400, chunk.estimated_tokens

    def test_a_paragraph_under_budget_is_not_split(self):
        chunks = SemanticChunker(max_tokens=1200).chunk(MIXED)
        assert all(not c.split_from_single_block for c in chunks)

    def test_an_oversized_paragraph_is_flagged(self):
        chunks = SemanticChunker(max_tokens=120).chunk(_big_paragraph(60))
        assert any(c.split_from_single_block for c in chunks)

    def test_small_blocks_are_packed_not_split(self):
        # Ten short paragraphs under the minimum should not become ten API calls.
        html = "".join(f"<p>Short {n}.</p>" for n in range(10))
        chunks = SemanticChunker(max_tokens=1200).chunk(html)
        assert len(chunks) < 10
        assert "".join(c.html for c in chunks) == html

    def test_the_budget_is_what_closes_a_chunk(self):
        # A regression guard for the bug the real book exposed. There used to be
        # a `min_tokens` floor, and it closed a chunk as soon as the running total
        # *reached* it, so every chunk came out at exactly 200 tokens and a
        # 1,200-token budget was never used: the book produced 1,376 chunks where
        # 470 reach the budget. The parameter has since been removed, because
        # with correct packing it has nothing to do -- an undersized chunk can
        # only occur at the end of a document, where its predecessor is by
        # construction full.
        #
        # What is asserted here is the property that replaces it: the budget
        # decides, and a chunk uses the room it has.
        html = "".join(f"<p>{'word ' * 150}Filler {n}.</p>" for n in range(3))
        whole = SemanticChunker(max_tokens=600).chunk(html)
        assert len(whole) == 1
        assert whole[0].estimated_tokens > 500
        assert "".join(c.html for c in whole) == html

        # The same content under a budget below its size is divided, and the
        # division lands on paragraph boundaries.
        split = SemanticChunker(max_tokens=400).chunk(html)
        assert len(split) > 1
        for chunk in split:
            assert chunk.html.count("<p>") == chunk.html.count("</p>")
        assert "".join(c.html for c in split) == html

    def test_a_whole_document_under_budget_is_one_chunk(self):
        html = "<p>One.</p><p>Two.</p><p>Three.</p>"
        joined = SemanticChunker(max_tokens=4000).chunk(html)
        assert len(joined) == 1
        assert "".join(c.html for c in joined) == html

    def test_a_short_trailing_paragraph_does_not_become_its_own_chunk(self):
        # The behaviour `min_tokens` was invented for, achieved instead by the
        # budget being the only thing that closes a chunk: a chapter ending in a
        # one-line paragraph joins the chunk before it when there is room.
        html = (
            "".join(f"<p>{'word ' * 150}Body {n}.</p>" for n in range(3))
            + "<p>End.</p>"
        )
        chunks = SemanticChunker(max_tokens=600).chunk(html)
        assert "".join(c.html for c in chunks) == html
        # The tail is in the same chunk as real content, not alone.
        assert sum("End." in c.html for c in chunks) == 1
        assert chunks[-1].text.strip().endswith("End.")

    def test_block_range_covers_the_document(self):
        blocks = segment_blocks(MIXED)
        chunks = SemanticChunker(max_tokens=150).chunk(MIXED)
        assert chunks[0].block_range[0] == 0
        assert chunks[-1].block_range[1] <= len(blocks)

    def test_text_matches_html(self):
        for chunk in SemanticChunker(max_tokens=150).chunk(MIXED):
            assert chunk.text == strip_tags(chunk.html)

    def test_chunker_holds_no_state_between_documents(self):
        # An earlier version accumulated sentence pieces on self, which leaked one
        # document's fragments into the next.
        chunker = SemanticChunker(max_tokens=120)
        first = _big_paragraph(40)
        second = _big_paragraph(40)
        assert "".join(c.html for c in chunker.chunk(first)) == first
        assert "".join(c.html for c in chunker.chunk(second)) == second

    def test_a_second_run_is_identical(self):
        chunker = SemanticChunker(max_tokens=200)
        assert chunker.chunk(MIXED) == chunker.chunk(MIXED)


class TestContext:

    def test_disabled(self):
        chunks = SemanticChunker(max_tokens=150, context_window=0).chunk(MIXED)
        assert all(c.context_before == "" for c in chunks)
        assert all(not c.has_context for c in chunks)

    def test_first_chunk_has_no_context(self):
        chunks = SemanticChunker(max_tokens=150, context_window=2).chunk(MIXED)
        assert chunks[0].context_before == ""

    def test_later_chunks_see_preceding_text(self):
        # A long enough document that the budget actually divides it. With the
        # packing fixed, a budget of 90 swallowed all of MIXED whole, so this
        # asserted nothing.
        html = "".join(
            f"<p>Paragraph number {n} of the chapter, with enough words in it "
            f"to matter.</p>"
            for n in range(6)
        )
        chunks = SemanticChunker(max_tokens=40, context_window=2).chunk(html)
        assert len(chunks) > 1
        assert any(c.has_context for c in chunks[1:])

    def test_context_is_plain_text_not_markup(self):
        chunks = SemanticChunker(max_tokens=150, context_window=2).chunk(MIXED)
        for chunk in chunks:
            assert "<" not in chunk.context_before
            assert chunk.context_before == chunk.context_before.strip()

    def test_window_is_respected(self):
        html = "".join(
            f"<p>Paragraph number {n} of the chapter, with enough words in it "
            f"to matter.</p>"
            for n in range(6)
        )
        chunks = SemanticChunker(max_tokens=40, context_window=1).chunk(html)
        assert len(chunks) > 2
        for chunk in chunks[1:]:
            # At most one preceding paragraph's worth.
            assert chunk.context_before.count("Paragraph number") <= 1

    def test_context_skips_empty_blocks(self):
        # A rule between two paragraphs must not consume a context slot.
        html = "<p>First.</p><hr/><p>Second.</p><p>Third.</p>"
        chunks = SemanticChunker(max_tokens=15, context_window=1).chunk(html)
        assert len(chunks) >= 2
        last = chunks[-1]
        assert last.context_before == "Second."


class TestChunkDocument:

    def test_renumbers_from_zero(self):
        chunks = SemanticChunker(max_tokens=150).chunk_document([MIXED, PERSIAN])
        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_each_document_is_lossless(self):
        first = SemanticChunker(max_tokens=150).chunk(MIXED)
        second = SemanticChunker(max_tokens=150).chunk(PERSIAN)
        combined = SemanticChunker(max_tokens=150).chunk_document([MIXED, PERSIAN])
        assert [c.html for c in combined] == [c.html for c in first] + [c.html for c in second]

    def test_carry_context_across_a_book(self):
        chapters = SemanticChunker(max_tokens=40).chunk_document(
            [MIXED, PERSIAN]
        )
        assert not chapters[0].has_context
        carried = carry_context(chapters, window=1)
        # The first chunk of chapter two now sees the end of chapter one.
        boundary = next(
            i for i, c in enumerate(carried) if c.context_before == ""
        )
        assert boundary == 0
        assert carried[boundary + 1].has_context

    def test_carry_context_zero_is_a_no_op(self):
        chunks = SemanticChunker(max_tokens=150).chunk(MIXED)
        assert carry_context(chunks, window=0) == chunks


class TestRenderForModel:

    def test_without_context(self):
        chunk = SemanticChunker(max_tokens=1200).chunk(MIXED)[0]
        context, payload = render_for_model(chunk)
        assert context == ""
        assert payload == chunk.html

    def test_with_context(self):
        html = "".join(
            f"<p>Paragraph number {n} of the chapter, with enough words in it "
            f"to matter.</p>"
            for n in range(6)
        )
        chunks = SemanticChunker(max_tokens=40, context_window=2).chunk(html)
        with_context = next(c for c in chunks if c.has_context)
        context, payload = render_for_model(with_context)
        assert "Do not translate it" in context
        assert with_context.context_before in context
        # The payload must be the chunk alone: the stored translation has to
        # correspond to the chunk, not to the context that was sent with it.
        assert payload == with_context.html
        assert with_context.context_before not in payload

    def test_payload_is_identical_with_and_without_context(self):
        # The strongest form of the above: context changes what the model reads
        # and nothing else, so what it writes back maps to the same chunk.
        html = "".join(
            f"<p>Paragraph number {n} of the chapter, with enough words in it "
            f"to matter.</p>"
            for n in range(6)
        )
        without = SemanticChunker(max_tokens=40, context_window=0).chunk(html)
        with_ctx = SemanticChunker(max_tokens=40, context_window=2).chunk(html)
        assert len(without) == len(with_ctx)
        assert [c.html for c in without] == [c.html for c in with_ctx]


# ============================================================
# Comparison with the chunker being replaced
# ============================================================

class TestAgainstTheOldChunker:

    """The defects that motivated this, asserted so they cannot come back."""

    def test_the_old_chunker_did_not_round_trip(self):
        from app.pipeline.html_processor import split_html_by_paragraph

        html = DIV_PARAGRAPHS
        assert "".join(split_html_by_paragraph(html)) != html
        # And the new one does.
        assert "".join(c.html for c in SemanticChunker(max_tokens=1200).chunk(html)) == html

    def test_the_old_chunker_invents_a_closing_tag(self):
        from app.pipeline.html_processor import split_html_by_paragraph

        rebuilt = "".join(split_html_by_paragraph(DIV_PARAGRAPHS))
        assert rebuilt.endswith("</p>")
        assert not DIV_PARAGRAPHS.endswith("</p>")

    def test_the_old_chunker_loses_characters(self):
        from app.pipeline.html_processor import split_html_by_paragraph

        html = _big_paragraph(40)
        rebuilt = "".join(split_html_by_paragraph(html, 400))
        assert len(rebuilt) < len(html)

    def test_the_new_chunker_keeps_every_character(self):
        html = _big_paragraph(40)
        rebuilt = "".join(c.html for c in SemanticChunker(max_tokens=120).chunk(html))
        assert len(rebuilt) == len(html)

    def test_the_new_chunker_sees_div_paragraphs_as_boundaries(self):
        blocks = segment_blocks(DIV_PARAGRAPHS)
        assert len([b for b in blocks if b.text]) == 2

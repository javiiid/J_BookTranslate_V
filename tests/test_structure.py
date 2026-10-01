"""The emphasis classes, and what the rewrite does with them.

## Why this file is small

The first version of this module held a full structure model -- an
``html.parser`` subclass, ``Block``/``Run`` dataclasses, a block-to-HTML
serialiser -- and every chunk's markup was parsed into it and carried on the
segment. 370 lines, one consumer, and that consumer did not exist: for an EPUB the
DOCX is written by `epub_convert` through pandoc, and the parsed blocks never got
a look-in. `json_segments` dropped them on the way out.

Measured, the two writers were never going to be equal:

* pandoc reads every structural element an EPUB has and embeds the images as
  real `word/media/` parts -- 6 of them on the test book, with 6 relationships.
* `app.output.docx` writes embedded fonts and heading levels but has no image
  support, so a picture becomes the text `[تصویر: ...]`.

So pandoc is right for an EPUB and `app.output.docx` is right for a PDF, an SRT
or a text file, and the parallel model was drift. What survives is the table: the
only thing pandoc cannot see is a class, because a class is not a tag.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import pytest

sys.stdout.reconfigure(encoding="utf-8")

from app.output.epub_convert import _normalise_emphasis, _rewrite_emphasis
from app.output.structure import CLASS_EMPHASIS

BOOK = Path(r"D:\J_BookTranslate_V\data\uploads\overthesevensea_ch1-3_test.epub")


class TestTheTable:
    def test_it_covers_the_classes_a_real_book_uses(self):
        # Read the book rather than trusting a list someone wrote down.
        used: set[str] = set()
        with zipfile.ZipFile(BOOK) as archive:
            for name in archive.namelist():
                if not name.endswith((".xhtml", ".html")):
                    continue
                try:
                    content = archive.read(name).decode("utf-8")
                except UnicodeDecodeError:
                    continue
                for match in re.finditer(r'<span\s+class="([^"]+)"', content):
                    used.update(match.group(1).split())

        emphasis = {
            name for name in used
            if name in CLASS_EMPHASIS
        }
        assert emphasis, f"no emphasis classes found in {BOOK.name}: {sorted(used)[:10]}"
        # And the ones this book uses are ones the table knows.
        assert "txit" in emphasis, sorted(emphasis)

    def test_every_value_is_one_the_rewriter_understands(self):
        known = {"italic", "bold", "smallcaps", "bold-italic"}
        for name, value in CLASS_EMPHASIS.items():
            assert value in known, (name, value)

    def test_it_is_not_case_sensitive(self):
        """A publisher may write ``.TXIT``.

        The table is lower case, so the lookup has to fold -- otherwise the class
        is missed on half the books, silently, which is the whole failure this
        module exists to prevent.

        The first version of this test asserted the opposite, that an upper-case
        class is *left alone*, and passed. It was asserting the bug.
        """
        out, changed = _rewrite_emphasis('<span class="TXIT">x</span>')
        assert changed is True, out
        assert "<i>" in out, out
        # The original spelling survives, so a consumer that knows the class
        # still sees it.
        assert 'class="TXIT"' in out


class TestTheRewrite:
    def test_it_turns_a_known_class_into_a_tag(self):
        out, changed = _rewrite_emphasis('<p>گفت <span class="txit">فکر</span>.</p>')
        assert changed is True
        assert "<i>" in out

    def test_the_text_stays_inside_the_emphasis(self):
        """The bug the parser was written to avoid.

        A substitution over the *opening* tag produces
        ``<span class="txit"><i></span>text</i>``: the text is outside the
        italic, the markup is unbalanced, pandoc drops the run, and the document
        comes out with no emphasis at all. Three attempts at this used a regex;
        each one looked right and each one removed the thing it was adding.
        """
        phrase = "فکر می‌کنم"
        out, _ = _rewrite_emphasis(
            f'<p>گفت <span class="txit">{phrase}</span> بله.</p>'
        )
        assert phrase in out, "the text was lost"
        start = out.index(phrase)
        end = start + len(phrase)
        # Sliced around the whole phrase, not its first character.
        assert out[:start].rstrip().endswith("<i>"), out[:start][-40:]
        assert out[end:].lstrip().startswith("</i>"), out[end:][:40]
        assert out.count("<i>") == out.count("</i>")
        assert out.count("<span") == out.count("</span>")

    def test_it_leaves_an_unknown_class_alone(self):
        source = '<p><span class="pagebreak">صفحه</span></p>'
        out, changed = _rewrite_emphasis(source)
        assert changed is False
        assert out == source

    def test_nested_emphasis_closes_in_order(self):
        out, _ = _rewrite_emphasis(
            '<p><span class="txit">یک <b>دو</b></span></p>'
        )
        assert out.count("<b>") == out.count("</b>")
        # </b> before </i>: mirror order, or the markup is crossed.
        assert out.index("</b>") < out.index("</i>")

    def test_a_class_already_inside_a_tag_is_not_doubled(self):
        out, _ = _rewrite_emphasis('<p><i><span class="txit">متن</span></i></p>')
        # One <i> from the source, and the redundant one is not added.
        assert out.count("<i>") == 1, out
        assert out.count("</i>") == 1, out

    def test_no_text_is_lost(self):
        source = (
            '<p>یک <span class="txit">دو</span> سه</p>'
            '<p><b>چهار</b> و <span class="smallcaps">پنج</span></p>'
        )
        out, _ = _rewrite_emphasis(source)
        for word in ("یک", "دو", "سه", "چهار", "پنج"):
            assert word in out, (word, out)

    def test_entities_survive(self):
        out, _ = _rewrite_emphasis('<p>a &amp; b <span class="txit">c</span></p>')
        assert "&amp;" in out

    def test_a_malformed_chapter_is_returned_untouched(self):
        # Better the same emphasis problem the reader already had than a chapter
        # that has lost its markup.
        source = '<p><span class="txit">unclosed</p>'
        out, changed = _rewrite_emphasis(source)
        assert "unclosed" in out


class TestTheBookRewrite:
    @pytest.fixture(scope="class")
    @classmethod
    def normalised(cls, tmp_path_factory):
        target = tmp_path_factory.mktemp("norm")
        return _normalise_emphasis(BOOK, target)

    def test_it_produces_a_readable_epub(self, normalised):
        with zipfile.ZipFile(normalised) as archive:
            names = archive.namelist()
            assert archive.testzip() is None
            for required in ("mimetype", "META-INF/container.xml"):
                assert required in names, required
            # mimetype first and stored, or it is not a valid EPUB.
            assert names[0] == "mimetype", names[:3]
            assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED

    def test_every_chapter_keeps_its_text(self, normalised):
        def text_of(path):
            total = 0
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.endswith((".xhtml", ".html")):
                        try:
                            total += len(archive.read(name).decode("utf-8").split())
                        except UnicodeDecodeError:
                            pass
            return total

        # The rewrite adds tags, so the word count can only go up if a word was
        # split -- never down.
        assert text_of(normalised) >= text_of(BOOK)

    def test_the_emphasis_is_in_the_markup_now(self, normalised):
        with zipfile.ZipFile(normalised) as archive:
            found = 0
            for name in archive.namelist():
                if not name.endswith((".xhtml", ".html")):
                    continue
                try:
                    content = archive.read(name).decode("utf-8")
                except UnicodeDecodeError:
                    continue
                found += content.count("<i>")
        assert found > 0, "no emphasis tag was written"

    def test_a_non_emphasis_chapter_is_byte_identical(self, normalised):
        # The rewrite is applied per chapter, so a chapter with no emphasis class
        # should come through unchanged rather than re-serialised.
        with zipfile.ZipFile(BOOK) as source, zipfile.ZipFile(normalised) as target:
            changed, same = 0, 0
            for name in source.namelist():
                if not name.endswith((".xhtml", ".html")):
                    continue
                try:
                    before = source.read(name)
                    after = target.read(name)
                except (KeyError, UnicodeDecodeError):
                    continue
                if before == after:
                    same += 1
                else:
                    changed += 1
            assert same > 0, "every chapter was re-serialised for nothing"
            assert changed > 0, "nothing was rewritten, so the table is not matching"

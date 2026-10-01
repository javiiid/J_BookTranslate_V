"""What a publisher's CSS class means, so a converter can act on it.

## Why this is a module of one table

An earlier version of this file held a full structure model: an ``html.parser``
subclass, a ``Block``/``Run`` pair, and a block-to-HTML serialiser. It was used to
carry a parsed representation of every chunk on its segment, on the theory that
the structure should reach the writers.

It did not. For an EPUB the DOCX is written by :mod:`app.output.epub_convert`,
which reads the book through pandoc, and the parsed blocks never got a look-in.
The parser ran on every chunk, the blocks rode along in memory, and
:mod:`app.output.json_segments` dropped them on the way out. It was 370 lines of
model with one consumer, and that consumer did not exist.

What survived measurement is the table below, and nothing else:

* pandoc reads every structural element an EPUB has -- headings, lists,
  blockquotes, tables, images, links, ``b``/``i``/``sup``/``br`` -- and embeds the
  images as real ``word/media/`` parts. Measured on a real book: 6 image parts,
  6 relationships, 6 ``<a:blip>`` references.
* What pandoc cannot see is a *class*, because a class is not a tag.
  ``<span class="txit">`` is italic by convention across a generation of e-books
  and nothing in the markup says so.

So the knowledge this module exists to hold is the mapping from a class to its
meaning, and :mod:`app.output.epub_convert` applies it by rewriting the class
into the tag pandoc does read. One table, one consumer, and the reason it is
there is a measurement rather than a hunch.
"""

from __future__ import annotations

#: Inline emphasis: the publisher's class, and what it means to a reader.
#:
#: ``txit`` is interior voice -- a character's thoughts as distinct from their
#: speech. ``txbdit`` is emphasised dialogue. ``smallcaps`` is small capitals.
#: None of it is recoverable from the tag, which is ``<span>`` in all four cases.
#:
#: The values are the names this project uses for the effect, and
#: :class:`app.output.epub_convert._EmphasisRewriter` turns each into a real
#: ``<i>``, ``<b>`` or ``<span class="smallcaps">``.
CLASS_EMPHASIS: dict[str, str] = {
    "txit": "italic",            # thoughts / interior voice
    "italic": "italic",
    "i": "italic",
    "smallcaps": "smallcaps",
    "sc": "smallcaps",
    "bold": "bold",
    "b": "bold",
    # Emphasis applied to dialogue: both, rather than one or the other.
    "txbdit": "bold-italic",
}

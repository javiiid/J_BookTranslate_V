"""Which stage loses characters: segmentation or sentence splitting?

Round-trip holds for `segment_blocks` on hand-written fixtures and on the small
cases above, yet the chunker's output is 9,744 characters short on a real chapter.
So the loss is in `chunk`, and the only thing there that rewrites text is
`split_markup_sentences`.

This measures each stage separately on the real files, and then measures exactly
how much `split_markup_sentences` drops on its own.
"""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.pipeline.semantic_chunker import (
    SemanticChunker,
    segment_blocks,
    split_markup_sentences,
)

BOOK = Path(r"D:\J_BookTranslate_V\data\output\Hands-On_Large_Language_Models_FA.epub")
chunker = SemanticChunker(max_tokens=1200, context_window=2, min_tokens=200)

seg_ok = seg_bad = 0
chunk_ok = chunk_bad = 0
seg_loss = chunk_loss = 0
split_loss = 0
split_calls = 0

with zipfile.ZipFile(BOOK) as archive:
    for name in archive.namelist():
        if not name.endswith((".xhtml", ".html")):
            continue
        try:
            content = archive.read(name).decode("utf-8")
        except UnicodeDecodeError:
            continue
        if "<" not in content:
            continue

        rebuilt_segments = "".join(b.html for b in segment_blocks(content))
        if rebuilt_segments == content:
            seg_ok += 1
        else:
            seg_bad += 1
            seg_loss += len(rebuilt_segments) - len(content)

        rebuilt_chunks = "".join(c.html for c in chunker.chunk(content))
        if rebuilt_chunks == content:
            chunk_ok += 1
        else:
            chunk_bad += 1
            chunk_loss += len(rebuilt_chunks) - len(content)

        # Isolate the sentence splitter: for every block that needed splitting,
        # compare lengths.
        for block in segment_blocks(content):
            cost = chunker.tokens(block.html)
            if cost <= chunker.max_tokens:
                continue
            pieces = split_markup_sentences(block.html)
            if len(pieces) <= 1:
                continue
            split_calls += 1
            split_loss += len("".join(pieces)) - len(block.html)

print("=== stage 1: segment_blocks ===")
print(f"  lossless files : {seg_ok}/{seg_ok + seg_bad}")
print(f"  characters lost: {seg_loss}")
print()
print("=== stage 2: chunker.chunk ===")
print(f"  lossless files : {chunk_ok}/{chunk_ok + chunk_bad}")
print(f"  characters lost: {chunk_loss}")
print()
print("=== split_markup_sentences, in isolation ===")
print(f"  called on {split_calls} over-budget block(s)")
print(f"  characters lost: {split_loss}")
print()

# Show a single case.
with zipfile.ZipFile(BOOK) as archive:
    for name in archive.namelist():
        if not name.endswith((".xhtml", ".html")):
            continue
        try:
            content = archive.read(name).decode("utf-8")
        except UnicodeDecodeError:
            continue
        for block in segment_blocks(content):
            if chunker.tokens(block.html) <= chunker.max_tokens:
                continue
            pieces = split_markup_sentences(block.html)
            if len(pieces) <= 1:
                continue
            joined = "".join(pieces)
            if joined == block.html:
                continue
            print("=== one over-budget block ===")
            print(f"  block tag={block.tag!r}  {len(block.html)} chars -> {len(joined)}")
            for i, piece in enumerate(pieces[:3]):
                print(f"    [{i}] {piece[:90]!r}")
            print(f"    lost between pieces: {len(block.html) - len(joined)} chars")
            # Show exactly what sits at the seam.
            at = 0
            for piece in pieces[:-1]:
                at += len(piece)
            print(f"  source at the first seam: {block.html[at - 40:at + 40]!r}")
            raise SystemExit(0)

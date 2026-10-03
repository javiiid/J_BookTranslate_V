"""Why are 97.7% of chunks being cut inside a single block?

Three numbers from the measurement on the real book need explaining before the
chunker can be called done:

  * 97.7% of chunks had to be cut inside one block, so the paragraph-first
    strategy is not actually finding paragraphs in this book.
  * one chunk came out at 4782 tokens against a 1200 budget.
  * one file out of 24 still does not round-trip.

This looks at the block sizes and the tags, rather than guessing.
"""
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.pipeline.semantic_chunker import (
    BLOCK_TAGS,
    SemanticChunker,
    segment_blocks,
    split_markup_sentences,
    strip_tags,
)

BOOK = Path(r"D:\J_BookTranslate_V\data\output\Hands-On_Large_Language_Models_FA.epub")
chunker = SemanticChunker(max_tokens=1200, context_window=2, min_tokens=200)

tag_counts = Counter()
sizes = []
worst = None
lossy_file = None

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

        for block in segment_blocks(content):
            if not block.text:
                continue
            tag_counts[block.tag or "(loose text)"] += 1
            cost = chunker.tokens(block.html)
            sizes.append(cost)
            if worst is None or cost > worst[0]:
                worst = (cost, block, name)

        rebuilt = "".join(c.html for c in chunker.chunk(content))
        if rebuilt != content and lossy_file is None:
            lossy_file = (name, len(content), len(rebuilt))

print("=== what the blocks actually are ===")
total = sum(tag_counts.values())
for tag, count in tag_counts.most_common(10):
    print(f"  {tag:<16} {count:>5}  ({100 * count / total:.1f}%)")

print()
print("=== block sizes in estimated tokens ===")
sizes.sort()
print(f"  blocks            : {len(sizes)}")
print(f"  min {sizes[0]}  median {sizes[len(sizes) // 2]}  p95 {sizes[int(len(sizes) * 0.95)]}  max {sizes[-1]}")
over = [s for s in sizes if s > 1200]
print(f"  over the 1200 budget : {len(over)}  ({100 * len(over) / len(sizes):.1f}%)")
print(f"  of those, unsplittable: ", end="")

if worst:
    unsplittable = 0
    for block_cost, block, _ in [(worst[0], worst[1], worst[2])]:
        pass
    print("(see below)")

print()
print("=== the largest block ===")
if worst:
    cost, block, where = worst
    print(f"  {cost} tokens, tag={block.tag}, in {where}")
    print(f"  visible text: {len(block.text)} chars")
    print(f"  begins: {block.html[:150]!r}")
    pieces = split_markup_sentences(block.html)
    print(f"  sentence pieces found: {len(pieces)}")
    if len(pieces) <= 3:
        # Show why the splitter found nothing.
        text = block.text
        print(f"  first 200 chars of text: {text[:200]!r}")
        breaks = [c for c in ".!?؟!۔" if c in text]
        print(f"  sentence punctuation present: {breaks}")

print()
print("=== the file that does not round-trip ===")
if lossy_file:
    name, before, after = lossy_file
    print(f"  {name}")
    print(f"  {before} -> {after} chars ({after - before:+d})")
    with zipfile.ZipFile(BOOK) as archive:
        content = archive.read(name).decode("utf-8")
    rebuilt = "".join(c.html for c in chunker.chunk(content))
    # Find the first divergence.
    for i, (a, b) in enumerate(zip(content, rebuilt)):
        if a != b:
            print(f"  first difference at char {i}")
            print(f"    original: {content[max(0,i-60):i+60]!r}")
            print(f"    rebuilt : {rebuilt[max(0,i-60):i+60]!r}")
            break
    else:
        print(f"  one is a prefix of the other; lengths {before} vs {after}")
else:
    print("  none")

print()
print("=== is BLOCK_TAGS too small? ===")
print(f"  {len(BLOCK_TAGS)} tags: {', '.join(sorted(BLOCK_TAGS))}")

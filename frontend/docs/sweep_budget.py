"""Chunk count against token budget, on the real book.

The semantic chunker produces 1,376 chunks where the old one produced 158. That
is not a defect: the old limit was 10,000 *characters*, and in Persian that is
roughly 5,000 tokens -- so the old chunks were about four times over a sane
budget and the new default of 1,200 is a deliberate reduction. But 8.7x the API
calls is a real cost, and the right budget is a decision, not a default.

This measures the trade so the number can be chosen rather than guessed.
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.pipeline.html_processor import split_html_by_paragraph
from app.pipeline.semantic_chunker import SemanticChunker, estimate_tokens

BOOK = Path(r"D:\J_BookTranslate_V\data\output\Hands-On_Large_Language_Models_FA.epub")

contents = []
with zipfile.ZipFile(BOOK) as archive:
    for name in archive.namelist():
        if not name.endswith((".xhtml", ".html")):
            continue
        try:
            content = archive.read(name).decode("utf-8")
        except UnicodeDecodeError:
            continue
        if "<" in content:
            contents.append(content)

total_chars = sum(len(c) for c in contents)
print(f"=== {BOOK.name} ===")
print(f"  {len(contents)} content files, {total_chars:,} characters")
print()

# What the old splitter actually produced, in tokens.
old_tokens = []
old_count = 0
for content in contents:
    pieces = split_html_by_paragraph(content, 10000)
    old_count += len(pieces)
    old_tokens.extend(estimate_tokens(p) for p in pieces)
old_tokens.sort()

print("=== the old chunker, measured in tokens ===")
print(f"  chunks            : {old_count}")
print(f"  median tokens     : {old_tokens[len(old_tokens) // 2]}")
print(f"  p95 tokens        : {old_tokens[int(len(old_tokens) * 0.95)]}")
print(f"  max tokens        : {old_tokens[-1]}")
print()

print("=== the new chunker, by budget ===")
print(f"  {'budget':>8}  {'chunks':>7}  {'vs old':>7}  {'mid-block cuts':>15}  {'over budget':>12}")
for budget in (800, 1200, 2000, 3000, 5000, 8000):
    chunker = SemanticChunker(max_tokens=budget, context_window=2)
    count = 0
    split_count = 0
    over = 0
    costs = []
    for content in contents:
        for chunk in chunker.chunk(content):
            count += 1
            costs.append(chunk.estimated_tokens)
            if chunk.split_from_single_block:
                split_count += 1
            if chunk.estimated_tokens > budget:
                over += 1
    costs.sort()
    ratio = count / old_count
    print(
        f"  {budget:>8}  {count:>7}  {ratio:>6.1f}x  "
        f"{split_count:>6} ({100 * split_count / count:>4.1f}%)  {over:>6} ({100 * over / count:>4.1f}%)"
    )

print()
print("  mid-block cuts: chunks that had to be divided inside one block, because")
print("  no paragraph boundary was available. Lower is better.")

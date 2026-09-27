"""Measure what the semantic chunker actually changes, on the user's real book.

Not a unit test. This chunks a real 400-page EPUB both ways and reports the
numbers, because the claim worth checking is a claim about a real book: cuts land
on paragraph boundaries, the token budget holds, and the API-call count does not
explode.

Also reports how much context would be sent, since context is free in requests but
not in tokens.
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.pipeline.html_processor import split_html_by_paragraph
from app.pipeline.semantic_chunker import SemanticChunker, strip_tags

BOOK = Path(
    r"D:\J_BookTranslate_V\data\output\Hands-On_Large_Language_Models_FA.epub"
)

if not BOOK.is_file():
    print(f"  not found: {BOOK}")
    raise SystemExit(1)

chunker = SemanticChunker(max_tokens=1200, context_window=2)

files = 0
skipped = 0
old_count = new_count = 0
old_lossy = 0
new_lossless = 0
costs = []
context_chars = 0
split_blocks = 0
total_blocks = 0

print(f"=== {BOOK.name} ({BOOK.stat().st_size / 1024:.0f} KB) ===")
print()

with zipfile.ZipFile(BOOK) as archive:
    for name in archive.namelist():
        if not name.endswith((".xhtml", ".html")):
            continue
        try:
            content = archive.read(name).decode("utf-8")
        except UnicodeDecodeError:
            skipped += 1
            continue
        if "<" not in content:
            continue
        files += 1

        old = split_html_by_paragraph(content, 10000)
        new = chunker.chunk(content)

        old_count += len(old)
        new_count += len(new)

        # Lossless: does the split reproduce the document?
        if "".join(old) != content:
            old_lossy += 1
        if "".join(c.html for c in new) == content:
            new_lossless += 1

        for chunk in new:
            costs.append(chunk.estimated_tokens)
            context_chars += len(chunk.context_before)
            if chunk.split_from_single_block:
                split_blocks += 1
        total_blocks += len({b for c in new for b in [c.block_range]})

print(f"  content files scanned      : {files}  ({skipped} skipped as non-UTF-8)")
print()
print("=== chunk count ===")
print(f"  old (character count)      : {old_count}")
print(f"  new (token budget)         : {new_count}")
print(f"  difference                 : {new_count - old_count:+d}")
print()
print("=== does the split reproduce the document? ===")
print(f"  old : lossless in {files - old_lossy}/{files} files")
print(f"  new : lossless in {new_lossless}/{files} files")
print()
print("=== where cuts land ===")
print(f"  chunks that had to be cut inside one block : {split_blocks}")
print(f"  ({100 * split_blocks / max(new_count, 1):.1f}% of {new_count})")
print()

if costs:
    costs.sort()
    over = [c for c in costs if c > 1200]
    print("=== estimated tokens per chunk (budget 1200) ===")
    print(f"  min {costs[0]}   median {costs[len(costs) // 2]}   p95 {costs[int(len(costs) * 0.95)]}   max {costs[-1]}")
    print(f"  chunks over budget : {len(over)} ({100 * len(over) / len(costs):.1f}%)")
    print()

print("=== context cost ===")
print(f"  total context characters : {context_chars:,}")
print(f"  per chunk, average       : {context_chars // max(new_count, 1):,}")
print("  (sent in the same request, so no extra API calls)")

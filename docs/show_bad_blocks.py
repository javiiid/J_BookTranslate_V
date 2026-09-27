"""Print the segmentation around the first divergence in a real file.

Reasoning about it stopped helping: the minimal cases round-trip and the real file
does not, so something in the real markup differs and the only way to see it is to
print the blocks either side of the point where the output stops matching.
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.pipeline.semantic_chunker import segment_blocks

BOOK = Path(r"D:\J_BookTranslate_V\data\output\Hands-On_Large_Language_Models_FA.epub")

with zipfile.ZipFile(BOOK) as archive:
    content = archive.read("OEBPS/ch04.html").decode("utf-8")

blocks = segment_blocks(content)
rebuilt = "".join(b.html for b in blocks)

print(f"=== OEBPS/ch04.html ===")
print(f"  {len(content)} -> {len(rebuilt)} ({len(rebuilt) - len(content):+d})")
print(f"  {len(blocks)} blocks")
print()

# Walk the blocks, tracking the offset in the rebuilt string, and report where
# they stop lining up with the source offsets.
cursor = 0
for i, b in enumerate(blocks[:14]):
    expected = content[b.start:b.start + len(b.html)]
    ok = expected == b.html
    print(f"  [{i:2}] tag={b.tag!r:<10} start={b.start:<7} len={len(b.html):<6} "
          f"rebuilt_at={cursor:<7} matches_source_offset={ok}")
    if not ok:
        print(f"        source at that offset: {expected[:80]!r}")
        print(f"        block actually is   : {b.html[:80]!r}")
        break
    cursor += len(b.html)

print()
print("=== the first 12 blocks, verbatim ===")
for i, b in enumerate(blocks[:12]):
    print(f"  [{i:2}] {b.html[:120]!r}")

"""Find the first byte where the chunker's output stops matching the source.

The unit tests assert round-trip on hand-written fixtures and all 75 pass. The
real book round-trips in 0 of 24 files, so the fixtures are missing whatever the
real files contain. This walks to the first divergence and prints the context,
which is the only way to see markup the fixtures never had.
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.pipeline.semantic_chunker import SemanticChunker, segment_blocks

BOOK = Path(r"D:\J_BookTranslate_V\data\output\Hands-On_Large_Language_Models_FA.epub")
chunker = SemanticChunker(max_tokens=1200, context_window=2, min_tokens=200)

shown = 0
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

        rebuilt = "".join(c.html for c in chunker.chunk(content))
        if rebuilt == content:
            continue

        # Locate the first divergence.
        limit = min(len(content), len(rebuilt))
        at = limit
        for i in range(limit):
            if content[i] != rebuilt[i]:
                at = i
                break

        print(f"=== {name} ===")
        print(f"  {len(content)} -> {len(rebuilt)} chars ({len(rebuilt) - len(content):+d})")
        print(f"  first difference at char {at}")
        lo = max(0, at - 90)
        print(f"  source : ...{content[lo:at + 90]!r}")
        print(f"  rebuilt: ...{rebuilt[lo:at + 90]!r}")
        print()

        shown += 1
        if shown >= 3:
            break

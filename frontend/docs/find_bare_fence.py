"""Report the code blocks that declare no language, with correct line numbers.

The earlier report pointed at the wrong line because it searched for the next
"```" from a moving offset, which lands on the *closing* fence of the previous
block rather than the opening fence of the current one.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

path = Path(r"D:\J_BookTranslate_V\readme.md")
lines = path.read_text(encoding="utf-8").splitlines()

print("=== every fenced block, with the line it opens on ===")
blocks = []
open_line = None
language = ""
for number, line in enumerate(lines, 1):
    match = re.match(r"^```(\S*)\s*$", line)
    if not match:
        continue
    if open_line is None:
        open_line, language = number, match.group(1)
    else:
        blocks.append((open_line, language))
        open_line = None

bare = [(number, lang) for number, lang in blocks if not lang]
print(f"  {len(blocks)} block(s) total, {len(bare)} without a language\n")
for number, _ in bare:
    preview = lines[number][:76]
    print(f"  line {number}  bare fence")
    print(f"    {preview!r}")
    for follow in lines[number + 1:number + 4]:
        print(f"      | {follow}")
    print()

if not blocks and lines:
    print("  a fence is still open at end of file")

"""Remove variation selectors from the README headings.

U+FE0F is an ``Mn`` (nonspacing mark), so github-slugger KEEPS it -- which
means the anchor for "## ⚙️ پیکربندی" begins with an invisible character. The
TOC link then has to carry that invisible character too, and the next person
who edits the heading breaks the link with no visible cause.

Dropping the selector fixes the anchor and costs nothing: these emoji render
identically without it. Emoji that genuinely need it would be flagged here
rather than silently left behind.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

path = Path(r"D:\J_BookTranslate_V\readme.md")
text = path.read_text(encoding="utf-8")

VS16 = "️"

lines = text.splitlines(keepends=True)
changed = []
for index, line in enumerate(lines):
    if not re.match(r"^#{1,4}\s", line) or VS16 not in line:
        continue
    before = line
    lines[index] = line.replace(VS16, "")
    if lines[index] != before:
        changed.append((index + 1, lines[index].rstrip()))

if changed:
    path.write_text("".join(lines), encoding="utf-8")

print("=== headings cleaned ===")
for number, line in changed:
    # Show the emoji as its codepoints so there is no ambiguity about what is
    # there now.
    emoji = line.split()[1] if len(line.split()) > 1 else ""
    print(f"  line {number:4}  emoji now {' '.join(f'U+{ord(c):04X}' for c in emoji)}")

print(f"\n  {len(changed)} heading(s) changed")
remaining = [i + 1 for i, l in enumerate(lines) if re.match(r"^#{1,4}\s", l)
             and (VS16 in l or "‍" in l)]
print(f"  headings still carrying VS16 or ZWJ: {remaining or 'none'}")

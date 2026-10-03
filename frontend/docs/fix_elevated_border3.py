"""Put each border token back in its own theme block.

The previous script deleted the comment block above the *first* match, which
turned out to be the day-mode declaration, and then inserted the new value
there too. Result: the day block held the dark value and the dark block kept
the old one.

This walks the file and assigns each `--color-border-strong-elevated` by which
selector block it sits in, then rewrites the comment once, in the dark block
where the reasoning belongs.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

path = Path(r"D:\J_Translate_Ui\ui\src\styles\tokens.css")
text = path.read_text(encoding="utf-8")

COMMENT = """  /* Two border tokens, and the second exists because of arithmetic.
     On the card surface (#0E2233) the ordinary strong border is nearly
     invisible at 2.79:1, so it goes lighter. On the elevated surface (#1F506B)
     a border must be LIGHTER than the surface, not darker. Darkening it is
     backwards and cannot work: at that luminance the +0.05 in the contrast
     formula leaves no room. Measured failures, all against #1F506B:
       #2B6076 -> 1.26:1   #0D2C3D -> 1.41:1   #5D8A9E -> 2.31:1
     #7FA8BC is 3.41:1, so the brand surface stays exactly as given. This is the
     normal dark-UI pattern: the border is lighter than what it outlines. */"""

# Split on the .dark selector so each half can be handled on its own terms.
marker = re.search(r"^(\.dark\s*\{)", text, re.M)
if not marker:
    print("no .dark block found")
    raise SystemExit(1)

head, tail = text[: marker.start()], text[marker.start():]

# Day: the day elevated surface is a light grey, so it keeps a mid-dark border
# that also clears 3:1 there.
head = re.sub(
    r"(\s*/\* Two border tokens.*?\*/\s*\n\s*)--color-border-strong-elevated:\s*#[0-9a-f]{6};",
    r"\1--color-border-strong-elevated: #6d8794;",
    head,
    flags=re.S,
)
head = re.sub(
    r"\s*/\* Two border tokens.*?\*/\s*\n(\s*--color-border-strong-elevated:)",
    r"\n\1",
    head,
    flags=re.S,
)

# Dark: replace the value and put the reasoning in front of it.
tail = re.sub(
    r"\s*--color-border-strong-elevated:\s*#[0-9a-f]{6};",
    f"\n{COMMENT}\n  --color-border-strong-elevated: #7fa8bc;",
    tail,
    count=1,
)

path.write_text(head + tail, encoding="utf-8")

print("=== declarations now ===")
for index, line in enumerate((head + tail).splitlines(), 1):
    if "border-strong-elevated:" in line:
        print(f"  line {index}: {line.strip()}")

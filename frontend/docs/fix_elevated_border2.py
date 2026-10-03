"""Fix the dark-mode elevated border, and record why.

Three values were measured against `--color-surface-elevated` (#1F506B) and all
failed WCAG 1.4.11:

    #2B6076  1.26:1
    #0D2C3D  1.41:1
    #5D8A9E  2.31:1

The instinct to fix a low-contrast border by darkening it is backwards here.
#1F506B has a relative luminance near 0.07, so (L + 0.05) leaves almost no
room below it: a *darker* border cannot reach 3:1 at all. The border has to be
lighter, which is the normal dark-UI pattern anyway.

#7FA8BC measures 3.41:1 and is the first value tried that clears the bar, so the
brand surface stays exactly as specified.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

path = Path(r"D:\J_BookTranslate_V\frontend\ui\src\styles\tokens.css")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

COMMENT = """  /* Two border tokens, and the second exists because of arithmetic.
     On the card surface (#0E2233) the ordinary strong border is nearly
     invisible at 2.79:1, so it goes lighter. On the elevated surface (#1F506B)
     a border must be LIGHTER than the surface, not darker. Darkening it is
     backwards and cannot work: at that luminance the +0.05 in the contrast
     formula leaves no room. Measured failures, all against #1F506B:
       #2B6076 -> 1.26:1     #0D2C3D -> 1.41:1     #5D8A9E -> 2.31:1
     #7FA8BC is 3.41:1, so the brand surface stays exactly as specified. This is
     the normal dark-UI pattern: the border is lighter than what it outlines. */
"""

replaced = 0
index = 0
while index < len(lines):
    line = lines[index]
    if "--color-border-strong-elevated:" in line:
        # Drop the old explanatory comment block above it, then the token.
        start = index
        while start > 0 and (lines[start - 1].lstrip().startswith(("/*", "*", "Two problems", "less than"))):
            start -= 1
        # The old comment started with a /* and ended with */ on its own line.
        while start < index and "*/" not in lines[start]:
            start -= 1
        del lines[start:index + 1]
        lines[start:start] = [COMMENT, "  --color-border-strong-elevated: #7fa8bc;\n"]
        replaced += 1
        break
    index += 1

if replaced != 1:
    print(f"replaced {replaced} site(s); expected 1")
    raise SystemExit(1)

path.write_text("".join(lines), encoding="utf-8")
print("dark elevated border set to #7fa8bc with the reasoning recorded")

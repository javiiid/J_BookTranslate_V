"""Copy Vazirmatn into the React build and reference it as a real font file.

First attempt inlined the woff2 as base64 in a generated stylesheet, copying
`app/core/fonts.py`. It works and it removes the CDN, but it inflated the CSS
from 29 KB to 370 KB (263 KB gzipped) -- 330 KB of base64 in a stylesheet, for
an application shell that is otherwise a few kilobytes.

Copying the files into `public/fonts/` and referencing them with `url()` is
strictly better and keeps the same guarantee:

  - no request leaves the machine, which is the property that matters for a
    local-first tool
  - the fonts are separate cacheable resources, so a CSS change does not force a
    263 KB re-download, and the font survives a deploy unchanged
  - the CSS stays 29 KB

The font files are not tracked in this repository. The Python project is the
source of truth for binary assets, and duplicating 250 KB of font across two
repositories is how they drift. Re-run this after changing a weight there.
"""
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PY_FONT_DIR = Path(r"D:\J_BookTranslate_V\app\library")
UI = Path(r"D:\J_BookTranslate_V\frontend\ui")
FONT_OUT = UI / "public" / "fonts"
CSS_OUT = UI / "src" / "styles" / "fonts.generated.css"

# The weights the design system uses. A weight the CSS asks for but this does
# not define gets synthesised by the browser, and synthesised Persian looks wrong.
WEIGHTS = [
    ("Vazirmatn-Regular.woff2", 400),
    ("Vazirmatn-Medium.woff2", 500),
    ("Vazirmatn-SemiBold.woff2", 600),
    ("Vazirmatn-Bold.woff2", 700),
    ("Vazirmatn-Black.woff2", 800),
]

missing = [name for name, _ in WEIGHTS if not (PY_FONT_DIR / name).is_file()]
if missing:
    print(f"  MISSING from {PY_FONT_DIR}: {missing}")
    raise SystemExit(1)

FONT_OUT.mkdir(parents=True, exist_ok=True)
copied = 0
for filename, _ in WEIGHTS:
    destination = FONT_OUT / filename
    shutil.copyfile(PY_FONT_DIR / filename, destination)
    copied += destination.stat().st_size

header = """/* GENERATED FILE -- do not edit. Run ../docs/build_fonts.py to regenerate.
   Source of truth: D:\\J_BookTranslate_V\\app\\library\\*.woff2

   The font is served from this origin rather than a CDN, which is the same
   guarantee app/core/fonts.py gives the Python pages: the app renders Persian
   text with the network unplugged and no third party learns who is reading.
   Unlike the Python version these are real font files rather than base64 in
   CSS, so they cache separately and the stylesheet stays small. */

"""

faces = []
for filename, weight in WEIGHTS:
    faces.append(
        "@font-face {\n"
        "  font-family: 'Vazirmatn';\n"
        "  font-style: normal;\n"
        f"  font-weight: {weight};\n"
        "  font-display: swap;\n"
        f"  src: url('/fonts/{filename}') format('woff2');\n"
        "}"
    )

CSS_OUT.write_text(header + "\n\n".join(faces) + "\n", encoding="utf-8")

print(f"wrote {CSS_OUT}  ({CSS_OUT.stat().st_size / 1024:.1f} KB)")
print(f"copied {len(WEIGHTS)} font file(s) to {FONT_OUT}  ({copied / 1024:.1f} KB total)")
print("  each is a separate cacheable resource; the CSS stays small")

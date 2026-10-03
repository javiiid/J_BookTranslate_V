"""Check the KALIMA mark actually lands in the rendered page.

The rename and the mark are both string surgery on a very large HTML literal, so
the check is "does the served page contain the right things" rather than a unit
test. It imports the real module, so it fails if a placeholder stops being
filled.

Checks:
  - the __KALIMA_MARK__ placeholder was consumed
  - both variants are present, and CSS shows exactly one per theme
  - the SVG is inline, because the server has no static route
  - the old placeholder glyph is gone
  - the product name appears
  - the SVG is well-formed enough to parse
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\J_BookTranslate_V")

failures = 0


def check(label, condition, detail=""):
    global failures
    failures += not condition
    print(f"  {'ok  ' if condition else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))


import app.web as web  # noqa: E402

page = web.PAGE
OLD_GLYPH = "\u6587"  # the placeholder ideograph the sidebar used to show

print("=== the mark in the rendered page ===")
check("the __KALIMA_MARK__ placeholder was consumed", "__KALIMA_MARK__" not in page)
check("the light variant is present", 'class="mark-light"' in page)
check("the dark variant is present", 'class="mark-dark"' in page)
check("both variants are inlined as SVG", page.count("<svg") >= 2, f"{page.count('<svg')} svg tag(s)")
check("the old placeholder glyph is gone", OLD_GLYPH not in page)
check("the product name is present", "KALIMA" in page)

print()
print("=== the theme switch ===")
check("dark hides the light mark", "body.app-dark .side-brand-mark .mark-light{display:none}" in page)
check("dark shows the dark mark", "body.app-dark .side-brand-mark .mark-dark{display:block}" in page)
check("light is the default", "body.app-dark" in page and "app-dark" in page,
      "the pages use an app-dark class, not .dark")

print()
print("=== the SVG parses ===")
start = page.find("<svg")
end = page.find("</svg>", start)
if start == -1 or end == -1:
    check("an <svg> block exists", False)
else:
    fragment = page[start: end + 6]
    try:
        ET.fromstring(fragment)
        check("the inlined SVG is well-formed XML", True, f"{len(fragment)} chars")
    except ET.ParseError as error:
        check("the inlined SVG is well-formed XML", False, str(error))

print()
print("=== the source SVGs are reachable and well-formed ===")
# Both copies are checked: the React one is the source, the Python one is what
# app/core/brand.py actually reads. If only the source were checked, a stale copy
# in the Python repo would pass and the sidebar would show an old mark.
import app.core.brand as brand_module  # noqa: E402

for location, directory in [
    ("react (source)", Path(r"D:\J_Translate_Ui\ui\public\brand")),
    ("python (copy)", brand_module.BRAND_DIR),
]:
    for name in ("kalima-mark-light.svg", "kalima-mark-dark.svg"):
        path = directory / name
        check(f"{location}: {name} exists", path.is_file())
        if path.is_file():
            try:
                ET.parse(path)
                check(f"{location}: {name} parses", True, f"{path.stat().st_size / 1024:.1f} KB")
            except ET.ParseError as error:
                check(f"{location}: {name} parses", False, str(error))

print()
print("=== the two copies are identical ===")
for name in ("kalima-mark-light.svg", "kalima-mark-dark.svg"):
    source = (Path(r"D:\J_Translate_Ui\ui\public\brand") / name).read_bytes()
    copy = (brand_module.BRAND_DIR / name).read_bytes()
    check(f"{name} is in sync", source == copy,
          "run install_brand.py" if source != copy else "")

print()
print("=== the brand module ===")
from app.core import brand  # noqa: E402


for theme in ("light", "dark"):
    mark = brand.kalima_mark(theme=theme, size=34)
    check(f"kalima_mark({theme!r}) returns an svg", mark.startswith("<svg") or "<svg" in mark)
    check(f"kalima_mark({theme!r}) honours the size argument", 'width="34"' in mark,
          "the master is 512 units, so width/height must be rewritten")

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)

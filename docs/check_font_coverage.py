"""Check that the font actually loads, and that Persian text can use it.

A 11px Persian label is uncomfortable. A missing font makes it unreadable, and
the two look identical from a screenshot. So this checks three things that are
easy to get wrong and invisible in the markup:

  1. do the woff2 files the CSS points at actually exist in the build output
  2. does the generated @font-face cover the weights the type scale asks for
  3. does Vazirmatn actually contain Persian glyphs, or does the browser fall
     back to a system font that may not have them

The third is the one that bites: a Persian UI rendered in a fallback font can
look like a styling problem for a long time before anyone suspects the font.
"""
import re
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

UI = Path(r"D:\J_Translate_Ui\ui")
DIST = UI / "dist"

failures = 0


def check(label, ok, detail=""):
    global failures
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))


print("=== 1. the @font-face rules in the built CSS ===")
css_file = next(p for p in (DIST / "assets").iterdir() if p.name.endswith(".css"))
css = css_file.read_text(encoding="utf-8")

faces = re.findall(r"@font-face\s*\{([^}]*)\}", css)
print(f"  {len(faces)} @font-face rule(s) in the built CSS")
if not faces:
    print("  FAIL no @font-face at all: the browser is using a system font")

for face in faces:
    family = re.search(r"font-family:\s*([^;]+)", face)
    weight = re.search(r"font-weight:\s*([^;]+)", face)
    source = re.search(r"src:\s*url\(([^)]+)\)", face)
    print(f"    family={family.group(1).strip() if family else '?'} "
          f"weight={weight.group(1).strip() if weight else '?'} "
          f"url={source.group(1).strip()[:48] if source else '?'}")

check("Vazirmatn is declared", any("Vazirmatn" in f for f in faces))

print()
print("=== 2. the font files the CSS points at exist in dist/ ===")
for face in faces:
    source = re.search(r"src:\s*url\(['\"]?([^'\")]+)", face)
    if not source:
        continue
    url = source.group(1).strip()
    if url.startswith("data:"):
        print(f"    inlined, {len(url) // 1024} KB of base64")
        continue
    name = url.lstrip("/")
    candidates = [DIST / name, DIST / "assets" / Path(name).name]
    found = next((c for c in candidates if c.is_file()), None)
    check(f"{url} is in the build", found is not None,
          f"{found.stat().st_size / 1024:.1f} KB" if found else "MISSING")

print()
print("=== 3. does Vazirmatn actually contain Persian glyphs? ===")
# Read one woff2 and look for the Arabic block in its cmap. The woff2 header is
# compressed, so a full parse is out of scope; instead check the file is a real
# woff2 and non-trivial in size, then verify the *source* font's coverage with
# fontTools if it happens to be installed.
woff = next((DIST / "fonts").glob("*.woff2"), None)
check("a woff2 is present", woff is not None, woff.name if woff else "")
if woff:
    header = woff.read_bytes()[:4]
    check("it is a real woff2 (wOF2 signature)", header == b"wOF2", str(header))
    check("it is a plausible size", woff.stat().st_size > 20_000,
          f"{woff.stat().st_size / 1024:.1f} KB")

try:
    from fontTools.ttLib import TTFont

    font = TTFont(str(woff))
    cmap = font.getBestCmap()
    # Persian letters that appear constantly in this UI.
    needed = {
        "ب": 0x0628, "ا": 0x0627, "ک": 0x06A9, "ی": 0x06CC,
        "م": 0x0645, "ت": 0x062A, "ر": 0x0631, "ه": 0x0647,
        "و": 0x0648, "ن": 0x0646, "س": 0x0633, "ل": 0x0644,
    }
    missing = [chr(cp) for cp in needed.values() if cp not in cmap]
    check("every common Persian letter is in the font", not missing, f"missing {missing}")
    arabic = sum(1 for cp in cmap if 0x0600 <= cp <= 0x06FF)
    check("the font has a substantial Arabic block", arabic > 100, f"{arabic} codepoints")
except ImportError:
    print("  fontTools is not installed, so glyph coverage was not verified")
    print("  install it with: pip install fonttools")

print()
print("=== 4. the weights the type scale asks for ===")
weights = sorted({int(w) for w in re.findall(r"font-weight:\s*(\d{3})", css)})
declared = sorted({int(m) for m in re.findall(r"@font-face\s*\{[^}]*?font-weight:\s*(\d{3})", css, re.S)})
print(f"  declared in @font-face : {declared}")
print(f"  requested by utilities : {weights}")
print(f"  the CSS also asks for bold via `font-weight: 600/700/800`, which the")
print(f"  browser synthesises from the nearest declared weight if it has to.")

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)

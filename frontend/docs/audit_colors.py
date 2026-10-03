"""Audit hardcoded colours across both front ends.

The brief asks for semantic tokens instead of hardcoded colours, so the first
question is how much is actually hardcoded and where. Counting before editing
keeps the migration honest: it is easy to claim "the interface is tokenised"
when only the files that happened to be opened are.
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PY = Path(r"D:\J_BookTranslate_V")
UI = Path(r"D:\J_BookTranslate_V\frontend\ui")

# Hex colours, excluding the ones that are obviously not UI colours.
HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
NAMED = re.compile(
    r"\b(?:white|black|red|green|blue|orange|purple|amber|emerald|slate|gray|grey|"
    r"sky|indigo|violet|teal|cyan|rose|lime|yellow)\b",
    re.I,
)
# class names that carry colour in Tailwind, e.g. bg-blue-700 text-slate-600.
TAILWIND = re.compile(
    r"\b(?:bg|text|border|from|to|via|ring|fill|stroke|shadow|accent|outline|divide)-"
    r"([a-z]+)-(\d{2,3})\b"
)

# Find the front-end files by what they contain, not by where they sit. The
# page modules are scattered (app/jobs/, app/account/, app/library/, ...) and a
# path-based guess missed eight of them.
def is_frontend(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    if "__pycache__" in str(path):
        return False
    # A module counts as front end if it emits markup, not if its name suggests
    # it. The earlier version keyed on directory names and matched nothing.
    return "<style" in text or "</style>" in text or "<main" in text or 'class="' in text


# rglob over the project root walks .venv and .opencode, which contributed
# dozens of false hits from third-party packages. Only the app is ours.
py_pages = sorted(p for p in (PY / "app").rglob("*.py") if is_frontend(p))
py_pages.append(PY / "landing.html")
py_pages = [p for p in py_pages if p.is_file()]

print("=== Python front-end files ===")
print("-" * 70)
totals = {"hex": 0, "named": 0, "tailwind": 0}
palette = Counter()
for path in py_pages:
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    hexes = HEX.findall(text)
    named = NAMED.findall(text)
    tw = TAILWIND.findall(text)
    palette.update(h.lower() for h in hexes)
    totals["hex"] += len(hexes)
    totals["named"] += len(named)
    totals["tailwind"] += len(tailwind_colors := [f"{a}-{b}" for a, b in tw])
    if hexes or named or tw:
        print(f"  {path.relative_to(PY)}")
        print(f"      hex {len(hexes):>4}   tailwind {len(tw):>4}   named-colour words {len(named):>4}")

print()
print(f"  total hex colours     : {totals['hex']}")
print(f"  total Tailwind classes: {totals['tailwind']}")
print(f"  total named colours   : {totals['named']}")

print()
print("=== most used hex colours (the de-facto palette) ===")
print("-" * 70)
for colour, count in palette.most_common(24):
    bar = "#" * min(30, count)
    print(f"  {colour}  {count:>4}  {bar}")

print()
print("=== is there ANY token system in the Python front end? ===")
print("-" * 70)
found_tokens = []
for path in py_pages:
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for name in ("--color-", "--surface", "--ink", "var(--"):
        if name in text:
            found_tokens.append((path.relative_to(PY), name, text.count(name)))
if found_tokens:
    for rel, name, count in found_tokens:
        print(f"  {rel}  uses {name!r} x{count}")
else:
    print("  no CSS custom properties found: the Python pages hardcode every colour")

print()
print("=== the React tokens ===")
print("-" * 70)
tokens = (UI / "src" / "styles" / "tokens.css")
if tokens.is_file():
    text = tokens.read_text(encoding="utf-8")
    declared = re.findall(r"^\s*(--[a-z0-9-]+)\s*:", text, re.M)
    print(f"  tokens.css declares {len(declared)} custom properties")
    semantic = [d for d in declared if any(
        k in d for k in ("background", "surface", "primary", "secondary", "accent",
                         "text-", "border", "success", "warning", "error", "info"))]
    print(f"  of which semantic-named : {len(semantic)}")
    for name in declared:
        print(f"    {name}")
else:
    print("  tokens.css is missing")

print()
print("=== where the old palette still lives ===")
print("-" * 70)
for path in [UI / "src" / "lib" / "format.ts", UI / "src" / "components" / "AppShell.tsx",
             UI / "src" / "pages" / "DashboardPage.tsx"]:
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8")
    hexes = HEX.findall(text)
    tw = TAILWIND.findall(text)
    print(f"  {path.relative_to(UI)}  hex {len(hexes)}  tailwind {len(tw)}")
    for match in sorted(set(TAILWIND.findall(text))):
        print(f"      {match[0]}-{match[1]}")

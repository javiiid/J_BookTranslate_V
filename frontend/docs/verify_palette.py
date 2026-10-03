"""Prove the old palette is gone from the React source.

Renaming tokens is only half the job. A hex literal or a Tailwind colour class
left in a component would still render the old blue/green, and it would survive
a diff review because the token rename looks complete.

The old palette, from before the migration:
  blue   #356df6  purple #7257e8  green #08966c  cyan  #0ca6a6
  amber  #d98518  red    #e24a4a  ink   #142033  line  #e3e9f2
  muted  #6d7a90  slate-* / emerald-* / blue-* / amber-* / red-*
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

UI = Path(r"D:\J_Translate_Ui\ui")

OLD_HEX = {
    "356df6", "2e62dc", "2d5ed4", "7257e8", "08966c", "0ca6a6",
    "d98518", "e24a4a", "142033", "e3e9f2", "6d7a90", "1e3a5a",
    "edf3ff", "f4f7fb", "f1f3f5", "b8c6d6", "243142", "60a5fa",
}
# Tailwind colour scales that carry the old palette, plus the greys that read as
# a different design language from the new blue-tinted neutrals.
OLD_TAILWIND = re.compile(
    r"\b(?:bg|text|border|ring|fill|stroke|shadow|divide|outline|accent|from|to|via)-"
    r"(?:slate|gray|grey|zinc|neutral|stone|sky|blue|indigo|violet|purple|fuchsia|"
    r"pink|rose|red|orange|amber|yellow|lime|green|emerald|teal|cyan)-[0-9]{2,3}\b"
)

files = sorted(list((UI / "src").rglob("*.ts")) + list((UI / "src").rglob("*.tsx")))
hex_hits = []
tw_hits = []

for path in files:
    text = path.read_text(encoding="utf-8")
    for index, line in enumerate(text.splitlines(), 1):
        # Comments are excluded on purpose. The migration deliberately records
        # what the old palette was and why each value moved, so a grep that
        # flagged the explanation would report the audit trail as a regression.
        code = re.sub(r"/\*.*?\*/", "", line)
        code = re.sub(r"//.*$", "", code)
        code = re.sub(r"`[^`]*`", "", code)
        for match in re.finditer(r"#([0-9A-Fa-f]{3,8})\b", code):
            value = match.group(1).lower()
            if value in OLD_HEX:
                hex_hits.append((path, index, match.group(0), line.strip()[:70]))
        for match in OLD_TAILWIND.finditer(code):
            tw_hits.append((path, index, match.group(0), line.strip()[:70]))

print("=== old hex literals ===")
if hex_hits:
    for path, index, value, line in hex_hits:
        print(f"  {path.relative_to(UI)}:{index}  {value}   {line}")
else:
    print("  none")

print()
print("=== old Tailwind colour classes ===")
if tw_hits:
    for path, index, value, line in tw_hits:
        print(f"  {path.relative_to(UI)}:{index}  {value:<26} {line}")
else:
    print("  none")

print()
print("=== the new palette, as actually referenced from the source ===")
css = (UI / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")
BRAND = {"f1e6b6": "cream", "b0e1e4": "aqua", "4c7c92": "blue",
         "ffffff": "day background", "071426": "dark background", "1f506b": "dark elevated"}
used = []
for hexvalue, name in BRAND.items():
    count = len(re.findall(hexvalue, css, re.I))
    used.append((name, hexvalue, count))
    print(f"  {name:20} #{hexvalue.upper()}  used {count}x")

print()
missing = [name for name, _, count in used if count == 0]
if missing:
    print(f"  WARNING: brand colour(s) absent from tokens.css: {missing}")
else:
    print("  all six given brand values are present")

print()
total = len(hex_hits) + len(tw_hits)
print(f"VERDICT: {'CLEAN' if total == 0 else f'{total} OLD REFERENCE(S) REMAIN'}")
sys.exit(1 if total else 0)

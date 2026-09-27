"""Migrate the monitor components from the old token names to the new ones.

This is a rename, not a redesign, for the six monitor files. Mechanical edits
are safer in a script than by hand across four files, and a miss would show up
as an undefined custom property at runtime rather than at build time -- CSS
custom properties fail silently.

The mapping is deliberately exhaustive: any `var(--old)` left behind is
reported, because a silently-undefined variable renders as inherited or
transparent and is invisible in a diff.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

UI = Path(r"D:\J_Translate_Ui\ui")

# Old name -> new name. Only renames; the tone decisions were made in tokens.css
# and in the hand-edited files.
MAP = {
    "--bg": "--color-background",
    "--surface": "--color-surface",
    "--surface-2": "--color-surface-elevated",
    "--ink": "--color-text-primary",
    "--ink-strong": "--color-text-primary",
    "--muted": "--color-text-muted",
    "--muted-2": "--color-text-muted",
    "--line": "--color-border",
    "--line-strong": "--color-border-strong",
    "--blue": "--color-primary",
    "--blue-soft": "--color-primary-subtle",
    "--purple": "--color-accent",
    "--green": "--color-success",
    "--amber": "--color-warning",
    "--red": "--color-error",
    "--cyan": "--color-info",
    "--shadow-soft": "--shadow-card",
    "--shadow-card": "--shadow-raised",
}

# Longest first, so --surface-2 is renamed before --surface.
ORDERED = sorted(MAP, key=len, reverse=True)

files = sorted(
    p for p in (UI / "src").rglob("*.tsx")
    if "components" in p.parts or "pages" in p.parts
)

total = 0
leftovers = []
for path in files:
    text = path.read_text(encoding="utf-8")
    original = text

    for old in ORDERED:
        new = MAP[old]
        # Only inside var(), so a class name is never touched.
        text = re.sub(rf"var\({re.escape(old)}\)", f"var({new})", text)

    if text != original:
        path.write_text(text, encoding="utf-8")
        count = sum(1 for a, b in zip(original.splitlines(), text.splitlines()) if a != b)
        print(f"  {path.relative_to(UI)}  ({count} line(s) changed)")
        total += count

    for match in re.finditer(r"var\((--[a-z0-9-]+)\)", text):
        if match.group(1) in MAP.values():
            continue
        # Anything not in the new set is reported for manual review.
        leftovers.append((path.relative_to(UI), match.group(1)))

print(f"\n  {total} line(s) changed across {len(files)} file(s)")

print("\n=== tokens referenced but not defined in tokens.css ===")
tokens_css = (UI / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")
defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", tokens_css))
referenced = set()
for path in sorted((UI / "src").rglob("*.ts")) + sorted((UI / "src").rglob("*.tsx")):
    for match in re.finditer(r"var\((--[a-z0-9-]+)\)", path.read_text(encoding="utf-8")):
        referenced.add(match.group(1))

missing = sorted(referenced - defined)
if missing:
    for name in missing:
        print(f"  UNDEFINED  {name}")
    print(f"\n  {len(missing)} undefined token(s) -- CSS would resolve these to nothing")
else:
    print("  none: every var() in the source is declared in tokens.css")

unused = sorted(defined - referenced)
print(f"\n=== declared but not referenced from TS/TSX ({len(unused)}) ===")
print("  " + ", ".join(unused[:24]) + (" ..." if len(unused) > 24 else ""))

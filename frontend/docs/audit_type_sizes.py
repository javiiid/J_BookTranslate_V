"""Report every text element below 12px, grouped by where it comes from.

The contrast audit found 166 of them, and at 11px Persian text with a
right-to-left script is genuinely hard to read: the letters join, so a small
size removes the shapes that disambiguate. The caption step in the type scale is
`0.6875rem` = 11px, which is the smallest value the design system defines and
the one most likely to be the complaint.

Grouping by class shows whether it is one component or the whole interface.
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

UI = Path(r"D:\J_BookTranslate_V\frontend\ui")

# Run the audit and capture its JSON by asking for machine output.
result = subprocess.run(
    ["node", str(UI / "scripts" / "audit-contrast.mjs")],
    capture_output=True, cwd=UI, check=False,
)
# Explicit UTF-8: the output is full of Persian, and the default cp1252 codec
# raises rather than substituting, which loses the whole report.
out = result.stdout.decode("utf-8", errors="replace")

sizes = Counter()
pages = Counter()
examples = {}

for line in out.splitlines():
    match = re.match(r"\s+(ok|large|FAIL)\s+([\d.]+):1\s+(\d+)px\s+(\S+)/(\w+)/(\w+)\s+\"(.*)\"\s*$", line)
    if not match:
        continue
    size = int(match.group(3))
    if size >= 12:
        continue
    page = match.group(5)
    pages[(page, size)] += 1
    sizes[size] += 1
    examples.setdefault((page, size), (match.group(7), match.group(6)))

print("=== every distinct (page, font-size) below 12px ===")
print("-" * 74)
for (page, size), count in sorted(pages.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    text, tag = examples[(page, size)]
    print(f"  {count:>4}x  {size:>2}px  {page:<12} <{tag}>  {text[:44]}")

print()
print("=== the type scale, and where each step is used ===")
print("-" * 74)
css = (UI / "dist" / "assets" / next(
    p.name for p in (UI / "dist" / "assets").iterdir() if p.name.endswith(".css")
)).read_text(encoding="utf-8")

scale = dict(re.findall(r"--text-([a-z0-9-]+):\s*([\d.]+)rem", css))
for name, value in sorted(scale.items(), key=lambda kv: float(kv[1])):
    pixels = float(value) * 16
    verdict = "TOO SMALL" if pixels < 12 else "ok"
    print(f"  --text-{name:<10} {value:>7} rem = {pixels:>5.1f}px  {verdict}")

print()
print("=== how many usages of each step ===")
print("-" * 74)
source = "\n".join(
    p.read_text(encoding="utf-8")
    for p in (UI / "src").rglob("*.tsx")
)
for name in sorted(scale, key=lambda k: float(scale[k])):
    pattern = rf"text-\[length:var\(--text-{re.escape(name)}\)\]"
    count = len(re.findall(pattern, source))
    pixels = float(scale[name]) * 16
    if count:
        print(f"  {pixels:>5.1f}px  --text-{name:<10} used {count:>3}x")

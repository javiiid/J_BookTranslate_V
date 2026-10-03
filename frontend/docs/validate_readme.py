"""Validate the README's structure the way GitHub will render it.

No browser is available in this session, so instead of guessing whether the
document looks right, this checks the things that actually break on GitHub:
the table of contents anchors, unbalanced HTML, stripped-by-GitHub tags, table
column consistency, and empty link targets that render as a link to nowhere.
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

README = Path(r"D:\J_BookTranslate_V\readme.md").read_text(encoding="utf-8")
failures = []


def prose_only(markdown):
    """Strip fenced blocks and inline code before structural analysis.

    Without this the architecture tree is read as real Markdown -- its
    `#   config.py` Python comments look like an h1, and a security note that
    names the `<base>` tag looks like an unpermitted element. Both were false
    alarms before this existed.
    """
    without_fences = re.sub(r"^```.*?^```", "", markdown, flags=re.M | re.S)
    return re.sub(r"`[^`\n]+`", "CODE", without_fences)


PROSE = prose_only(README)


def check(label, condition, detail=""):
    if not condition:
        failures.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))


def slugify(heading):
    """Reproduce github-slugger, which is what GitHub actually uses.

    The rule is: lowercase and trim, drop everything that is not a letter,
    number, mark, connector punctuation, dash punctuation, whitespace or a
    hyphen, then turn each run of whitespace into a single hyphen.

    Two details matter here and both were wrong in a first attempt:
      * an em-dash is ``\\p{Pd}``, so it SURVIVES into the anchor
      * a ZWNJ in واژه‌نامه is ``\\p{Cf}``, so it is REMOVED
    Guessing this produced a TOC link that 404s on a heading that renders fine.
    """
    import unicodedata as ud

    text = heading.strip().lower()
    kept = []
    for char in text:
        category = ud.category(char)
        if category[0] in {"L", "N", "M"}:
            kept.append(char)
        elif category in {"Pc", "Pd"}:
            kept.append(char)
        elif char.isspace():
            kept.append(" ")
        # Everything else, including emoji and Cf, is dropped.
    return re.sub(r"\s", "-", "".join(kept))


print("=== table of contents anchors ===")
print("-" * 72)
headings = re.findall(r"^#{1,4}\s+(.+?)\s*$", README, re.M)
anchors = {slugify(h) for h in headings}
toc_links = re.findall(r"^\s*-\s*\[([^\]]+)\]\(#([^)]+)\)\s*$", README, re.M)
check("the TOC has entries", len(toc_links) >= 10, f"{len(toc_links)} links")
for label, anchor in toc_links:
    if anchor not in anchors:
        # Show the real slugs rather than just failing, so the fix is obvious.
        close = [a for a in anchors if a.startswith(anchor[:12])]
        print(f"       want: #{anchor}")
        for candidate in (close or sorted(anchors)[:3]):
            print(f"       got:  #{candidate}")
    check(f"anchor #{anchor}", anchor in anchors, f"for '{label}'")

print()
print("=== headings that are not in the TOC (informational) ===")
print("-" * 72)
linked = {anchor for _, anchor in toc_links}
missing = sorted(a for a in anchors if a not in linked)
print(f"  {len(missing)} heading(s) not linked from the TOC")

print()
print("=== HTML that GitHub strips ===")
print("-" * 72)
check("no <style> block", "<style" not in README.lower())
check("no <script> block", "<script" not in README.lower())
check("no inline event handlers", not re.search(r"\son[a-z]+\s*=", PROSE, re.I))
check("no <iframe>", "<iframe" not in PROSE.lower())
allowed = {"div", "br", "sub", "sup", "p", "span", "details", "summary", "a", "img",
           "b", "i", "em", "strong", "code", "h1", "h2", "h3", "h4", "ul", "ol", "li"}
used = {tag.lower() for tag in re.findall(r"<\s*/?\s*([a-zA-Z][a-zA-Z0-9]*)", PROSE)}
check("only tags GitHub permits", used <= allowed, f"unexpected: {sorted(used - allowed)}")

print()
print("=== tag balance ===")
print("-" * 72)
for tag in ("div", "details", "summary", "p"):
    opens = len(re.findall(rf"<\s*{tag}[\s>]", PROSE))
    closes = len(re.findall(rf"<\s*/\s*{tag}\s*>", PROSE))
    check(f"<{tag}> balanced", opens == closes, f"{opens} open / {closes} close")

print()
print("=== tables have consistent columns ===")
print("-" * 72)
blocks, current = [], []
for line in README.splitlines():
    if line.strip().startswith("|"):
        current.append(line)
    elif current:
        blocks.append(current)
        current = []
if current:
    blocks.append(current)
for index, block in enumerate(blocks, 1):
    widths = {len(re.split(r"(?<!\\)\|", row.strip())) - 2 for row in block}
    check(f"table {index} ({len(block)} rows) has one column count", len(widths) == 1,
          f"widths {sorted(widths)}")
print(f"  {len(blocks)} table(s) total")

print()
print("=== link targets ===")
print("-" * 72)
empty = re.findall(r"\[([^\]]+)\]\(\s*\)", README)
check("no empty link targets", not empty, str(empty))
relative = [t for t in re.findall(r"\[([^\]]+)\]\((?!https?://|#)([^)]+)\)", README)]
for label, target in relative:
    exists = (Path(r"D:\J_BookTranslate_V") / target.strip()).exists()
    check(f"relative link '{label}' -> {target} exists", exists)

print()
print("=== badges ===")
print("-" * 72)
badges = re.findall(r"\[!\[([^\]]*)\]\(([^)]+)\)\]", README)
check("badges use shields.io", all("shields.io" in url for _, url in badges),
      f"{len(badges)} badges")
for name, url in badges:
    check(f"badge '{name}' has an https url", url.startswith("https://"))

print()
print("=== headings and structure ===")
print("-" * 72)
# Counted from PROSE, not README: the architecture tree is full of `#   file.py`
# Python comments that are not headings at all.
h1 = len(re.findall(r"^#\s+\S", PROSE, re.M))
check("exactly one h1", h1 == 1, f"{h1} found")
levels = [len(h) for h in re.findall(r"^(#+) ", PROSE, re.M)]
check("no heading jumps more than one level",
      all(b - a <= 1 for a, b in zip(levels, levels[1:])), f"levels {sorted(set(levels))}")
check("fenced code blocks are balanced", README.count("```") % 2 == 0,
      f"{README.count('```')} fences")
# Only opening fences carry a language; a closing fence is "```" with nothing
# after it, so checking every match would flag half of them.
blocks = re.findall(r"^```(\w*)\s*$.*?^```\s*$", README, re.M | re.S)
bare = [index for index, lang in enumerate(blocks, 1) if not lang]
check("every code block declares a language", not bare,
      f"bare at position(s) {bare} of {len(blocks)}")
print(f"  languages used: {sorted(set(blocks))}")
if bare:
    # Point at the offending line so it can be fixed without hunting.
    offset = 0
    for index, lang in enumerate(blocks, 1):
        start = README.index("```", offset)
        if index in bare:
            line = README[:start].count("\n") + 1
            following = README[start + 4:start + 4 + 70].replace("\n", " / ")
            print(f"       line {line}: {following!r}")
        offset = start + 4

print()
print("=" * 72)
print("FAILURES:", len(failures))
for item in failures:
    print("  -", item)
sys.exit(1 if failures else 0)

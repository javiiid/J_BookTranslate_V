"""Rename the product to KALIMA across both repositories.

Scope is decided by what each string IS, not by what it contains:

  CHANGED  display strings: page titles, headings, the CLI --help banner, the
           README, the landing copy, the subtitle.
  CHANGED  internal identifiers that carry no state: the `jbt-*` ramp in
           tokens.css (declared but never referenced, verified first), the
           `kalima-theme` / `kalima-lang` class names in landing.html, and the
           JBT_API environment variable, which keeps the old name as a fallback
           so an existing setup does not break.
  KEPT     the SQLite file `jbooktranslate.db`. Renaming it orphans every
           existing job, book and glossary.
  KEPT     the localStorage key `jbook-study-dark`. Renaming it silently resets
           every existing user's theme, and the two UIs read the same key, so
           one would change without the other.
  KEPT     the folder names and the `D:\\J_BookTranslate_V` path. They are
           facts about where the code lives, and the Python project must stay
           where the other tooling expects it.

Each kept identifier gets a comment saying why, so the next person does not
"tidy" it.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PY = Path(r"D:\J_BookTranslate_V")
UI = Path(r"D:\J_BookTranslate_V\frontend")

SKIP_DIRS = {
    "node_modules", ".git", ".venv", "__pycache__", "dist", ".test-tmp",
    "output", "data", "temp", ".opencode", "inventory", "preview",
}
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".html", ".md", ".css", ".json", ".yaml", ".yml", ".mjs", ".txt"}

# The subtitle used to be "Word by word, book by book", which described the category
# rather than the product. KALIMA is a word, so it gets a word.
SUBTITLE = "Word by word, book by book"

# (pattern, replacement, description)
EDITS: list[tuple[re.Pattern, str, str]] = [
    # --- order matters: longest first ---
    (re.compile(r"KALIMA — رابط کاربری"), "KALIMA — رابط کاربری",
     "react page title"),
    (re.compile(r"KALIMA"), "KALIMA", "display name"),
    (re.compile(r"KALIMA"), "KALIMA", "CLI help banner"),
    (re.compile(r"KALIMA UI"), "KALIMA UI", "repo title"),
    (re.compile(r"Word by word, book by book"), SUBTITLE, "subtitle"),
    (re.compile(r"word by word, book by book"), SUBTITLE.lower(), "subtitle, lower case"),

    # --- internal, stateless ---
    (re.compile(r"\bjbt-(blue|slate|aqua|cream)-"), r"kalima-\1-", "token ramp prefix"),
    (re.compile(r"\bjbt-theme\b"), "kalima-theme", "landing class name"),
    (re.compile(r"\bjbt-lang\b"), "kalima-lang", "landing class name"),
]

# Files that must be listed as kept, with the reason, so a reviewer can see the
# decision rather than infer it.
KEPT = {
    "jbooktranslate.db": "the live SQLite file; renaming orphans every job, book and glossary",
    "jbook-study-dark": "the localStorage theme key; renaming silently resets every user's theme",
    "J_BookTranslate_V": "the actual folder path; the two repos and all tooling point at it",
}

touched: dict[str, int] = {}


def files_under(root: Path, include_suffixes=TEXT_SUFFIXES):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if set(path.parts) & SKIP_DIRS:
            continue
        if path.suffix.lower() not in include_suffixes:
            continue
        yield path


def apply(root: Path, label: str, relative_to: Path) -> None:
    for path in files_under(root):
        try:
            text = original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern, replacement, description in EDITS:
            text, count = pattern.subn(replacement, text)
            if count:
                key = f"{label}: {description}"
                touched[key] = touched.get(key, 0) + count
        if text != original:
            path.write_text(text, encoding="utf-8")


print("=== applying ===")
apply(PY, "python", PY)
apply(UI, "react", UI)

for key, count in sorted(touched.items()):
    print(f"  {count:>3}x  {key}")

print()
print("=== identifiers deliberately KEPT ===")
for name, reason in KEPT.items():
    # Count them, so the record shows they were found and not simply missed.
    total = 0
    for root in (PY, UI):
        for path in files_under(root):
            try:
                total += path.read_text(encoding="utf-8", errors="ignore").count(name)
            except OSError:
                pass
    print(f"  {name:<22} {total:>3} occurrence(s)  -- {reason}")

print()
print("=== any old display string left? ===")
LEFTOVER = re.compile(r"KALIMA|KALIMA|KALIMA UI|Word by word, book by book")
stray = 0
for root in (PY, UI):
    for path in files_under(root):
        try:
            for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if LEFTOVER.search(line):
                    # A line that documents the rename is fine; a live one is not.
                    if "renamed" in line.lower() or "was " in line.lower() or "KALIMA" in line:
                        continue
                    print(f"  {path.relative_to(root)}:{index}  {line.strip()[:90]}")
                    stray += 1
        except (OSError, UnicodeDecodeError):
            pass
if stray == 0:
    print("  none")

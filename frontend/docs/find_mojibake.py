"""Find every file whose text is double-encoded UTF-8.

The symptom is "the text is not readable" and nothing fixes it, because the
bytes are wrong before any styling is applied: the browser is handed the
mojibake of a Persian string, not the Persian string.

The signature is reliable. A correct Persian character never looks like Latin-1
supplement punctuation, and the letters that do appear (`` followed by
superscript digits, the classic UTF-8-as-Windows-1252 rendering) only ever turn
up in a file that has been through the wrong codec. Valid Persian text has no
`` and no run of characters in U+0080..U+00FF sitting between spaces.

Reports rather than fixes, so the blast radius is known first.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOTS = [Path(r"D:\J_BookTranslate_V\frontend"), Path(r"D:\J_BookTranslate_V")]
SUFFIXES = {".ts", ".tsx", ".js", ".mjs", ".css", ".html", ".json", ".md", ".py"}
SKIP = {"node_modules", ".git", "dist", ".venv", "__pycache__", ".test-tmp", "output"}

# The two characters that cannot occur in correctly-encoded Persian source but
# dominate the mojibake. U+00D9 is `` the first byte of every Arabic letter.
MARKERS = ("Ù", "Ø", "â€", "Ã©", "Ù„", "Å", "Æ")

rows = []
for root in ROOTS:
    for path in root.rglob("*"):
        if path.suffix not in SUFFIXES or not path.is_file():
            continue
        if any(part in SKIP for part in path.parts):
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            # Not even valid UTF-8: worse, and worth knowing about.
            rows.append((path, 0, 0, -1))
            continue
        markers = sum(text.count(m) for m in MARKERS)
        persian = sum(1 for ch in text if "؀" <= ch <= "ۿ")
        if markers and not (persian and markers < persian // 4):
            rows.append((path, persian, markers, 0))

rows.sort(key=lambda r: -r[2])

print(f"=== {len(rows)} file(s) with double-encoded text ===")
print("-" * 78)
for path, persian, markers, broken in rows:
    if broken == -1:
        print(f"  NOT VALID UTF-8   persian={persian:<5} {path}")
    else:
        print(f"  markers={markers:<5} persian={persian:<5} {path}")

print("-" * 78)
print(f"  total markers: {sum(r[2] for r in rows)}")

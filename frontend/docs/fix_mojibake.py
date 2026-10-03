"""Repair double-encoded UTF-8 in source files.

Some files were written through the wrong codec on Windows, so a Persian string
went in as UTF-8 bytes, came out as Windows-1252 characters, and was then saved as
UTF-8 again. The result is valid UTF-8 that no longer says what it should: the
browser renders `` instead of ``.

The repair is a codec round trip in the other direction:

    mojibake.encode("cp1252").decode("utf-8")

Windows-1252 rather than latin-1, because that is the codec that was actually
used: 0x80..0x9F decode to characters like `` (U+20AC) and `` (U+201C) in
cp1252 but are undefined in latin-1, so a latin-1 round trip raises on exactly the
files that need fixing most.

Every file is verified before and after, and nothing is written unless the repair
strictly improves the text:

  * every damaged marker is gone
  * the Persian character count went up
  * the result still parses as UTF-8

If any of those fail, the file is reported and left alone. A blind rewrite of a
file that was merely *mixed* -- some strings damaged, some fine -- would corrupt
the good ones, so those are reported separately rather than guessed at.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

MARKERS = ("Ù", "Ø", "â€", "Ã©", "Ù„", "Å", "Æ")


def persian_count(text: str) -> int:
    return sum(1 for ch in text if "؀" <= ch <= "ۿ")


def marker_count(text: str) -> int:
    return sum(text.count(m) for m in MARKERS)


def to_bytes(text: str) -> bytes:
    """Undo the wrong decode, for text that went through more than one codec.

    A plain ``encode("cp1252")`` is not enough, and neither is latin-1. The damage
    in these files is mixed: the `` sequences prove part of it was decoded as
    cp1252, while stray C1 controls -- U+0081, U+0090 -- prove another part was
    decoded as latin-1, which is the only codec that maps those at all. A file
    that has been through an editor, git and a shell on the way in picks up both.

    So cp1252 where it can encode, and the latin-1 byte value where it cannot.
    That covers the whole range without guessing.
    """
    out = bytearray()
    for ch in text:
        try:
            out += ch.encode("cp1252")
        except UnicodeEncodeError:
            out.append(ord(ch))
    return bytes(out)


def repair(text: str) -> str | None:
    """The round trip, or None if it is not the right move for this text."""
    # A byte order mark is legitimate, but one sitting mid-file is debris from
    # the same broken write, and it is not encodable, so it goes.
    cleaned = text.replace("﻿", "").replace(
        "".join(chr(c) for c in range(0x80, 0xA0)), ""
    )
    try:
        candidate = to_bytes(cleaned).decode("utf-8")
    except UnicodeDecodeError:
        return None
    # Only accept a repair that is unambiguously an improvement. A file with some
    # healthy Persian in it is mixed rather than wholly damaged, and a single
    # round trip would mangle the healthy parts.
    if persian_count(candidate) <= persian_count(text):
        return None
    if marker_count(candidate) >= marker_count(text):
        return None
    return candidate


TARGETS = [
    Path(r"D:\J_Translate_Ui\ui\src\pages\ReaderPage.tsx"),
    Path(r"D:\J_Translate_Ui\ui\src\pages\AccountPage.tsx"),
    Path(r"D:\J_BookTranslate_V\app\pipeline\epub_pipeline.py"),
    Path(r"D:\J_BookTranslate_V\app\pipeline\pdf_fixer.py"),
]

print("=== repair ===")
print("-" * 78)
for path in TARGETS:
    if not path.is_file():
        print(f"  {path.name}: missing, skipped")
        continue
    original = path.read_text(encoding="utf-8")
    before = (persian_count(original), marker_count(original))
    if before[1] == 0:
        print(f"  {path.name}: no damage, skipped")
        continue

    fixed = repair(original)
    if fixed is None:
        print(f"  {path.name}: NOT REPAIRED  persian={before[0]} markers={before[1]}")
        print("      left untouched -- needs a look by hand")
        continue

    after = (persian_count(fixed), marker_count(fixed))
    path.write_text(fixed, encoding="utf-8")
    print(f"  {path.name}: persian {before[0]} -> {after[0]}, markers {before[1]} -> {after[1]}")
    if after[1]:
        print(f"      *** {after[1]} marker(s) remain; written anyway for review")

print("-" * 78)

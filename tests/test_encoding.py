"""No module in ``app/`` may contain double-encoded text.

Two React pages shipped with every Persian string written as mojibake: the browser
showed `` where it should have shown ``. Two modules here had the same damage --
1,317 marker characters across ``app/pipeline/pdf_fixer.py`` alone, which is 103
lines of Persian comments and docstrings. Comments are not user-facing, so nothing
downstream caught it, and the generated documentation was unreadable.

Nothing in the toolchain can catch this. A mojibake file is valid UTF-8 and valid
Python, so it compiles, imports, passes every other test, and looks fine to ``git
diff``. Only a check on the *content* of the string finds it.

The signature is reliable: correctly encoded Persian never contains a character
from the Latin-1 supplement, and `` -- the UTF-8 bytes of U+2026 read as
Windows-1252 -- cannot occur in Persian source at all.
"""
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
SUFFIXES = {".py", ".html", ".css", ".js"}
SKIP = {"__pycache__"}

# What the damage looks like, in the forms it takes.
MARKERS = ("Ù", "Ø", "â€", "Ã©", "Å", "Æ")


def _persian(text: str) -> int:
    return sum(1 for ch in text if "؀" <= ch <= "ۿ")


def _markers(text: str) -> int:
    return sum(text.count(marker) for marker in MARKERS)


def _sources():
    for path in sorted(APP.rglob("*")):
        if path.suffix not in SUFFIXES or not path.is_file():
            continue
        if any(part in SKIP for part in path.parts):
            continue
        yield path


def test_app_contains_no_mojibake():
    """Every module under app/ decodes to the text it was written as."""
    damaged = []
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        hits = _markers(text)
        if hits:
            damaged.append(f"{path.relative_to(APP.parent)}: {hits} marker(s)")

    assert not damaged, (
        "double-encoded text found, which the browser would render as garbage. "
        "Reverse it with docs/fix_mojibake.py:\n  " + "\n  ".join(damaged)
    )


def test_app_still_holds_persian():
    """The guard above must not pass because the Persian is gone.

    The failure this file guards against has an inverse: if every Persian string
    were replaced with ASCII, the mojibake check would be perfectly happy and the
    product would have lost its language. ``app/`` is documented and commented in
    Persian, so Persian has to be present.
    """
    total = sum(_persian(path.read_text(encoding="utf-8")) for path in _sources())
    assert total > 500, f"only {total} Persian characters across app/"

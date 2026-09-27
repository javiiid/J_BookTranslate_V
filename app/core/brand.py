"""Brand assets for the Python pages.

The font is inlined as base64 by `app/core/fonts.py`, and the mark follows the
same idea for the same reason: `app/web.py` serves no static files, so an
`<img src="/brand/...">` would 404. Inlining puts the mark in the HTML that is
already being sent.

The SVGs live in `app/brand/`, copied there from the React project by
`D:\\J_Translate_Ui\\docs\\install_brand.py`. They are a copy, not the source:
the React project owns the artwork, because it is the one that will outlive this
Python app. Editing the files here means the two UIs drift apart silently.

Both variants are kept as files rather than generated, because they are artwork
and artwork does not belong in a string literal.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

BRAND_DIR = Path(__file__).parent.parent / "brand"

LIGHT = "kalima-mark-light.svg"
DARK = "kalima-mark-dark.svg"


def _read(name: str) -> str:
    candidate = BRAND_DIR / name
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"KALIMA brand asset {name!r} is missing from {BRAND_DIR}. "
        "Run: python D:\\J_Translate_Ui\\docs\\install_brand.py"
    )


@lru_cache(maxsize=2)
def kalima_mark(theme: str = "light", size: int = 40) -> str:
    """Return an inline ``<svg>`` for the KALIMA mark.

    ``theme`` picks the variant, which is not a simple inversion: on the light
    theme the blue is the ink and the cream is the paper, while on the dark
    theme the aqua becomes the ink and the document turns into the pale object.

    The width and height are forced to ``size`` because the source SVG is a
    512-unit master; everything else is left alone.
    """
    name = DARK if theme == "dark" else LIGHT
    svg = _read(name)
    # The master declares width/height, which would override any CSS sizing.
    svg = svg.replace('width="512"', f'width="{size}"', 1)
    svg = svg.replace('height="512"', f'height="{size}"', 1)
    return svg


def kalima_wordmark(size: int = 40, theme: str = "light") -> str:
    """The mark plus the product name, for headers and the welcome page.

    The name is real text, not part of the artwork, so it stays selectable,
    translatable and readable by a screen reader.
    """
    label = (
        '<span style="display:inline-flex;align-items:center;gap:10px;'
        'vertical-align:middle">'
        f"{kalima_mark(theme=theme, size=size)}"
        '<strong style="font-size:1.05em;letter-spacing:.14em">KALIMA</strong>'
        "</span>"
    )
    return label

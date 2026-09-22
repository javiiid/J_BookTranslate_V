"""Shared embedded font assets for local web pages."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def embedded_vazirmatn_font_faces() -> str:
    """Return local Vazirmatn files as inline CSS font faces."""
    fonts = (
        ("Vazirmatn-Regular.woff2", 400),
        ("Vazirmatn-Medium.woff2", 500),
        ("Vazirmatn-SemiBold.woff2", 600),
        ("Vazirmatn-Bold.woff2", 700),
        ("Vazirmatn-Black.woff2", 800),
    )
    font_dir = Path(__file__).parent.parent / "library"
    faces = []
    for filename, weight in fonts:
        encoded = base64.b64encode((font_dir / filename).read_bytes()).decode("ascii")
        faces.append(
            "@font-face{font-family:Vazirmatn;font-style:normal;"
            f"font-weight:{weight};src:url(data:font/woff2;base64,{encoded}) "
            "format('woff2');font-display:swap}"
        )
    return "<style>" + "".join(faces) + "</style>"

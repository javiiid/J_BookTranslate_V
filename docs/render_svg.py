"""Rasterise an SVG so it can actually be looked at.

There is no browser in this session, and an SVG that has never been rendered is
an SVG that has never been checked. PyMuPDF will open an SVG and render it, so
the mark can be inspected as an image before it ships.

Usage: python render_svg.py <in.svg> <out.png> [size]
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import pymupdf  # noqa: E402


def render(svg_path: Path, out_path: Path, size: int = 640) -> None:
    # PyMuPDF opens SVG as a document; one page, sized from the viewBox.
    document = pymupdf.open(str(svg_path))
    page = document[0]
    zoom = size / max(page.rect.width, page.rect.height)
    matrix = pymupdf.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=True)
    pixmap.save(str(out_path))
    document.close()
    print(f"  {svg_path.name}  ->  {out_path.name}  ({pixmap.width}x{pixmap.height})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(1)
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 640
    render(Path(sys.argv[1]), Path(sys.argv[2]), size)

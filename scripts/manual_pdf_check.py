# Manual visual check for the rewritten PDF outputs (no API key needed).
#
# Run:  python scripts/manual_pdf_check.py
# Open: output/manual-check/translated.pdf + bilingual.pdf
#
# What to look at:
#   1. Page count is small (a few pages for 60 segments, NOT 60 pages).
#   2. Book title on top of page 1.
#   3. Bilingual file: original next to translation, both columns filled.
#   4. Persian paragraphs shaped/joined, aligned right.
#   5. The flagged segment has a yellow background.

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz

from app.output.pdf import write_bilingual_pdf, write_translated_pdf

OUT_DIR = Path(__file__).resolve().parent.parent / "output" / "manual-check"


def build_segments(count=60):
    segments = []
    for i in range(count):
        segments.append(
            {
                "id": f"chunk-{i}",
                "position": i,
                "source": f"Original sentence number {i} with some filler words.",
                "target": f"متن پژوهش شماره {i} پایان.",
                "format": "epub",
                "chapter": "ch1.xhtml",
                "flagged": i == 5,
                "notes": ["ambiguous term kept as-is"] if i == 5 else [],
            }
        )
    return segments


def report(path):
    document = fitz.open(path)
    try:
        text = unicodedata.normalize(
            "NFKC", "".join(document[i].get_text() for i in range(len(document)))
        )
        fonts = sorted({font[3] for page in document for font in page.get_fonts()})
        print(f"  pages   : {len(document)}")
        print(f"  title   : {document.metadata.get('title')!r}")
        print(f"  fonts   : {fonts}")
        print(f"  has no.5: {'شماره 5' in text}")
        return len(document)
    finally:
        document.close()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    segments = build_segments()

    translated = OUT_DIR / "translated.pdf"
    bilingual = OUT_DIR / "bilingual.pdf"
    write_translated_pdf(segments, translated, title="Manual Check Book", to_lang="FA")
    write_bilingual_pdf(segments, bilingual, title="Manual Check Book", to_lang="FA")

    print(f"translated: {translated}")
    pages_t = report(translated)
    print(f"bilingual : {bilingual}")
    pages_b = report(bilingual)

    assert pages_t < len(segments), "pagination regressed: one page per segment again"
    assert pages_b < len(segments), "pagination regressed: one page per pair again"
    print("OK: flowing layout, open the PDFs and look at them.")


if __name__ == "__main__":
    main()

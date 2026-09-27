"""Prove the RTL fix: a FA target must now render right-to-left in exports.

Before the fix, none of the three `generate_outputs` call sites passed
`to_lang`, so it defaulted to `""` and every writer's
`rtl = str(to_lang).upper() in {"FA","AR","UR","HE"}` was False. A Persian
translation was therefore laid out left-to-right in every PDF/DOCX/TXT/MD.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"D:\J_BookTranslate_V")
sys.stdout.reconfigure(encoding="utf-8")

from app.output.formats import generate_outputs  # noqa: E402

PERSIAN = "این یک جملهٔ فارسی است که باید از راست به چپ رندر شود."


def build(lang):
    out = Path(tempfile.mkdtemp())
    segments = [{
        "id": "chunk-0",
        "source": "This is an English sentence.",
        "target": PERSIAN,
        "chapter": "OEBPS/ch01.xhtml",
        "chapter_title": "Chapter 1",
        "notes": [],
        "flagged": False,
    }]
    result = generate_outputs(
        segments,
        requested=["txt_bilingual", "markdown", "docx", "translated_pdf"],
        output_dir=out,
        base_name="book",
        filetype="epub",
        title="Book",
        to_lang=lang,
    )
    return out, result


failures = 0

def rtl_signals(lang):
    """Collect the direction-dependent signals the writers actually emit."""
    out, result = build(lang)
    produced = {name: Path(p) for name, p in (result.get("generated") or {}).items()}
    signals = {}

    docx_file = produced.get("docx")
    if docx_file and docx_file.exists():
        import zipfile
        with zipfile.ZipFile(docx_file) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
        # <w:bidi/> also appears in the unconditional default styles, so the
        # meaningful signal is how many paragraph properties carry it.
        signals["docx_bidi_count"] = xml.count("<w:pPr><w:bidi/></w:pPr>")

    md_file = produced.get("markdown")
    if md_file and md_file.exists():
        # Markdown has no directionality concept, so the only proof that
        # `to_lang` is threaded through is the metadata line it writes.
        body = md_file.read_text(encoding="utf-8")
        signals["md_lang_tagged"] = int(f"target language: {lang}" in body)

    pdf_file = produced.get("translated_pdf")
    if pdf_file and pdf_file.exists():
        import fitz
        with fitz.open(pdf_file) as document:
            page = document[0]
            signals["pdf_text"] = page.get_text()
    return signals


fa = rtl_signals("FA")
en = rtl_signals("EN")

print("=== direction signals, to_lang=FA vs to_lang=EN ===")
# Only signals that represent *direction* must increase for an RTL target.
RTL_SENSITIVE = {"docx_bidi_count"}
for key in sorted(set(fa) | set(en)):
    if key == "pdf_text":
        continue
    fa_value, en_value = fa.get(key), en.get(key)
    if key in RTL_SENSITIVE:
        ok = (fa_value or 0) > (en_value or 0)
        note = "FA must exceed EN"
    else:
        ok = (fa_value or 0) == 1 and (en_value or 0) == 1
        note = "to_lang reached the writer in both"
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {key:20} FA={fa_value}  EN={en_value}  ({note})")

print()
print("  (FA must produce strictly more RTL paragraph properties than EN)")

for label, signals in (("FA", fa), ("EN", en)):
    ok = signals.get("md_lang_tagged") == 1
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} markdown {label}: to_lang reached the writer")

# The PDF must still contain extractable Persian text in both cases.
for label, signals in (("FA", fa), ("EN", en)):
    text = signals.get("pdf_text", "")
    has_persian = any("؀" <= ch <= "ۿ" for ch in text)
    ok = has_persian
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} pdf {label}: {len(text)} chars, persian={has_persian}")

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)

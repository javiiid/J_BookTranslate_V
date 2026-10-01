# ============================================================
# app/output/convert.py
# ============================================================
"""
PURE FILE CONVERSION — without LLM translation.

Takes an already-existing book/subtitle file and renders it
into the other OUTPUT formats using only source extraction.
No API key is required.

Supported inputs : .epub  .pdf  .srt  .txt  .md
Supported outputs: json_segments · txt_bilingual · markdown
                   · docx · translated_pdf
                   (bilingual_pdf is omitted — it needs a
                   translation; translated_pdf is the same
                   engine with source == target)
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

from app.output.formats import SUFFIXES, generate_outputs
from app.output.typography import has_rtl, html_text

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

RTL_CHARS = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

def _html_to_text(value: str) -> str:
    return html_text(value)


def _detect_to_lang(sample: str) -> str:
    return "FA" if RTL_CHARS.search(sample or "") else "EN"


# ------------------------------------------------------------------
# Extractors — purely local, no network
# ------------------------------------------------------------------

def _extract_epub(input_path: Path):
    from app.pipeline.epub_handler import EPUBHandler

    all_chunks, chapter_map, _contexts = EPUBHandler.build_chunks(input_path)
    return all_chunks, chapter_map


def _extract_pdf(input_path: Path):
    import fitz

    doc = fitz.open(input_path)
    all_chunks = []
    chapter_map = {}
    for idx in range(len(doc)):
        text = doc[idx].get_text().strip()
        if not text:
            continue
        chunk_id = f"chunk-{idx}"
        all_chunks.append((chunk_id, text))
        chapter_map[chunk_id] = (f"page_{idx:04d}.html", 0)
    doc.close()
    return all_chunks, chapter_map


def _extract_srt(input_path: Path):
    from app.output.srt import parse_srt

    text = input_path.read_text(encoding="utf-8", errors="replace")
    blocks = parse_srt(text)
    all_chunks = []
    chapter_map = {}
    for pos, block in enumerate(blocks):
        if not block.text.strip():
            continue
        chunk_id = f"chunk-{pos}"
        all_chunks.append((chunk_id, block.text))
        chapter_map[chunk_id] = (f"block-{block.index}.srt", 0)
    return all_chunks, chapter_map


def _extract_txt(input_path: Path):
    raw = input_path.read_text(encoding="utf-8", errors="replace")
    # split on blank lines, keep non-empty paragraphs
    paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    if not paras:
        paras = [raw.strip()] if raw.strip() else []
    all_chunks = []
    chapter_map = {}
    for idx, para in enumerate(paras):
        chunk_id = f"chunk-{idx}"
        all_chunks.append((chunk_id, para))
        chapter_map[chunk_id] = (input_path.name, idx)
    return all_chunks, chapter_map


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

_CONVERT_FORMATS = {
    "json_segments",
    "txt_bilingual",
    "markdown",
    "docx",
    "translated_pdf",
}

_CONVERT_ALIASES = {
    "txt": "txt_bilingual",
    "md": "markdown",
    "pdf": "translated_pdf",
    "json": "json_segments",
}


def normalize_convert_formats(value) -> list[str]:
    """
    Like normalize_outputs but restricted to convert-safe formats.
    """
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
    elif value is None:
        return []
    else:
        parts = list(value or [])

    normalized: list[str] = []
    for name in parts:
        key = str(name).strip().lower()
        key = _CONVERT_ALIASES.get(key, key)
        # map bilingual_pdf -> translated_pdf for convert
        if key == "bilingual_pdf":
            key = "translated_pdf"
        if key not in _CONVERT_FORMATS:
            # also allow the canonical set from formats.py — silently map
            # unknown convert requests to the closest real format
            # but raise for truly unknown
            from app.output.formats import OUTPUT_FORMATS
            if key not in OUTPUT_FORMATS:
                raise ValueError(f"Unknown convert format '{name}'. Supported: {', '.join(sorted(_CONVERT_FORMATS))}.")
            # translated_epub / srt are source formats, not convert targets
            if key in {"translated_epub", "srt"}:
                continue
            key = {"bilingual_pdf": "translated_pdf"}.get(key, key)
            if key not in _CONVERT_FORMATS:
                continue
        if key not in normalized:
            normalized.append(key)
    return normalized


def build_convert_segments(all_chunks, chapter_map, filetype: str):
    """
    From raw chunks build the segment records expected by
    generate_outputs — source == target, never flagged.

    ## Why there are no ``blocks`` here

    An earlier version parsed each chunk's markup into blocks of runs and carried
    them on the segment, on the theory that structure should reach the writers.
    It did not: for an EPUB the DOCX is written by `epub_convert`, which reads
    the book file through pandoc, and the segment never got a look-in. So the
    parser ran on every chunk, the blocks rode along in memory, and
    `json_segments` dropped them on the floor on the way out.

    Measured on the same book, the two writers are not equal and were never going
    to be:

    * pandoc reads every structural element an EPUB has -- headings, lists,
      blockquotes, tables, images, links, `b`/`i`/`sup`/`br` -- and embeds the
      images as real `word/media/` parts: 6 of them, referenced by 6
      relationships. A converted illustrated book keeps its illustrations.
    * `app.output.docx` writes a correct document with embedded fonts and
      heading levels, but has no image support, so a picture becomes the text
      ``[تصویر: ...]``.

    So pandoc is the right writer for an EPUB and `app.output.docx` is the right
    writer for a PDF, an SRT or a text file -- sources that have no markup to
    preserve and no images to carry. Carrying a parallel structure model on the
    segment for the path that does not use it was the drift, and removing it is
    what makes the two writers one code path each.
    """
    segments = []
    for chunk_id, raw_html in all_chunks:
        chapter = ""
        loc = chapter_map.get(chunk_id)
        if isinstance(loc, dict):
            chapter = str(loc.get("item", "") or "")
        elif isinstance(loc, (tuple, list)) and len(loc) >= 1:
            chapter = str(loc[0])
        # raw may already be plain text (pdf/txt/srt) or HTML (epub)
        source = _html_to_text(raw_html) if "<" in str(raw_html) else str(raw_html).strip()
        if not source:
            continue
        # numeric position for stable ordering
        m = re.search(r"(\d+)\s*$", chunk_id)
        pos = int(m.group(1)) if m else 0
        segments.append(
            {
                "id": chunk_id,
                "position": pos,
                "source": source,
                "target": source,
                "format": filetype,
                "chapter": chapter,
                "flagged": False,
                "notes": [],
            }
        )
    # sort by chapter then position
    segments.sort(key=lambda s: (s["chapter"], s["position"]))
    return segments


def convert_file(
    input_path: Path | str,
    output_dir: Path | str,
    requested,
    title: str = "",
    to_lang: str | None = None,
) -> dict:
    """
    Convert *input_path* into every format in *requested*.

    Returns the same dict shape as generate_outputs:
        {"generated": {name: path}, "skipped": {}, "qa_report": None,
         "flagged": 0}
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = input_path.suffix.lower().lstrip(".")
    filetype = suffix if suffix in {"epub", "pdf", "srt", "txt", "md"} else suffix
    # normalize md -> txt family
    if filetype == "md":
        filetype = "txt"

    # -- extract
    if suffix == "epub":
        all_chunks, chapter_map = _extract_epub(input_path)
    elif suffix == "pdf":
        all_chunks, chapter_map = _extract_pdf(input_path)
    elif suffix == "srt":
        all_chunks, chapter_map = _extract_srt(input_path)
    elif suffix in {"txt", "md"}:
        all_chunks, chapter_map = _extract_txt(input_path)
    else:
        raise ValueError(f"فرمت ورودی پشتیبانی نمی‌شود: .{suffix}")

    if not all_chunks:
        raise ValueError("فایلی برای تبدیل یافت نشد یا محتوای قابل استخراج ندارد.")

    # -- language detection
    sample = " ".join(str(c) for _, c in all_chunks[:3])
    lang = (to_lang or _detect_to_lang(sample) or "FA")

    # -- segments
    segments = build_convert_segments(all_chunks, chapter_map, filetype)

    # -- normalize requested (accept both convert and full names)
    normalized = normalize_convert_formats(requested)
    if not normalized:
        raise ValueError("حداقل یک فرمت خروجی انتخاب کنید.")

    base_name = Path(title).stem if title else input_path.stem

    formatted = [name for name in normalized if suffix == "epub" and name in {"docx", "translated_pdf", "markdown"}]
    persian_pdf = suffix != "epub" and "translated_pdf" in normalized and any(has_rtl(segment["source"]) for segment in segments)
    result = generate_outputs(
        segments,
        requested=[name for name in normalized if name not in formatted and not (persian_pdf and name == "translated_pdf")],
        output_dir=output_dir,
        base_name=base_name,
        filetype=filetype,
        title=title or input_path.stem,
        to_lang=lang,
    )
    if formatted:
        from app.output.epub_convert import write_epub_output

        for name in formatted:
            target = output_dir / f"{base_name}{SUFFIXES[name]}"
            write_epub_output(input_path, target, name, lang)
            result["generated"][name] = str(target)
    if persian_pdf:
        from app.output.rtl_pdf import write_html_pdf

        target = output_dir / f"{base_name}.pdf"
        paragraphs = "".join(f'<p>{escape(segment["source"]).replace(chr(10), "<br>")}</p>' for segment in segments)
        write_html_pdf(f'<!doctype html><html><head><meta charset="utf-8"><title>{escape(title or base_name)}</title></head><body>{paragraphs}</body></html>', target)
        result["generated"]["translated_pdf"] = str(target)
    if "docx" in result["generated"]:
        from app.output.rtl_docx import fix_docx_typography

        # For every source, not just the non-EPUB ones.
        #
        # The condition used to be `suffix != "epub"`, on the assumption that an
        # EPUB's own markup was already suitable. It is not: the DOCX writer
        # flattens the markup to text, so the output needs the same direction,
        # spacing and font treatment as any other conversion. Skipping it meant an
        # EPUB conversion shipped with no embedded font at all -- measured: 0 font
        # parts in a 1.3 MB document that declared `Tahoma` and embedded nothing.
        fix_docx_typography(result["generated"]["docx"])
    return result

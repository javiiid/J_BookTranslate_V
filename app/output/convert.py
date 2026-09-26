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
from pathlib import Path

from app.output.formats import generate_outputs, normalize_outputs

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

RTL_CHARS = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\u200c]+")


def _html_to_text(value: str) -> str:
    text = _HTML_TAG_RE.sub(" ", str(value or ""))
    text = _WS_RE.sub(" ", text)
    # collapse space before punctuation
    text = re.sub(r"\s+([.!?,;:،؛»\"')\u2013\u2014\u2026-])", r"\1", text)
    return text.strip()


def _detect_to_lang(sample: str) -> str:
    return "FA" if RTL_CHARS.search(sample or "") else "EN"


# ------------------------------------------------------------------
# Extractors — purely local, no network
# ------------------------------------------------------------------

def _extract_epub(input_path: Path):
    from app.pipeline.epub_handler import EPUBHandler

    all_chunks, chapter_map = EPUBHandler.build_chunks(input_path)
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

    result = generate_outputs(
        segments,
        requested=normalized,
        output_dir=output_dir,
        base_name=base_name,
        filetype=filetype,
        title=title or input_path.stem,
        to_lang=lang,
    )
    return result

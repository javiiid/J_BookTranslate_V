# ============================================================
# app/output/__init__.py
# ============================================================
"""
Output format generation for J Book Translate.

Runs after translation and before final storage; produces every
requested OUTPUT format (JSON_SEGMENTS, TXT_BILINGUAL, MARKDOWN,
DOCX, TRANSLATED_PDF, BILINGUAL_PDF, SRT) plus QA_REPORT data.
"""

from app.output.formats import (
    OUTPUT_FORMATS,
    available_output_formats,
    emit_outputs,
    generate_outputs,
    normalize_outputs,
)
from app.output.markers import (
    extract_markers,
    strip_markers,
)
from app.output.segments import (
    build_qa_report,
    build_segments,
)

__all__ = [
    "OUTPUT_FORMATS",
    "available_output_formats",
    "build_qa_report",
    "build_segments",
    "emit_outputs",
    "extract_markers",
    "generate_outputs",
    "normalize_outputs",
    "strip_markers",
]
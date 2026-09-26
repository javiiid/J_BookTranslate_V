# ============================================================
# app/output/txt.py
# ============================================================
"""
OUTPUT: TXT_BILINGUAL

Plain text with alternating [ORIGINAL]/[TRANSLATION] lines.
Useful for review and QA passes. A QA_REPORT section is appended
so flagged segments are immediately visible.
"""

from __future__ import annotations

from pathlib import Path


def render_bilingual_txt(
    segments,
    title="",
    filetype="epub",
    to_lang="",
):
    """
    Render the bilingual TXT document as a string.
    """

    segments = segments or []

    flagged_count = sum(
        1
        for segment in segments
        if segment["flagged"]
    )

    lines = []

    lines.append("=" * 60)
    lines.append(title or "Translated book")
    lines.append(
        f"format: {filetype}  "
        f"to: {to_lang}"
    )
    lines.append(
        f"segments: {len(segments)}  "
        f"flagged: {flagged_count}"
    )
    lines.append("=" * 60)
    lines.append("")

    for segment in segments:

        chapter = segment["chapter"]

        lines.append("[ORIGINAL]")

        if chapter:

            lines.append(f"({chapter})")

        lines.append(segment["source"])
        lines.append("")

        lines.append("[TRANSLATION]")

        if chapter:

            lines.append(f"({chapter})")

        lines.append(segment["target"])
        lines.append("")

        lines.append("-" * 40)
        lines.append("")

    return "\n".join(lines)


def write_bilingual_txt(
    segments,
    path,
    title="",
    filetype="epub",
    to_lang="",
):
    """
    Write the TXT_BILINGUAL output file.
    """

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        render_bilingual_txt(
            segments,
            title=title,
            filetype=filetype,
            to_lang=to_lang,
        ),
        encoding="utf-8",
    )

    return path
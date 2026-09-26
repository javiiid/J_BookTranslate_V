# ============================================================
# app/output/markdown.py
# ============================================================
"""
OUTPUT: MARKDOWN

Translated Markdown preserving the book structure. Suitable for
import into static sites, Obsidian, Notion, etc.
"""

from __future__ import annotations

from pathlib import Path

from app.output.segments import chapter_title

from app.output.markers import NOTE_RE


def _target_lines(segment):
    """
    Render the translation, keeping inline NOTE markers visible
    as blockquotes so QA information survives the export.
    """

    text = segment["target"]

    if not segment["notes"]:

        lines = [
            line.strip()
            for line in str(text or "").splitlines()
            if line.strip()
        ]

        return lines or [""]

    note_marks = sorted(
        set(NOTE_RE.findall(str(segment["target"]) or "")),
        key=len,
        reverse=True,
    )

    quoted = [
        f"> {note}"
        for note in segment["notes"]
        if note and note not in note_marks
    ]

    rendered = [
        line.strip()
        for line in str(text or "").splitlines()
        if line.strip()
    ] or [""]

    return rendered + quoted


def render_markdown(
    segments,
    title="",
    filetype="epub",
    to_lang="",
):
    """
    Render the translated Markdown document as a string.
    """

    segments = segments or []

    lines = []

    if title:

        lines.append(f"# {title}")

        lines.append("")

        if filetype:

            lines.append(
                f"> Translated from {filetype.upper()} "
                f"source, target language: {to_lang}"
            )

            lines.append("")

    current_chapter = None

    first_paragraph = True

    for segment in segments:

        heading = chapter_title(
            segment["chapter"]
        )

        if heading != current_chapter:

            current_chapter = heading

            lines.append("")

            lines.append(f"## {heading}")

            lines.append("")

        for line in _target_lines(segment):

            if not first_paragraph:

                lines.append("")

            lines.append(line)

            first_paragraph = False

    return "\n".join(lines).strip() + "\n"


def write_markdown(
    segments,
    path,
    title="",
    filetype="epub",
    to_lang="",
):
    """
    Write the MARKDOWN output file.
    """

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        render_markdown(
            segments,
            title=title,
            filetype=filetype,
            to_lang=to_lang,
        ),
        encoding="utf-8",
    )

    return path
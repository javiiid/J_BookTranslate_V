# ============================================================
# app/output/formats.py
# ============================================================
"""
Output format registry and dispatcher.

This is the "صرفاً بعد از ترجمه، قبل از ذخیرهسازی" stage: given
the completed translation state (chunks + translations +
chapter_map) it produces every requested OUTPUT format and a
QA_REPORT.
"""

from __future__ import annotations

from pathlib import Path

from app.output import docx, json_segments, markdown, pdf, txt
from app.output.markers import strip_markers
from app.output.segments import build_qa_report, build_segments
from app.pipeline import quality_scorer

OUTPUT_FORMATS = {
    "json_segments": (
        "machine-readable segment pairs for Translation Memory"
    ),
    "txt_bilingual": (
        "plain text with alternating [ORIGINAL]/[TRANSLATION]"
    ),
    "markdown": "translated Markdown preserving structure",
    "docx": "translated Word document with RTL support",
    "translated_pdf": "translation-only PDF",
    "bilingual_pdf": "original + translation PDF",
    "translated_epub": (
        "translated EPUB (the primary EPUB output)"
    ),
    "srt": "translated subtitles with preserved timecodes",
    "quality_report": (
        "six-dimension chunk quality scores (QA) as JSON"
    ),
}

ALIASES = {
    "json": "json_segments",
    "segments": "json_segments",
    "bilingual": "bilingual_pdf",
    "txt": "txt_bilingual",
    "md": "markdown",
    "quality": "quality_report",
}

SUFFIXES = {
    "json_segments": ".segments.json",
    "txt_bilingual": ".bilingual.txt",
    "markdown": ".md",
    "docx": ".docx",
    "translated_pdf": ".pdf",
    "bilingual_pdf": ".bilingual.pdf",
    "quality_report": ".quality.json",
}


def normalize_outputs(value):
    """
    Normalize a format list or comma-separated string.

    Returns:
        list[str]: canonical lowercase format names.

    Raises:
        ValueError: when any format name is unknown.
    """

    if isinstance(value, str):

        value = [
            part.strip()
            for part in value.split(",")
            if part.strip()
        ]

    if value is None:

        return []

    normalized = []

    for name in value or []:

        key = str(name).strip().lower()

        key = ALIASES.get(key, key)

        if key not in OUTPUT_FORMATS:

            known = ", ".join(sorted(OUTPUT_FORMATS))

            raise ValueError(
                f"Unknown output format '{name}'. "
                f"Supported: {known}."
            )

        if key not in normalized:

            normalized.append(key)

    return normalized


def available_output_formats():
    """
    List of canonical output format names.
    """

    return sorted(OUTPUT_FORMATS)


def generate_outputs(
    segments,
    requested,
    output_dir,
    base_name,
    filetype="epub",
    title="",
    to_lang="",
    scorer=None,
):
    """
    Generate every requested output format into ``output_dir``.

    When ``scorer`` is supplied and ``quality_report`` is
    requested, every segment is scored before the writers run so
    that JSON_SEGMENTS carries per-segment ``quality`` and the
    ``quality_report`` file is written.

    Returns:
        dict:
            {
                "generated": {name: absolute path},
                "skipped":   {name: reason},
                "qa_report": QA_REPORT text or None,
                "flagged":   number of flagged segments,
                "quality":   quality summary dict or None,
            }
    """

    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    filetype = str(filetype).lower().lstrip(".")

    normalized = normalize_outputs(requested)

    if scorer is not None and "quality_report" in normalized:
        quality_scorer.score_and_attach(segments, scorer)

    generated = {}

    skipped = {}

    for name in normalized:

        if name == "translated_epub":

            if filetype == "epub":

                skipped[name] = (
                    "the reassembled EPUB is the "
                    "primary output of this job"
                )

            else:

                skipped[name] = (
                    "regionalized EPUB output requires "
                    "an EPUB source file"
                )

            continue

        if name == "srt":

            if filetype == "srt":

                skipped[name] = (
                    "the translated SRT is the primary "
                    "output of this job"
                )

            else:

                skipped[name] = (
                    "SRT output requires a subtitle source"
                )

            continue

        target = (
            output_dir
            / f"{base_name}{SUFFIXES[name]}"
        )

        if name == "json_segments":

            json_segments.write_json_segments(
                segments,
                target,
                title=title,
                to_lang=to_lang,
            )

        elif name == "txt_bilingual":

            txt.write_bilingual_txt(
                segments,
                target,
                title=title,
                filetype=filetype,
                to_lang=to_lang,
            )

        elif name == "markdown":

            markdown.write_markdown(
                segments,
                target,
                title=title,
                filetype=filetype,
                to_lang=to_lang,
            )

        elif name == "docx":

            docx.write_docx(
                segments,
                target,
                title=title,
                to_lang=to_lang,
            )

        elif name == "translated_pdf":

            pdf.write_translated_pdf(
                segments,
                target,
                title=title,
                to_lang=to_lang,
            )

        elif name == "bilingual_pdf":

            pdf.write_bilingual_pdf(
                segments,
                target,
                title=title,
                to_lang=to_lang,
            )

        elif name == "quality_report":

            if not any(
                segment.get("quality")
                for segment in segments or []
            ):

                skipped[name] = (
                    "quality scoring did not run "
                    "(no scorer or no translated chunks)"
                )

                continue

            quality_scorer.write_quality_report(
                segments,
                target,
                title=title,
                filetype=filetype,
                to_lang=to_lang,
            )

        generated[name] = str(target)

    flagged_count = sum(
        1
        for segment in segments or []
        if segment["flagged"]
    )

    qa_report = None

    if flagged_count:

        qa_report = build_qa_report(
            segments,
            title=title,
            filetype=filetype,
        )

    return {
        "generated": generated,
        "skipped": skipped,
        "qa_report": qa_report,
        "flagged": flagged_count,
        "quality": quality_scorer.summary_from_segments(segments),
    }


def emit_outputs(
    input_path,
    output_path,
    all_chunks,
    translations,
    chapter_map,
    filetype="epub",
    requested=None,
    title="",
    to_lang="",
    scorer=None,
):
    """
    Pipeline hook: build segments, generate outputs and return
    cleaned translations (QA markers removed) for reassembly.
    """

    if not normalize_outputs(requested):

        return (
            {},
            None,
            translations,
        )

    segments = build_segments(
        all_chunks,
        translations,
        chapter_map,
        filetype,
    )

    output_path = Path(output_path)

    result = generate_outputs(
        segments,
        requested=requested,
        output_dir=output_path.parent,
        base_name=output_path.stem,
        filetype=filetype,
        title=title or Path(input_path).stem,
        to_lang=to_lang,
        scorer=scorer,
    )

    cleaned = {
        chunk_id: strip_markers(value)
        for chunk_id, value
        in translations.items()
    }

    return (
        result,
        segments,
        cleaned,
    )
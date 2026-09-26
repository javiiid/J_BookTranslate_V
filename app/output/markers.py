# ============================================================
# app/output/markers.py
# ============================================================
"""
QA markers used across all output formats.

The translation engine appends two inline markers to its output:

    {NOTE: explanation}
        Used when a passage is ambiguous and the closest faithful
        meaning was kept. The explanation documents the decision.

    {BOUNDARY_WARNING}
        Used when a chunk appears cut off at the start or end, so
        the model never silently guesses the missing words.

Every output generator removes the markers and converts them into
structured QA data (``flagged`` / ``notes``), a highlighted visual
in PDF/DOCX, and a QA_REPORT section for review.
"""

from __future__ import annotations

import re


NOTE_PATTERN = r"\{NOTE:\s*(.*?)\}"

NOTE_RE = re.compile(
    NOTE_PATTERN,
    re.DOTALL,
)

BOUNDARY_RE = re.compile(
    r"\{BOUNDARY_WARNING\}",
    re.IGNORECASE,
)

FLAG_NOTE = "note"

FLAG_BOUNDARY = "boundary"


def extract_markers(text):
    """
    Remove QA markers from translated text.

    Returns:
        tuple:
            (clean_text, flags, notes)

            - clean_text:
                Translation with all markers removed.
            - flags:
                A list of flag names ("note"/"boundary").
            - notes:
                The collected ``{NOTE: ...}`` explanations.
    """

    if not text:

        return "", [], []

    text = str(text)

    flags = []

    notes = []

    if BOUNDARY_RE.search(text):

        flags.append(FLAG_BOUNDARY)

    for match in NOTE_RE.finditer(text):

        flags.append(FLAG_NOTE)

        note = match.group(1).strip()

        if note:

            notes.append(note)

    clean = NOTE_RE.sub("", text)

    clean = BOUNDARY_RE.sub("", clean)

    return clean.strip(), flags, notes


def strip_markers(text):
    """
    Return translated text with all QA markers removed.
    """

    clean, _, _ = extract_markers(text)

    return clean


def detect_cut_boundary(text):
    """
    Heuristic check for a chunk that starts or ends mid-sentence.

    The model is the authoritative source of ``{BOUNDARY_WARNING}``;
    this helper only backs QA tooling and does not auto-flag output.
    """

    stripped = str(text or "").strip()

    if not stripped:

        return False

    if re.match(r"^[a-z]", stripped):

        return True

    return not stripped.endswith(
        (
            ".",
            "?",
            "!",
            ":",
            "»",
            "…",
        )
    )
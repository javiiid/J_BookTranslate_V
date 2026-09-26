# ============================================================
# app/pipeline/quality_scorer.py
# ============================================================
"""
CHUNK QUALITY SCORER

Post-translation QA stage. Scores every translated chunk on six
dimensions and flags chunks that need a human reviewer:

    Accuracy            30%   meaning preserved?
    Fluency             25%   natural target language?
    Terminology         15%   glossary respected? (N/A without glossary)
    Format Preservation 15%   tags/timecodes intact?
    Boundary Integrity  10%   clean sentence boundaries?
    Length Ratio         5%   plausible source/target length?

Modes
-----
full   LLM scores all six dimensions (temperature=0.0).
light  LLM scores only Accuracy and Fluency; the rest is
       rule-based — for weaker/cheaper models.
rules  no LLM at all: tags/timecodes, boundary heuristics,
       glossary term checks and length ratio only.

The stage is opt-in: it only runs when ``quality_report`` is part
of the requested output formats (``--outputs quality_report`` or
the dashboard checkbox). LLM scoring runs in parallel across
chunks and never breaks the job — on any API or parse failure the
chunk falls back to rule-based scores plus a flag reason.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from app.core.config import read_config_safe
from app.output.markers import BOUNDARY_RE, NOTE_RE, strip_markers

# ── dimension names and weights ────────────────────────────────

DIMENSIONS = (
    "accuracy",
    "fluency",
    "terminology",
    "format_preservation",
    "boundary_integrity",
    "length_ratio",
)

WEIGHTS = {
    "accuracy": 0.30,
    "fluency": 0.25,
    "terminology": 0.15,
    "format_preservation": 0.15,
    "boundary_integrity": 0.10,
    "length_ratio": 0.05,
}

COMPOSITE_THRESHOLD = 6.5
ACCURACY_THRESHOLD = 6.0
FORMAT_THRESHOLD = 5.0
LENGTH_TOLERANCE = 0.30

LENGTH_RATIO_RANGES = {
    ("EN", "FA"): (0.9, 1.4),
    ("EN", "AR"): (0.9, 1.4),
    ("EN", "TR"): (0.9, 1.35),
    ("FA", "EN"): (0.7, 1.1),
}
DEFAULT_LENGTH_RATIO_RANGE = (0.75, 1.5)

MODES = ("full", "light", "rules")

# ── flag reasons (machine-readable tokens) ─────────────────────

FLAG_COMPOSITE = "composite below 6.5"
FLAG_ACCURACY = "accuracy below 6"
FLAG_BOUNDARY = "{BOUNDARY_WARNING} present"
FLAG_NOTE = "{NOTE:} present"
FLAG_FORMAT = "format preservation below 5"
FLAG_LENGTH = "length ratio outside +/-30% of expected range"
FLAG_SCORER_ERROR = "scorer error, rule-based fallback"

# ── prompt tokens (safe substitution — prompt contains literal
#    JSON braces so we avoid str.format) ────────────────────────

TOKEN_RE = re.compile(r"\{\{(\w+)\}\}")

SCORER_SYSTEM_MESSAGE = (
    "You are a senior translation quality auditor for book publishing. "
    "Answer with a single JSON object only — no markdown, no commentary."
)

SCORER_PROMPT_TEMPLATE = """You are a senior translation quality auditor for book publishing.

You will receive one chunk of a book in $source_language, already translated into $target_language. The chunk comes from a $file_format file.

INPUT STRUCTURE:
- chunk_id
- source_language
- target_language
- file_format
- original_text
- translated_text
- glossary_entries

EVALUATION DIMENSIONS (score each from 0 to 10):

1. Accuracy (weight 30%)
- Does the translation preserve the meaning of the original text?
- Are there omissions, additions, distortions, or mistranslations?
- Penalize any change that would alter the reader's understanding.

2. Fluency (weight 25%)
- Does the translation read naturally in $target_language?
- Penalize literal, awkward, robotic, or grammatically broken output.

3. Terminology (weight 15%)
- Are domain-specific terms translated consistently?
- If glossary entries are provided, check whether the required terms are used correctly.
- If no glossary is provided, score this dimension as null (N/A).

4. Format Preservation (weight 15%)
- Are tags, markers, timecodes, and formatting intact?
- For EPUB/HTML chunks the structural tags must be preserved and balanced.
- For SRT subtitles the timecodes must remain unchanged.
- The markers {NOTE: ...} and {BOUNDARY_WARNING} are legitimate QA annotations, not damage.

5. Boundary Integrity (weight 10%)
- Does the chunk start and end at clean sentence boundaries?
- If {BOUNDARY_WARNING} is present, the chunk was likely cut mid-sentence. Deduct 3 points automatically if {BOUNDARY_WARNING} is present in the translation.

6. Length Ratio (weight 5%)
- Compare the length of the translation with the original text.
- For English to Persian, a healthy ratio is 0.9 to 1.4 (the translation is usually longer).
- The expected range varies by language pair; flag a ratio outside plus/minus 30% of that range.

COMPOSITE SCORING:
- composite = weighted average of the applicable dimensions, rounded to 2 decimals.
- Weights: accuracy 0.30, fluency 0.25, terminology 0.15, format_preservation 0.15, boundary_integrity 0.10, length_ratio 0.05.
- If Terminology is N/A, redistribute its 15% proportionally to Accuracy and Fluency.

FLAG CONDITIONS (set flagged to true and list a short reason for each):
- composite < 6.5
- accuracy < 6
- {BOUNDARY_WARNING} is present in the translation
- {NOTE:} is present in the translation
- format preservation < 5
- length ratio is outside plus/minus 30% of the expected range
- a proper noun or key term appears in the source but is absent from the translation
- a critical omission changes the meaning of the passage

OUTPUT FORMAT:
Respond with one JSON object only. No markdown fences, no commentary.

{
  "chunk_id": "...",
  "scores": {
    "accuracy": 0.0,
    "fluency": 0.0,
    "terminology": 0.0,
    "format_preservation": 0.0,
    "boundary_integrity": 0.0,
    "length_ratio": 0.0
  },
  "composite": 0.0,
  "flagged": false,
  "flag_reasons": ["short reason"],
  "notes": "optional short note if a {NOTE:} was present"
}

INPUT VALUES:
chunk_id: {{chunk_id}}
source_language: {{source_language}}
target_language: {{target_language}}
file_format: {{file_format}}
glossary_entries:
{{glossary_entries}}
original_text:
{{original_text}}
translated_text:
{{translated_text}}
"""

SCORER_LIGHT_PROMPT_TEMPLATE = """You are a senior translation quality auditor for book publishing.

Score ONLY two dimensions of this chunk, from 0 to 10:

1. Accuracy (weight 30%)
- Does the translation preserve the meaning of the original text?
- Are there omissions, additions, distortions, or mistranslations?

2. Fluency (weight 25%)
- Does the translation read naturally in $target_language?
- Penalize literal, awkward, robotic, or grammatically broken output.

All other dimensions (terminology, format preservation, boundary integrity, length ratio) are computed automatically by rule-based checks — do not score them.

FLAG CONDITIONS (set flagged to true and list a short reason for each):
- accuracy < 6
- a proper noun or key term appears in the source but is absent from the translation
- a critical omission changes the meaning of the passage

OUTPUT FORMAT:
Respond with one JSON object only. No markdown fences, no commentary.

{
  "chunk_id": "...",
  "scores": {
    "accuracy": 0.0,
    "fluency": 0.0
  },
  "flagged": false,
  "flag_reasons": ["short reason"],
  "notes": ""
}

INPUT VALUES:
chunk_id: {{chunk_id}}
source_language: {{source_language}}
target_language: {{target_language}}
file_format: {{file_format}}
glossary_entries:
{{glossary_entries}}
original_text:
{{original_text}}
translated_text:
{{translated_text}}
"""


# ── ChunkScore ─────────────────────────────────────────────────

@dataclass
class ChunkScore:
    """Score record for one translated chunk."""

    chunk_id: str
    scores: dict
    composite: float
    flagged: bool
    flag_reasons: list
    notes: str = ""
    mode: str = "full"

    @classmethod
    def from_dict(cls, data, chunk_id="", mode="full"):
        """
        Build a ChunkScore from parsed LLM JSON, clamping values to
        0–10 and recomputing composite from the configured weights.
        """

        if not isinstance(data, dict):
            raise ValueError("scorer response is not a JSON object")

        raw_scores = data.get("scores")
        if not isinstance(raw_scores, dict):
            raise ValueError("scorer response is missing 'scores'")

        scores = {}
        for dim in DIMENSIONS:
            if dim not in raw_scores:
                continue
            value = raw_scores[dim]
            if value is None:
                scores[dim] = None
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            scores[dim] = max(0.0, min(10.0, value))

        reasons = data.get("flag_reasons") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        reasons = [str(reason).strip() for reason in reasons if str(reason).strip()]
        if data.get("flagged") and not reasons:
            reasons.append("flagged by scorer")

        notes = data.get("notes")
        notes = str(notes) if notes else ""

        return cls(
            chunk_id=str(data.get("chunk_id") or chunk_id),
            scores=scores,
            composite=composite_score(scores),
            flagged=bool(data.get("flagged")) or bool(reasons),
            flag_reasons=reasons,
            notes=notes,
            mode=mode,
        )

    def as_storage(self):
        """
        Record inserted into every segment that carries a score.
        """

        return {
            "composite": self.composite,
            "flag_reasons": list(self.flag_reasons),
            "scores": {dim: self.scores.get(dim) for dim in DIMENSIONS},
            "notes": self.notes,
        }


# ── helpers ────────────────────────────────────────────────────

def resolve_mode(mode=None, client=None):
    """
    Return one of 'full', 'light', 'rules'.
    No client implies rule-based scoring only.
    """

    if client is None:
        return "rules"
    if mode in MODES:
        return mode
    try:
        configured = (
            (read_config_safe().get("quality") or {}).get("mode")
        )
    except Exception:
        configured = None
    if configured in MODES:
        return configured
    return "full"


def _default_workers():
    try:
        value = int(get_translation_config().get("max_concurrency", 3))
    except Exception:
        value = 3
    return max(1, min(value, 8))


def get_translation_config():
    from app.core.config import read_config_safe
    return (read_config_safe().get("translation") or {})


def expected_length_range(source_lang, target_lang):
    key = (
        str(source_lang or "").upper(),
        str(target_lang or "").upper(),
    )
    return LENGTH_RATIO_RANGES.get(key, DEFAULT_LENGTH_RATIO_RANGE)


def _plain(text):
    text = strip_markers(str(text or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def length_ratio_value(source_text, translated_text):
    source_plain = _plain(source_text)
    if len(source_plain) <= 0:
        return None
    return len(_plain(translated_text)) / len(source_plain)


def length_out_of_range(ratio, lo, hi):
    if ratio is None:
        return False
    return ratio < lo * (1 - LENGTH_TOLERANCE) or ratio > hi * (1 + LENGTH_TOLERANCE)


def composite_score(scores):
    """
    Weighted average over applicable (non-null) dimensions.
    When Terminology is null its weight is redistributed
    proportionally to Accuracy and Fluency, as per spec.
    """

    scores = scores or {}
    applicable = {
        dim: scores[dim]
        for dim in DIMENSIONS
        if scores.get(dim) is not None
    }
    if not applicable:
        return 0.0

    weights = {}
    if scores.get("terminology") is None and "terminology" in WEIGHTS:
        extra = WEIGHTS["terminology"]
        primary = [
            dim for dim in ("accuracy", "fluency")
            if dim in applicable
        ]
        if primary:
            share = sum(WEIGHTS[dim] for dim in primary)
            for dim in primary:
                weights[dim] = WEIGHTS[dim] + extra * WEIGHTS[dim] / share
    for dim, value in applicable.items():
        if dim not in weights:
            weights[dim] = WEIGHTS[dim]

    total = sum(weights.values())
    if total <= 0:
        return 0.0
    return round(
        sum(weights[dim] * applicable[dim] for dim in applicable) / total,
        2,
    )


# ── rule-based dimension scorers ───────────────────────────────

TAG_RE = re.compile(r"<[^>]+>")
TIMECODE_RE = re.compile(r"\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}")


def rule_format_score(source_text, translated_text, filetype="epub"):
    """
    Structural markers preserved? Tags for EPUB, timecodes for SRT.
    """

    filetype = str(filetype or "epub").lower().lstrip(".")
    if filetype == "srt":
        source_tokens = TIMECODE_RE.findall(str(source_text or ""))
        target_tokens = TIMECODE_RE.findall(str(translated_text or ""))
    else:
        source_tokens = [t.lower() for t in TAG_RE.findall(str(source_text or ""))]
        target_tokens = [t.lower() for t in TAG_RE.findall(str(translated_text or ""))]
    if not source_tokens:
        return 10.0 if not target_tokens else 6.0
    missing = sum(
        (Counter(source_tokens) - Counter(target_tokens)).values()
    )
    ratio = missing / len(source_tokens)
    if ratio <= 0:
        return 10.0
    if ratio <= 0.10:
        return 8.0
    if ratio <= 0.50:
        return 5.0
    if ratio < 1.0:
        return 3.0
    return 0.0


def rule_boundary_score(source_text):
    """
    Base boundary integrity before the automatic {BOUNDARY_WARNING}
    deduction. A clean chunk scores 10; a cut at one end 5; both 2.
    """

    stripped = str(source_text or "").strip()
    if not stripped:
        return 10.0
    start_cut = bool(re.match(r"^[a-z]", stripped))
    end_cut = not stripped.endswith((".", "?", "!", ":", "»", "…"))
    if start_cut and end_cut:
        return 2.0
    if start_cut or end_cut:
        return 5.0
    if stripped.endswith((",", ";", "—", "-", "،", "؛")):
        return 8.0
    return 10.0


def rule_length_score(ratio, lo, hi):
    """
    Length plausibility score based on deviation from the expected
    range for the language pair.
    """

    if ratio is None:
        return None
    if lo <= ratio <= hi:
        return 10.0
    distance = (lo - ratio) / lo if ratio < lo else (ratio - hi) / hi
    if distance <= 0.15:
        return 7.0
    if distance <= LENGTH_TOLERANCE:
        return 4.0
    return 1.0


def rule_terminology_score(source_text, translated_text, glossary):
    """
    Rule-based terminology check using glossary snapshot.
    Returns None when no glossary or no term is relevant to this chunk.
    """

    from app.glossary.service import check_translation, matching_terms
    if not glossary or not glossary.get("terms"):
        return None
    try:
        matched = matching_terms(str(source_text or ""), glossary)
    except Exception:
        return None
    if not matched:
        return None
    missing = check_translation(
        str(source_text or ""),
        str(translated_text or ""),
        glossary,
    )
    missing_ratio = len(missing) / len(matched)
    if missing_ratio <= 0:
        return 10.0
    if missing_ratio < 1.0 and len(missing) == 1:
        return 7.0
    if missing_ratio <= 0.5:
        return 5.0
    if missing_ratio < 1.0:
        return 2.0
    return 0.0


# ── prompt building ────────────────────────────────────────────

def _glossary_entries(source_text, glossary):
    """Relevant glossary lines for this chunk, or NONE."""
    if not glossary or not glossary.get("terms"):
        return "NONE"
    try:
        from app.glossary.service import matching_terms
        matched = matching_terms(str(source_text or ""), glossary)
    except Exception:
        matched = []
    if not matched:
        return "NONE"
    return "\n".join(
        f"{term.get('source_term', '')} -> {term.get('target_term', '')}"
        for term in matched
    )


def build_scorer_prompt(
    chunk_id,
    source_text,
    translated_text,
    source_lang,
    target_lang,
    file_format="epub",
    glossary=None,
    mode="full",
):
    """
    Render the scorer prompt with chunk values.
    Uses ``string.Template`` because the prompt itself contains literal
    JSON braces that would confuse ``str.format``.
    """

    import string
    template = (
        SCORER_LIGHT_PROMPT_TEMPLATE
        if mode == "light"
        else SCORER_PROMPT_TEMPLATE
    )
    values = {
        "chunk_id": str(chunk_id),
        "source_language": str(source_lang or ""),
        "target_language": str(target_lang or ""),
        "file_format": str(file_format or ""),
        "glossary_entries": _glossary_entries(source_text, glossary),
        "original_text": str(source_text or ""),
        "translated_text": str(translated_text or ""),
    }
    return TOKEN_RE.sub(
        lambda match: values.get(match.group(1), match.group(0)),
        template,
    )


def parse_scorer_response(content, chunk_id="", mode="full"):
    """
    Parse the LLM response into a ChunkScore.
    Robust against code fences and prose surrounding the JSON object.
    """

    text = str(content or "").strip()
    if not text:
        raise ValueError("empty scorer response")
    if text.startswith("```"):
        text = re.sub(r"^```[A-Za-z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("scorer response contains no JSON object")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as error:
        raise ValueError(
            f"scorer response is not valid JSON: {error}"
        ) from error
    return ChunkScore.from_dict(data, chunk_id=chunk_id, mode=mode)


# ── core scoring function ──────────────────────────────────────

def score_chunk(
    chunk_id,
    source_text,
    translated_text,
    source_lang,
    target_lang,
    file_format="epub",
    glossary=None,
    llm_client=None,
    model=None,
    mode="full",
    stop_event=None,
) -> ChunkScore:
    """
    Score a single chunk on all six dimensions.

    Rule-based dimensions (format, boundary, length, terminology) are
    always computed. LLM contributes Accuracy and Fluency (and the
    remaining dimensions in ``full`` mode). On any API or parse
    failure the chunk falls back to rule-based scores and is flagged
    so the reviewer notices the incomplete scoring.
    """

    source_text = str(source_text or "")
    translated_text = str(translated_text or "")

    boundary_warning = bool(BOUNDARY_RE.search(translated_text))
    has_note = bool(NOTE_RE.search(translated_text))

    lo, hi = expected_length_range(source_lang, target_lang)
    ratio = length_ratio_value(source_text, translated_text)

    glossary_entries = _glossary_entries(source_text, glossary)
    has_glossary = glossary_entries != "NONE"

    scores = {
        "accuracy": None,
        "fluency": None,
        "terminology": rule_terminology_score(
            source_text, translated_text, glossary
        ),
        "format_preservation": rule_format_score(
            source_text, translated_text, file_format
        ),
        "boundary_integrity": rule_boundary_score(source_text),
        "length_ratio": rule_length_score(ratio, lo, hi),
    }

    mode = resolve_mode(mode, llm_client)
    model_reasons = []
    model_notes = ""
    llm_failed = False

    if mode in ("full", "light") and llm_client is not None:
        stopped = stop_event is not None and stop_event.is_set()
        if not stopped:
            try:
                prompt = build_scorer_prompt(
                    chunk_id=chunk_id,
                    source_text=source_text,
                    translated_text=translated_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    file_format=file_format,
                    glossary=glossary,
                    mode=mode,
                )
                response = llm_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": SCORER_SYSTEM_MESSAGE,
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    temperature=0.0,
                    max_tokens=512,
                )
                content = response.choices[0].message.content
                parsed = parse_scorer_response(
                    content, chunk_id=chunk_id, mode=mode
                )
                if mode == "light":
                    scores["accuracy"] = parsed.scores.get("accuracy")
                    scores["fluency"] = parsed.scores.get("fluency")
                else:
                    for dim, value in parsed.scores.items():
                        scores[dim] = value
                    if not has_glossary:
                        scores["terminology"] = None
                    elif (
                        parsed.scores.get("terminology") is None
                        and "terminology" not in parsed.scores
                    ):
                        scores["terminology"] = rule_terminology_score(
                            source_text, translated_text, glossary
                        )
                model_reasons = list(parsed.flag_reasons)
                model_notes = parsed.notes
            except Exception:
                llm_failed = True

    # {BOUNDARY_WARNING} automatically deducts 3 points (spec).
    if boundary_warning:
        scores["boundary_integrity"] = max(
            0.0, float(scores.get("boundary_integrity") or 0.0) - 3.0
        )

    composite = composite_score(scores)
    reasons = []
    if composite < COMPOSITE_THRESHOLD:
        reasons.append(FLAG_COMPOSITE)
    if (
        scores.get("accuracy") is not None
        and scores["accuracy"] < ACCURACY_THRESHOLD
    ):
        reasons.append(FLAG_ACCURACY)
    if boundary_warning:
        reasons.append(FLAG_BOUNDARY)
    if has_note:
        reasons.append(FLAG_NOTE)
    if (
        scores.get("format_preservation") is not None
        and scores["format_preservation"] < FORMAT_THRESHOLD
    ):
        reasons.append(FLAG_FORMAT)
    if length_out_of_range(ratio, lo, hi):
        reasons.append(FLAG_LENGTH)
    if llm_failed:
        reasons.append(FLAG_SCORER_ERROR)
    for reason in model_reasons:
        if reason not in reasons:
            reasons.append(reason)

    return ChunkScore(
        chunk_id=str(chunk_id),
        scores=scores,
        composite=composite,
        flagged=bool(reasons),
        flag_reasons=reasons,
        notes=model_notes,
        mode=mode,
    )


# ── parallel scoring + segment attachment ──────────────────────

def score_and_attach(segments, scorer):
    """
    Score every segment in parallel and attach quality records.

    scorer: configuration dict built by make_scorer().
    Returns the list of ChunkScore records.
    """

    if not scorer or not segments:
        return []
    translations = scorer.get("translations") or {}
    chunks = scorer.get("chunks") or {}
    targets = [
        segment
        for segment in segments
        if str(segment["id"]) in translations
    ]
    if not targets:
        return []
    mode = resolve_mode(scorer.get("mode"), scorer.get("client"))
    workers = max(1, int(scorer.get("max_workers") or _default_workers()))
    print(
        f"Quality scoring {len(targets)} chunks "
        f"(mode={mode}) [quality_scorer]"
    )

    def run(segment):
        chunk_id = str(segment["id"])
        return score_chunk(
            chunk_id=chunk_id,
            source_text=chunks.get(chunk_id, segment.get("source", "")),
            translated_text=translations.get(chunk_id, ""),
            source_lang=scorer.get("source_lang", ""),
            target_lang=scorer.get("target_lang", ""),
            file_format=scorer.get("filetype", "epub"),
            glossary=scorer.get("glossary"),
            llm_client=scorer.get("client"),
            model=scorer.get("model"),
            mode=mode,
            stop_event=scorer.get("stop_event"),
        )

    if workers == 1 or len(targets) == 1:
        results = [run(segment) for segment in targets]
    else:
        with ThreadPoolExecutor(
            max_workers=min(workers, len(targets))
        ) as pool:
            results = list(pool.map(run, targets))

    for segment, score in zip(targets, results):
        segment["quality"] = score.as_storage()
        if score.flagged:
            segment["flagged"] = True
    return results


# ── pipeline helper ────────────────────────────────────────────

def make_scorer(
    requested=None,
    *,
    client=None,
    model=None,
    source_lang="",
    target_lang="",
    filetype="epub",
    all_chunks=None,
    translations=None,
    paths=None,
    stop_event=None,
    mode=None,
    max_workers=None,
    glossary=None,
):
    """
    Build the scorer config passed to generate_outputs.
    Returns None when quality_report is not requested.

    ``glossary`` may be supplied directly (a snapshot dict) to skip
    loading from ``paths``; useful in tests.
    """

    if not wants_quality(requested):
        return None
    glossary_snapshot = {}
    if glossary is not None:
        glossary_snapshot = glossary
    elif paths:
        try:
            from app.glossary.service import load_snapshot
            glossary_snapshot = load_snapshot(paths) or {}
        except Exception:
            glossary_snapshot = {}
    return {
        "client": client,
        "model": model,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "filetype": str(filetype or "epub").lower().lstrip("."),
        "chunks": {
            str(chunk_id): text
            for chunk_id, text in (all_chunks or [])
        },
        "translations": dict(translations or {}),
        "glossary": glossary_snapshot,
        "mode": mode,
        "stop_event": stop_event,
        "max_workers": max_workers,
    }


def wants_quality(requested) -> bool:
    """True when the quality_report output format is requested."""
    try:
        from app.output.formats import normalize_outputs
        return "quality_report" in normalize_outputs(requested)
    except Exception:
        return False


# ── QA report builder ──────────────────────────────────────────

def build_qa_report(scores) -> dict:
    """
    Summary of scoring for the manifest and the QA report.

    ``scores`` is a list of ChunkScore records.
    """

    scores = list(scores or [])
    flagged = [score for score in scores if score.flagged]
    return {
        "total_chunks": len(scores),
        "flagged_count": len(flagged),
        "average_composite": (
            round(
                sum(score.composite for score in scores) / len(scores),
                2,
            )
            if scores
            else 0.0
        ),
        "flagged_chunks": [
            {
                "chunk_id": score.chunk_id,
                "composite": score.composite,
                "reasons": list(score.flag_reasons),
                "notes": score.notes,
            }
            for score in flagged
        ],
    }


def summary_from_segments(segments) -> dict | None:
    """
    Reconstruct a build_qa_report-style summary from segments that
    carry a ``quality`` key. Returns None when no segment was scored.
    """

    scores = []
    for segment in segments or []:
        quality = segment.get("quality")
        if not quality:
            continue
        scores.append(
            ChunkScore(
                chunk_id=str(segment["id"]),
                scores=dict(quality.get("scores") or {}),
                composite=float(quality.get("composite") or 0.0),
                flagged=bool(quality.get("flag_reasons")),
                flag_reasons=list(quality.get("flag_reasons") or []),
                notes=str(quality.get("notes") or ""),
            )
        )
    if not scores:
        return None
    return build_qa_report(scores)


# ── quality report file writer ─────────────────────────────────

def write_quality_report(
    segments, path, title="", filetype="", to_lang="",
):
    """
    Write the per-job quality report JSON document.

    Storage structure per segment:
    {"id","source","target","format","chapter","flagged","quality"}.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    scored = [
        segment
        for segment in segments or []
        if segment.get("quality")
    ]
    document = {
        "book": title,
        "format": filetype,
        "to_language": to_lang,
        "summary": summary_from_segments(segments),
        "segments": [
            {
                "id": segment["id"],
                "source": segment["source"],
                "target": segment["target"],
                "format": segment["format"],
                "chapter": segment["chapter"],
                "flagged": bool(segment["flagged"]),
                "quality": segment["quality"],
            }
            for segment in scored
        ],
    }
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path

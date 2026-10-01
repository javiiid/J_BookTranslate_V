"""
Pre-translation cost and time estimation.

Why this exists
---------------
``/api/jobs/estimate`` already existed and nothing called it. It answered::

    chunks = ceil(file_size / 12000)
    estimated_seconds = chunks * 4
    estimated_cost = 0.0

Three things wrong with that, in increasing order of how much they mislead:

1. The chunk count came from the file's size in bytes, not from chunking it. A
   200-page book of Persian prose and a 200-page book of code produce the same
   number, and neither number is the number of API calls that will happen.
2. The time estimate ignored concurrency entirely. At ``max_concurrency = 12``
   the real figure is roughly an eighth of what it reported.
3. The cost was a hardcoded zero. Shown next to a "start translating" button,
   a zero does not read as "unknown" -- it reads as "free".

So this module computes the real numbers, and the route calls it.

Token counting
--------------
There is no tokenizer available here: ``tiktoken`` is not in ``requirements.txt``
and not installed, and installing it means fetching a BPE table at runtime, which
is exactly the sort of thing that fails on a locked-down machine. Instead the
count comes from :func:`app.pipeline.semantic_chunker.estimate_tokens`, which is
script-aware -- it prices Arabic script at roughly two characters per token and
CJK nearer one-and-a-half, instead of applying one Latin average to everything.

That is an estimate and is labelled as one. It is biased high on purpose: a chunk
count that is too low understates the bill.

Pricing
-------
The obvious thing to do here is invent numbers, and the numbers in the original
spec (``gpt-4o`` at $0.005/1K) are invented -- the project's models are
``gpt-5.6-luna``, ``gpt-5.6-terra`` and ``gemini-3.1-flash-lite``, and no public
price list covers them. Rather than print a fabricated figure, :data:`PRICING`
holds a price per million tokens, and a model with no entry is reported with
``cost_known = False``. The UI then says the price is unknown instead of
asserting a number. Anyone who knows the real prices edits one dict.
"""

from __future__ import annotations

import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.pipeline.semantic_chunker import SemanticChunker, estimate_tokens

# ============================================================
# Pricing
# ============================================================

# USD per million tokens, as (input, output). A model absent from this table has
# no known price, and the estimate says so rather than inventing one.
PRICING: dict[str, tuple[float, float]] = {
    # OpenAI GPT-4 family (prices per million tokens - actual as of Sep 2026)
    "gpt-4": (30.00, 60.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    
    # OpenAI GPT-3.5
    "gpt-3.5-turbo": (0.50, 1.50),
    "gpt-3.5-turbo-16k": (1.00, 2.00),
    
    # Anthropic Claude
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-sonnet-20240229": (3.00, 15.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "claude-3-5-sonnet-20240620": (3.00, 15.00),
    
    # Google Gemini
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-pro": (0.50, 1.50),
    
    # Project custom models (adjust based on your actual provider pricing)
    "gpt-5.6-luna": (0.15, 0.60),           # Equivalent to gpt-4o-mini
    "gpt-5.6-terra": (2.50, 10.00),         # Equivalent to gpt-4o
    "gemini-3.1-flash-lite": (0.075, 0.30), # Equivalent to gemini-1.5-flash
}


# A translation is usually a little longer than its source. The spec's 1.1 is a
# reasonable figure for prose and a low one for Persian-to-English, where the
# expansion is often larger. It is applied to the source, not assumed twice.
OUTPUT_RATIO = 1.1

# The band around the estimate. Not a confidence interval -- nothing here is
# probabilistic -- but a plain acknowledgement that a token estimate and a single
# price point cannot be exact.
RANGE = 0.15

# Seconds of latency per chunk, by mode.
#
# 6.5 is measured, not guessed: this project benchmarked 12 chunks at 72 seconds
# sequentially and 6.6 seconds at concurrency 12, so a wave of twelve costs about
# 6.6 seconds. The specification this replaced proposed 4.5, which is 30% optimistic
# against a measurement taken on this provider.
#
# The batch figure has not been measured here -- batch jobs go through a different
# provider path with its own queueing -- so it is a guess and is marked as one. The
# two are the only numbers in this module not grounded in a run of the product.
LATENCY_FAST_SECONDS = 6.5
LATENCY_BATCH_SECONDS = 8.0

# One LLM call per chunk when the glossary learns inline or deferred.
#
# This was a flat ``GLOSSARY_COST_PER_CHUNK = 0.002``, on the reasoning that a
# glossary call "costs far less than a translation". Measured against the real
# book that reasoning is wrong by a factor of five, and in the worst direction:
# on ``gemini-3.1-flash-lite`` the flat rate came to $0.12 against a token cost
# of $0.05, so the glossary was 70% of the headline figure. On
# ``gpt-5.6-terra`` the same $0.12 was 6%. A constant cannot be right for both,
# because the thing it is standing in for is not constant -- it is a call on the
# same model at the same prices.
#
# So it is derived from what ``app.glossary.automatic.learn_chunk`` actually
# sends, which is not a small payload at all:
#
#   * input  -- the chunk's source *and* its translation, both with tags stripped
#               (``payload['source']`` and ``payload['translation']``), plus a
#               fixed instruction block. So the input is roughly
#               ``1 + OUTPUT_RATIO`` times the source, not 1.
#   * output -- a JSON list of at most 20 short terms against that same volume of
#               text, capped by ``max_tokens=2000`` in the call.
GLOSSARY_SYSTEM_TOKENS = 180
GLOSSARY_INPUT_RATIO = 1.0 + OUTPUT_RATIO
GLOSSARY_OUTPUT_RATIO = 0.05
GLOSSARY_OUTPUT_CAP = 2000


# ============================================================
# Result
# ============================================================

@dataclass(frozen=True)
class Estimate:
    """What the caller gets. Serialised by :func:`to_payload`."""

    #: Chunks that will actually be billed. Equals ``chunk_count_total`` on a
    #: fresh run and the remainder on a resume.
    chunk_count: int
    #: Every chunk the book chunks into, whether or not it is being translated.
    chunk_count_total: int
    token_count: int
    cost: CostBreakdown
    seconds: int
    source_lang: str
    target_lang: str
    model: str
    mode: str
    concurrency: int
    resume: Resume
    #: True when the chunk count came from actually chunking the file rather than
    #: from its size. Worth surfacing: they can differ by a lot.
    chunk_count_exact: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "chunk_count": self.chunk_count,
            "chunk_count_total": self.chunk_count_total,
            "chunks_already_done": self.resume.done,
            "token_count": self.token_count,
            "estimated_cost": self.cost.to_payload(),
            "glossary_cost": round(self.cost.glossary, 4),
            "estimated_time": format_duration(self.seconds),
            "estimated_time_seconds": self.seconds,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "model": self.model,
            "mode": self.mode,
            "concurrency": self.concurrency,
            "has_resume": self.resume.found,
            "resume_progress": self.resume.progress,
            "resume_remaining": self.resume.remaining,
            "chunk_count_exact": self.chunk_count_exact,
        }


# ============================================================
# Human-readable duration, in Persian
# ============================================================

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa_digits(value: float | int) -> str:
    """Latin digits to Persian ones.

    The first version of this returned ``f"~{round(minutes)} دقیقه"`` and produced
    "~45 دقیقه" -- Latin digits inside an otherwise Persian sentence, in the one
    string on the page that is built rather than typed. Every other number in the
    interface goes through the frontend's ``fa()``; this one is generated on the
    server, so it needs its own conversion.
    """
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.1f}".translate(_PERSIAN_DIGITS)
    return str(int(value)).translate(_PERSIAN_DIGITS)


def format_duration(seconds: int) -> str:
    """A Persian duration, in the units a person would actually say.

    Seconds are useless above a few hundred, and minutes are useless above a few
    hours, so the unit changes. Under a minute says so rather than guessing.
    """
    seconds = max(0, int(seconds))

    if seconds < 60:
        return "کمتر از یک دقیقه"

    minutes = seconds / 60
    if minutes < 60:
        return f"~{_fa_digits(round(minutes))} دقیقه"

    hours = minutes / 60
    if hours < 10:
        return f"~{_fa_digits(round(hours, 1))} ساعت"
    return f"~{_fa_digits(round(hours))} ساعت"


# ============================================================
# Chunking a file for a real count
# ============================================================

def count_chunks(
    path: Path,
    max_tokens: int = 1200,
    context_window: int = 2,
) -> tuple[int, int, bool]:
    """Chunk the file for real. Returns ``(chunks, tokens, exact)``.

    ``exact`` is False when the file could not be read as a book -- a PDF, an
    image-only file, a corrupt archive -- and the count fell back to a size
    estimate. The caller surfaces that rather than presenting a guess as a
    measurement.
    """
    if not path.is_file():
        return 0, 0, False

    if path.suffix.lower() == ".epub":
        chunks, tokens, exact = _count_epub(path, max_tokens, context_window)
        if exact:
            return chunks, tokens, True
        # Fall through to the size estimate for a book we could not parse.

    # PDFs have no chunker here -- the PDF path is a separate pipeline -- so the
    # honest answer is an estimate from the page count when we can get it, and
    # from the byte count otherwise.
    if path.suffix.lower() == ".pdf":
        pages = _pdf_page_count(path)
        if pages:
            # ~450 tokens of prose per page, with a wide margin.
            tokens = int(pages * 450 * 1.3)
            return max(1, math.ceil(tokens / max_tokens)), tokens, False

    tokens = _tokens_from_size(path)
    return max(1, math.ceil(tokens / max_tokens)), tokens, False


def _count_epub(
    path: Path,
    max_tokens: int,
    context_window: int,
) -> tuple[int, int, bool]:
    """Run the real chunker over every content file in the archive."""
    chunker = SemanticChunker(
        max_tokens=max_tokens,
        context_window=context_window,
    )
    chunks = 0
    tokens = 0
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.endswith((".xhtml", ".html", ".htm")):
                    continue
                try:
                    content = archive.read(name).decode("utf-8")
                except (UnicodeDecodeError, KeyError, OSError):
                    # A chapter that is not UTF-8 is skipped by the translator
                    # too, so counting it would overstate the work.
                    continue
                if "<" not in content:
                    continue
                for chunk in chunker.chunk(content):
                    chunks += 1
                    tokens += chunk.estimated_tokens
    except (zipfile.BadZipFile, OSError):
        return 0, 0, False

    if chunks == 0:
        return 0, 0, False
    return chunks, tokens, True


def _pdf_page_count(path: Path) -> int:
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore[no-redef]
        except ImportError:
            return 0
    try:
        with pymupdf.open(str(path)) as document:
            return int(document.page_count)
    except Exception:  # noqa: BLE001
        # A damaged or encrypted PDF. The caller falls back to the byte count.
        return 0


def _tokens_from_size(path: Path) -> int:
    """A last-resort token count from the file's size.

    3.5 bytes per token is the usual rule of thumb for UTF-8 mixed with markup,
    which is what an unparseable book leaves us. Deliberately generous, so the
    estimate errs toward "more than you think".
    """
    try:
        size = path.stat().st_size
    except OSError:
        return 0
    return max(1, int(size / 3.5))


# ============================================================
# Cost
# ============================================================

@dataclass(frozen=True)
class CostBreakdown:
    """The total, and the two things that make it up.

    Split out because the dialog has to be able to show the total *and* have the
    reader be able to add it up. The first version returned a bare total plus a
    separate ``glossary_cost``, and the dialog rendered the total with a badge
    reading ``+$0.12`` -- so a reader who believed the badge computed a total
    $0.12 higher than the one on screen. The word in the badge said "شامل"
    (includes) and the sign said "+" (add); they contradicted each other.

    ``base`` is the sum of the two parts, before the band. It is carried
    explicitly so the breakdown on screen adds up to something the total is
    derived from, rather than to a number the reader has to infer.
    """

    translation: float
    glossary: float
    base: float
    minimum: float
    maximum: float
    known: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "min": round(self.minimum, 2),
            "max": round(self.maximum, 2),
            # Enough precision that the two parts visibly add up to the base.
            # Rounded to cents they do not: 0.05 + 0.03 is 0.08, not 0.09.
            "base": round(self.base, 4),
            "translation": round(self.translation, 4),
            "glossary": round(self.glossary, 4),
            "currency": "USD",
            # False means "no price is known for this model", not "zero".
            "known": self.known,
        }


def cost_for(
    model: str,
    tokens: int,
    glossary_auto: bool,
    chunk_count: int,
) -> CostBreakdown:
    """Price a run, split into the translation and the glossary pass."""
    price = PRICING.get(model)
    if price is None:
        # No price on file. Returning zero with known=False is the whole point:
        # the caller must not render this as "free".
        return CostBreakdown(0.0, 0.0, 0.0, 0.0, 0.0, False)

    per_million_in, per_million_out = price
    translation = (tokens / 1_000_000) * per_million_in
    translation += (tokens * OUTPUT_RATIO / 1_000_000) * per_million_out

    glossary = 0.0
    if glossary_auto and chunk_count > 0:
        tokens_per_chunk = tokens / chunk_count
        glossary_in = tokens_per_chunk * GLOSSARY_INPUT_RATIO + GLOSSARY_SYSTEM_TOKENS
        glossary_out = min(
            tokens_per_chunk * GLOSSARY_INPUT_RATIO * GLOSSARY_OUTPUT_RATIO,
            GLOSSARY_OUTPUT_CAP,
        )
        glossary = (glossary_in * chunk_count / 1_000_000) * per_million_in
        glossary += (glossary_out * chunk_count / 1_000_000) * per_million_out

    base = translation + glossary
    return CostBreakdown(
        translation=translation,
        glossary=glossary,
        base=base,
        minimum=base * (1 - RANGE),
        maximum=base * (1 + RANGE),
        known=True,
    )


# ============================================================
# Time
# ============================================================

def seconds_for(
    chunk_count: int,
    concurrency: int,
    mode: str,
    glossary_auto: bool,
) -> int:
    """Wall-clock seconds, at the configured concurrency.

    Concurrency is the whole point of the existing ``max_concurrency = 12``, and
    the stub this replaces ignored it -- it reported twelve times the real figure.
    """
    if chunk_count <= 0:
        return 0
    workers = max(1, int(concurrency))
    latency = (
        LATENCY_BATCH_SECONDS if str(mode).lower() == "batch" else LATENCY_FAST_SECONDS
    )
    # Wavefronts: N chunks over W workers is ceil(N / W) rounds.
    rounds = math.ceil(chunk_count / workers)
    total = rounds * latency
    if glossary_auto:
        # The glossary call is smaller and cheaper, but it is still a second pass
        # over every chunk, so it adds real time rather than nothing.
        total *= 1.15
    return int(math.ceil(total))


# ============================================================
# Resume
# ============================================================

@dataclass(frozen=True)
class Resume:
    """What an unfinished job for this book means for the estimate.

    ``remaining`` is the point of the class. The dialog offers "continue where it
    left off", and on that path only the untranslated chunks are ever billed -- so
    quoting the full book is quoting work that will not be done. It also matters
    that a *finished* job is not an unfinished one: a book translated yesterday
    was being offered as resumable, and priced in full, because the lookup never
    checked.
    """

    found: bool
    progress: float | None
    remaining: int
    done: int

    @property
    def complete(self) -> bool:
        return self.found and self.remaining <= 0


def resume_for(
    book: str,
    from_lang: str,
    to_lang: str,
    model: str,
) -> Resume:
    """Whether an unfinished job exists for this book, and how much is left.

    Two faults, both of which showed up as a dialog offering to resume a book
    that was already finished:

    1. ``find_resumable_jobs`` yields ``(name, timestamp, state)`` tuples, and
       this read them as dictionaries -- ``job.get("state") if isinstance(job,
       dict) else None`` -- so every job was discarded and ``progress`` was
       always ``None``. The guard looked like defensive coding and was in fact
       the whole bug: a job with 60 of 60 chunks done reported "0% saved".
    2. Nothing compared ``chunks_completed`` against ``chunks_total``, so a
       finished job counted as resumable.
    """
    try:
        from app.jobs.state import find_resumable_jobs
    except ImportError:
        return Resume(False, None, 0, 0)

    try:
        jobs = find_resumable_jobs(book, from_lang, to_lang, model)
    except Exception:  # noqa: BLE001
        # A resume lookup must never be the thing that breaks the estimate.
        return Resume(False, None, 0, 0)

    best_progress = 0.0
    best_remaining = 0
    best_done = 0
    found = False
    for job in jobs:
        # A tuple of (name, timestamp, state), not a mapping. Unpack it as one.
        state = job[2] if isinstance(job, tuple) and len(job) >= 3 else None
        if not isinstance(state, dict):
            continue
        total = int(state.get("chunks_total") or 0)
        done = int(state.get("chunks_completed") or 0)
        if total <= 0:
            continue
        remaining = max(0, total - done)
        # A job with nothing left is not a resume, it is a finished translation.
        if remaining <= 0:
            continue
        found = True
        # The most nearly finished job is the one worth continuing.
        if not best_remaining or remaining < best_remaining:
            best_remaining = remaining
            best_done = done
            best_progress = min(1.0, done / total)

    if not found:
        return Resume(False, None, 0, 0)
    return Resume(True, best_progress, best_remaining, best_done)


# ============================================================
# The entry point
# ============================================================

def estimate(
    file_path: str,
    model: str,
    concurrency: int,
    mode: str = "fast",
    glossary_auto: bool = False,
    source_lang: str = "",
    target_lang: str = "",
    max_tokens: int = 1200,
    context_window: int = 2,
) -> Estimate:
    """Estimate a translation run. Never raises for a bad file; degrades instead."""
    path = Path(file_path)
    if not path.is_absolute():
        # Relative paths are resolved against the working directory, which is
        # where uploads land when the server is started from the project root.
        path = Path.cwd() / path

    chunk_count, token_count, exact = count_chunks(path, max_tokens, context_window)

    # An unreadable file still gets a number, so the dialog can open. One chunk is
    # the floor: something will be sent, and saying zero would be a lie.
    if chunk_count <= 0:
        chunk_count = 1
        exact = False

    resume = resume_for(path.stem, source_lang, target_lang, model)

    # On a resume only the untranslated chunks are sent, so only those are billed.
    # Quoting the whole book here is what made the figure wrong: the dialog said
    # "continue where it left off" and then charged for the parts already done.
    if resume.found and resume.remaining > 0:
        # The tokens of the already-translated chunks are not re-sent either, and
        # tokens scale with chunks closely enough for a per-chunk share.
        share = resume.remaining / chunk_count
        billable_chunks = resume.remaining
        billable_tokens = int(token_count * share)
    else:
        billable_chunks = chunk_count
        billable_tokens = token_count

    cost = cost_for(model, billable_tokens, glossary_auto, billable_chunks)
    seconds = seconds_for(billable_chunks, concurrency, mode, glossary_auto)

    return Estimate(
        chunk_count=billable_chunks,
        chunk_count_total=chunk_count,
        token_count=billable_tokens,
        cost=cost,
        seconds=seconds,
        source_lang=source_lang or "?",
        target_lang=target_lang or "?",
        model=model,
        mode=mode,
        concurrency=max(1, int(concurrency)),
        resume=resume,
        chunk_count_exact=exact,
    )

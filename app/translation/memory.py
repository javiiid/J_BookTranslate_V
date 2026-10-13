# ============================================================
# Translation memory read/write for the engine
# ============================================================
"""
Exact-match translation memory used by ``translate_chunk``.

Before any provider API call the engine looks the whole chunk up in
``translation_memory`` for the same language pair; on a hit the stored
translation is served with zero API cost (repeated sentences, headings,
formulas, boilerplate, or a full re-run of the same book). After every
successful chunk translation the pair is stored back, so each book teaches
the memory for the next one.

Matching is deliberately EXACT on the raw chunk text: the chunker is
deterministic, so the same book always produces byte-identical chunks, and
exactness is what makes a no-review auto-apply safe. Fuzzy matching would
need a product decision (thresholds, review UI) and is out of scope.

This module imports nothing from ``app`` so ``translator.py`` can use it
without import cycles. ``db`` is any object with ``fetch_one``/``execute``
like ``app.storage.database.Database`` (which is thread-safe).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lookup(db: Any, source_text: str, from_lang: str, to_lang: str) -> str | None:
    """Return the stored translation for an exact match, else ``None``.

    A hit refreshes ``last_used_at`` so the memory UI (ORDER BY last_used_at)
    surfaces what the engine actually reuses. Never raises: a memory failure
    must degrade to a normal API call, never break the job.
    """
    try:
        row = db.fetch_one(
            "SELECT translated_text FROM translation_memory"
            " WHERE source_text=? AND source_language=? AND target_language=?",
            (source_text, from_lang, to_lang),
        )
    except Exception:
        return None
    if row is None or not row.get("translated_text"):
        return None
    try:
        db.execute(
            "UPDATE translation_memory SET last_used_at=?"
            " WHERE source_text=? AND source_language=? AND target_language=?",
            (_now(), source_text, from_lang, to_lang),
        )
    except Exception:
        pass
    return row["translated_text"]


def store(
    db: Any,
    source_text: str,
    translated_text: str,
    from_lang: str,
    to_lang: str,
    source: str = "auto",
) -> None:
    """Remember one engine-produced pair. Upsert; never raises.

    Engine rows are marked ``source='auto'`` (confidence 1.0: they came from
    the same pipeline that would translate them again) so they stay
    distinguishable from hand-entered (``manual``) and bulk (``import``)
    rows in the memory UI. Empty inputs are refused: they can never match.
    """
    if not source_text or not translated_text:
        return
    try:
        db.execute(
            "INSERT INTO translation_memory(source_text, translated_text,"
            " source_language, target_language, source, confidence, last_used_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(source_text, source_language, target_language)"
            " DO UPDATE SET translated_text=excluded.translated_text,"
            " confidence=excluded.confidence, last_used_at=excluded.last_used_at",
            (source_text, translated_text, from_lang, to_lang, source, 1.0, _now()),
        )
    except Exception:
        pass

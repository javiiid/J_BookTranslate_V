"""Compatibility helpers for durable structured job events."""

from app.core.structured_logging import get_job_logger


def log_progress(paths, message, *, event="progress", level="INFO", **fields):
    """Persist a JSONL event; callers no longer depend on console output."""
    try:
        return get_job_logger(paths).emit(event, message, level=level, **fields)
    except OSError:
        # Logging must not destroy a translation job; state files remain the
        # source of truth for recovery.
        return None

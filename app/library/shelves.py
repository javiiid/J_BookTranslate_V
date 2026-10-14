"""Reading shelves, custom tags and per-day reading stats.

Translation ``status`` (completed/running/failed/available) describes the
translation job and must never be overloaded with reading state. This module
owns the separate reading layer: which shelf a book sits on, what the user
tagged it with, and how many pages were read each day.

All tables carry ``user_id`` from day one (LAUNCH.md Phase A). The current
build still runs single-user/local, so callers fall back to the first user
(or 1 when no user exists yet) — marked inline as loopback-justified. That
fallback dies at launch; the scoping itself does not change.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

UTC = timezone.utc

SHELVES = ("want", "reading", "finished")
MAX_TAGS_PER_BOOK = 20
MAX_TAG_LENGTH = 40
MAX_PAGES_PER_REPORT = 5000


def _now() -> str:
    return datetime.now(UTC).isoformat()


def resolve_user_id(database, explicit: int | None = None) -> int:
    """Return the user new rows belong to.

    Prefers the authenticated user id; falls back to the first user row, then
    1. The fallback is loopback-justified for the current local build and dies
    at launch (Phase A makes auth mandatory).
    """
    if explicit:
        return int(explicit)
    try:
        row = database.fetch_one("SELECT id FROM users ORDER BY id LIMIT 1")
    except Exception:
        row = None
    if row:
        return int(row["id"])
    return 1


def normalize_tag(tag: object) -> str:
    """Normalize one tag: trim, collapse whitespace, keep ZWNJ.

    ``str.lower()`` only affects cased (Latin) characters — Persian text and
    U+200C (ZWNJ) pass through untouched, matching the glossary term rule that
    ZWNJ must never be stripped (else distinct terms merge).
    """
    text = " ".join(str(tag or "").split())
    return text.lower()


def validate_tags(tags: object) -> list[str]:
    """Coerce and validate a tag list. Raises ``ValueError`` on bad input."""
    if not isinstance(tags, list):
        raise ValueError("tags must be a list.")
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        tag = normalize_tag(raw)
        if not tag:
            continue
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError("Each tag must be at most 40 characters.")
        if tag not in seen:
            seen.add(tag)
            cleaned.append(tag)
    if len(cleaned) > MAX_TAGS_PER_BOOK:
        raise ValueError("At most 20 tags per book.")
    return cleaned


def get_shelf(database, user_id: int, book_id: int) -> str | None:
    row = database.fetch_one(
        "SELECT shelf FROM book_shelves WHERE user_id=? AND book_id=?",
        (user_id, book_id),
    )
    return row["shelf"] if row else None


def set_shelf(database, user_id: int, book_id: int, shelf: str | None) -> str | None:
    """Set or clear a book's shelf. ``None`` clears. Returns the new shelf."""
    if shelf is not None:
        shelf = str(shelf).strip().lower()
        if shelf not in SHELVES:
            raise ValueError("Unknown shelf. Use want, reading or finished.")
        if not database.fetch_one("SELECT id FROM library_books WHERE id=?", (book_id,)):
            raise LookupError("Book not found.")
        database.execute(
            "INSERT INTO book_shelves(user_id, book_id, shelf, updated_at)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(user_id, book_id) DO UPDATE SET shelf=excluded.shelf,"
            " updated_at=excluded.updated_at",
            (user_id, book_id, shelf, _now()),
        )
        database.execute(
            "UPDATE library_books SET updated_at=? WHERE id=?", (_now(), book_id)
        )
        return shelf
    database.execute(
        "DELETE FROM book_shelves WHERE user_id=? AND book_id=?", (user_id, book_id)
    )
    return None


def get_tags(database, user_id: int, book_id: int) -> list[str]:
    rows = database.fetch_all(
        "SELECT tag FROM book_tags WHERE user_id=? AND book_id=? ORDER BY tag",
        (user_id, book_id),
    )
    return [row["tag"] for row in rows]


def set_tags(database, user_id: int, book_id: int, tags: object) -> list[str]:
    cleaned = validate_tags(tags)
    if not database.fetch_one("SELECT id FROM library_books WHERE id=?", (book_id,)):
        raise LookupError("Book not found.")
    database.execute(
        "DELETE FROM book_tags WHERE user_id=? AND book_id=?", (user_id, book_id)
    )
    timestamp = _now()
    for tag in cleaned:
        database.execute(
            "INSERT OR IGNORE INTO book_tags(user_id, book_id, tag, created_at)"
            " VALUES (?, ?, ?, ?)",
            (user_id, book_id, tag, timestamp),
        )
    database.execute("UPDATE library_books SET updated_at=? WHERE id=?", (timestamp, book_id))
    return cleaned


def record_progress(
    database,
    user_id: int,
    book_id: int,
    pages: object,
    location: object = None,
) -> dict:
    """Add ``pages`` to today's reading total for one book."""
    try:
        count = int(pages)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError("pages must be a number.")
    if not 1 <= count <= MAX_PAGES_PER_REPORT:
        raise ValueError("pages must be between 1 and 5000.")
    if not database.fetch_one("SELECT id FROM library_books WHERE id=?", (book_id,)):
        raise LookupError("Book not found.")
    day = datetime.now(UTC).date().isoformat()
    timestamp = _now()
    database.execute(
        "INSERT INTO reading_events(user_id, book_id, day, pages, updated_at)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(user_id, book_id, day) DO UPDATE SET"
        " pages=pages+excluded.pages, updated_at=excluded.updated_at",
        (user_id, book_id, day, count, timestamp),
    )
    if location is not None:
        database.execute(
            "UPDATE files SET last_opened_at=?, last_read_location=? WHERE book_id=?",
            (timestamp, str(location)[:500], book_id),
        )
    else:
        database.execute(
            "UPDATE files SET last_opened_at=? WHERE book_id=?", (timestamp, book_id)
        )
    row = database.fetch_one(
        "SELECT pages FROM reading_events WHERE user_id=? AND book_id=? AND day=?",
        (user_id, book_id, day),
    )
    return {"day": day, "pages_today": int((row or {}).get("pages", count))}


def reading_stats(database, user_id: int, days: object = 30) -> dict:
    """Per-day page totals for the user, newest last, plus streak/averages."""
    try:
        window = int(days)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        window = 30
    window = max(1, min(365, window))
    rows = database.fetch_all(
        "SELECT day, SUM(pages) AS pages FROM reading_events"
        " WHERE user_id=? GROUP BY day ORDER BY day DESC LIMIT ?",
        (user_id, window),
    )
    by_day = {row["day"]: int(row["pages"] or 0) for row in rows}
    per_day = [
        {"day": day, "pages": by_day[day]} for day in sorted(by_day)
    ]
    total = sum(by_day.values())
    avg = round(total / window, 1) if window else 0.0
    # Streak: consecutive days ending today (or yesterday, so a reader who has
    # not opened today's book yet does not lose the count at midnight).
    streak = 0
    today = datetime.now(UTC).date()
    if today.isoformat() not in by_day and (today.fromordinal(today.toordinal() - 1)).isoformat() in by_day:
        cursor = today.fromordinal(today.toordinal() - 1)
    else:
        cursor = today
    while cursor.isoformat() in by_day:
        streak += 1
        cursor = cursor.fromordinal(cursor.toordinal() - 1)
    return {
        "per_day": per_day,
        "total_pages": total,
        "avg_per_day": avg,
        "streak_days": streak,
        "days": window,
    }


def attach_to_book(database, user_id: int, book: dict[str, Any]) -> dict[str, Any]:
    """Return ``book`` with the user's ``shelf`` and ``tags`` added."""
    book_id = int(book["id"])
    return {
        **book,
        "shelf": get_shelf(database, user_id, book_id),
        "tags": get_tags(database, user_id, book_id),
    }

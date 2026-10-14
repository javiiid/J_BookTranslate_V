"""Shelves, tags and reading stats: user-scoped from day one."""
from app.library import shelves as book_shelves
from app.storage.database import Database
from app.web import library_summary


def _book(database):
    return database.execute(
        "INSERT INTO library_books(title, created_at, updated_at) VALUES (?, ?, ?)",
        ("Demo", "now", "now"),
    )


def test_shelf_crud_and_unknown_rejected(tmp_path):
    database = Database(tmp_path / "shelf.db")
    book_id = _book(database)
    assert book_shelves.get_shelf(database, 1, book_id) is None
    assert book_shelves.set_shelf(database, 1, book_id, "reading") == "reading"
    assert book_shelves.get_shelf(database, 1, book_id) == "reading"
    assert book_shelves.set_shelf(database, 1, book_id, "finished") == "finished"
    assert book_shelves.set_shelf(database, 1, book_id, None) is None
    try:
        book_shelves.set_shelf(database, 1, book_id, "nope")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown shelf must raise ValueError")
    try:
        book_shelves.set_shelf(database, 1, 999999, "reading")
    except LookupError:
        pass
    else:
        raise AssertionError("foreign book must raise LookupError")


def test_shelves_are_user_scoped(tmp_path):
    database = Database(tmp_path / "scope.db")
    book_id = _book(database)
    book_shelves.set_shelf(database, 1, book_id, "reading")
    book_shelves.set_shelf(database, 2, book_id, "finished")
    assert book_shelves.get_shelf(database, 1, book_id) == "reading"
    assert book_shelves.get_shelf(database, 2, book_id) == "finished"


def test_tags_normalise_keep_zwnj_and_enforce_limits(tmp_path):
    database = Database(tmp_path / "tags.db")
    book_id = _book(database)
    tags = book_shelves.set_tags(database, 1, book_id, ["  رمان  ", "رمان", "Sci-Fi ", ""])
    assert "رمان" in tags and "sci-fi" in tags and len(tags) == 2
    zwnj = "می\u200cخوانم"
    assert book_shelves.set_tags(database, 1, book_id, [zwnj]) == [zwnj]
    assert "\u200c" in book_shelves.get_tags(database, 1, book_id)[0]
    try:
        book_shelves.set_tags(database, 1, book_id, ["x" * 41])
    except ValueError:
        pass
    else:
        raise AssertionError("overlong tag must raise")
    try:
        book_shelves.set_tags(database, 1, book_id, [f"t{i}" for i in range(21)])
    except ValueError:
        pass
    else:
        raise AssertionError(">20 tags must raise")
    try:
        book_shelves.set_tags(database, 1, book_id, "not-a-list")  # type: ignore[arg-type]
    except ValueError:
        pass
    else:
        raise AssertionError("non-list tags must raise")


def test_tags_are_user_scoped(tmp_path):
    database = Database(tmp_path / "tagscope.db")
    book_id = _book(database)
    book_shelves.set_tags(database, 1, book_id, ["رمان"])
    book_shelves.set_tags(database, 2, book_id, ["تاریخ"])
    assert book_shelves.get_tags(database, 1, book_id) == ["رمان"]
    assert book_shelves.get_tags(database, 2, book_id) == ["تاریخ"]


def test_progress_validation_and_daily_rollup(tmp_path):
    database = Database(tmp_path / "progress.db")
    book_id = _book(database)
    for bad in (0, -3, 5001, "abc", None):
        try:
            book_shelves.record_progress(database, 1, book_id, bad)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError(f"pages={bad!r} must raise")
    first = book_shelves.record_progress(database, 1, book_id, 10)
    second = book_shelves.record_progress(database, 1, book_id, 5)
    assert first["day"] == second["day"]
    assert second["pages_today"] == 15
    stats = book_shelves.reading_stats(database, 1, 30)
    assert stats["total_pages"] == 15
    assert stats["streak_days"] == 1
    assert stats["per_day"][-1]["pages"] == 15


def test_empty_stats_never_nan(tmp_path):
    database = Database(tmp_path / "emptystats.db")
    stats = book_shelves.reading_stats(database, 1, 30)
    assert stats == {"per_day": [], "total_pages": 0, "avg_per_day": 0.0, "streak_days": 0, "days": 30}


def test_library_summary_carries_shelf_tags_and_filters(tmp_path, monkeypatch):
    import app.web as web_module

    database = Database(tmp_path / "summary.db")
    monkeypatch.setattr(web_module, "db", database)
    monkeypatch.setattr("app.library.shelves.resolve_user_id", lambda *a, **k: 1)
    book_id = _book(database)
    database.execute(
        "INSERT INTO files(book_id, path, kind, display_name, extension, size_bytes, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (book_id, "demo.epub", "original", "demo.epub", "epub", 10, "now"),
    )
    book_shelves.set_shelf(database, 1, book_id, "reading")
    book_shelves.set_tags(database, 1, book_id, ["رمان"])
    summary = web_module.library_summary("", 1)
    assert summary["total"] == 1
    item = summary["items"][0]
    # Reading shelf must not touch the translation status.
    assert item["status"] == "completed"
    assert item["shelf"] == "reading"
    assert item["tags"] == ["رمان"]
    assert web_module.library_summary("shelf=reading", 1)["total"] == 1
    assert web_module.library_summary("shelf=finished", 1)["total"] == 0
    assert web_module.library_summary("tag=رمان", 1)["total"] == 1
    assert web_module.library_summary("tag=تاریخ", 1)["total"] == 0
    # Other user sees the same book unshelved/untagged.
    other = web_module.library_summary("", 2)
    assert other["items"][0]["shelf"] is None
    assert other["items"][0]["tags"] == []

# ============================================================
# job_events index tests
# ============================================================
#
# job_events is append-only and outgrows every other table on large books.
# The monitor reads one job's events in time order, so the composite index
# on (job_id, timestamp) must exist on fresh databases and be backfilled
# onto pre-index installs by initialize().
#
# ============================================================

import sqlite3

from app.storage.database import DB_NAME, Database


def _indexes(database, table):
    with database.connect() as connection:
        return {
            row[1]
            for row in connection.execute(
                "SELECT * FROM sqlite_master WHERE type='index' AND tbl_name=?",
                (table,),
            )
        }


def test_fresh_database_has_job_events_index(tmp_path):
    database = Database(tmp_path / DB_NAME)
    assert "idx_job_events_job_time" in _indexes(database, "job_events")


def test_initialize_backfills_index_on_old_database(tmp_path):
    path = tmp_path / DB_NAME
    Database(path)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP INDEX idx_job_events_job_time")
        connection.commit()
        before = {
            row[1]
            for row in connection.execute(
                "SELECT * FROM sqlite_master WHERE type='index' AND tbl_name='job_events'"
            )
        }
    assert "idx_job_events_job_time" not in before
    # A plain re-init (what every app start does) must restore it.
    Database(path).initialize()
    with sqlite3.connect(path) as connection:
        after = {
            row[1]
            for row in connection.execute(
                "SELECT * FROM sqlite_master WHERE type='index' AND tbl_name='job_events'"
            )
        }
    assert "idx_job_events_job_time" in after


def test_monitor_query_uses_index(tmp_path):
    database = Database(tmp_path / DB_NAME)
    database.execute(
        "INSERT INTO jobs(id, filename, input_path, filetype, source_language,"
        " target_language, model, mode, status, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("job-1", "book.epub", "book.epub", "epub", "EN", "FA",
         "m", "fast", "running", "2026-01-01", "2026-01-01"),
    )
    database.execute(
        "INSERT INTO job_events(job_id, timestamp, level, event, message) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "2026-01-01", "INFO", "started", "hi"),
    )
    with database.connect() as connection:
        plan = "\n".join(
            row[3]
            for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM job_events WHERE job_id=? ORDER BY timestamp",
                ("job-1",),
            )
        )
    assert "idx_job_events_job_time" in plan, plan

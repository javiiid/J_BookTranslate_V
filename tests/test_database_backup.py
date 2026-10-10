# ============================================================
# Database Rename + Backup Tests
# ============================================================
#
# - kalima.db is canonical; a legacy jbooktranslate.db is adopted by COPY.
# - Backups precede migrations, prune to 5, and list newest-first.
# - Tests use tmp dirs only — never the real data/ directory.
#
# ============================================================

import hashlib
import json
import os
import sqlite3
import time

from app.storage.database import (
    BACKUP_KEEP,
    DB_NAME,
    SCHEMA_VERSION,
    Database,
)


def seed_legacy(path, with_version=True):
    """Build a pre-rename database by hand: settings without version key."""
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE jobs (id TEXT PRIMARY KEY, filename TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO jobs(id, filename) VALUES ('job-1', 'book.epub')"
    )
    connection.execute(
        "INSERT INTO settings(key, value_json, updated_at) VALUES ('other', '1', '2026-01-01')"
    )
    if with_version:
        connection.execute(
            "INSERT INTO settings(key, value_json, updated_at) VALUES ('schema_version', ?, '2026-01-01')",
            (json.dumps(0),),
        )
    connection.commit()
    connection.close()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fresh_dir_creates_canonical_name_without_backup(tmp_path):
    database = Database(tmp_path / DB_NAME)
    assert (tmp_path / DB_NAME).is_file()
    assert not (tmp_path / "jbooktranslate.db").exists()
    assert database.list_backups() == []
    row = database.fetch_one("SELECT value_json FROM settings WHERE key='schema_version'")
    assert json.loads(row["value_json"]) == SCHEMA_VERSION


def test_legacy_file_adopted_by_copy_with_rows_intact(tmp_path):
    legacy = tmp_path / "jbooktranslate.db"
    seed_legacy(legacy)
    before = file_hash(legacy)
    database = Database(tmp_path / DB_NAME)
    assert (tmp_path / DB_NAME).is_file()
    # The original is preserved byte-identical — never moved, never altered.
    assert file_hash(legacy) == before
    assert database.fetch_one("SELECT filename FROM jobs WHERE id='job-1'")["filename"] == "book.epub"
    # Legacy had no version: a migrate backup was taken first.
    assert len(database.list_backups()) == 1


def test_version_bump_backs_up_before_migrating(tmp_path):
    database = Database(tmp_path / DB_NAME)
    database.execute(
        "INSERT INTO settings(key, value_json, updated_at) VALUES ('marker', '\"late\"', '2026-01-01')"
    )
    assert database.list_backups() == []
    # Simulate an older install: drop the version key, add a row, re-init.
    database.execute("DELETE FROM settings WHERE key='schema_version'")
    database.execute(
        "INSERT INTO settings(key, value_json, updated_at) VALUES ('early', '\"x\"', '2026-01-01')"
    )
    database.initialize()
    backups = database.list_backups()
    assert len(backups) == 1
    # Point-in-time proof: the backup predates the re-init writes
    # (no schema_version stored yet), while the live DB has moved on.
    backup = sqlite3.connect(backups[0])
    try:
        live_keys = {row[0] for row in database.connect().execute("SELECT key FROM settings")}
        backup_keys = {row[0] for row in backup.execute("SELECT key FROM settings")}
        assert "schema_version" in live_keys and "schema_version" not in backup_keys
        assert "early" in live_keys and "early" in backup_keys
    finally:
        backup.close()


def test_retention_prunes_to_newest_five(tmp_path):
    database = Database(tmp_path / DB_NAME)
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()
    old = time.time() - 2 * 86400
    for day in range(1, 8):
        planted = backups_dir / f"kalima-202001{day:02d}-000000.db"
        planted.write_bytes(b"x")
        os.utime(planted, (old, old))
    database.initialize()
    kept = [entry.name for entry in database.list_backups()]
    assert len(kept) == BACKUP_KEEP
    assert "kalima-20200101-000000.db" not in kept
    assert "kalima-20200102-000000.db" not in kept
    assert "kalima-20200103-000000.db" not in kept


def test_scheduled_backup_when_newest_is_stale(tmp_path):
    database = Database(tmp_path / DB_NAME)
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()
    stale = backups_dir / "kalima-20200101-000000.db"
    stale.write_bytes(b"x")
    old = time.time() - 2 * 86400
    os.utime(stale, (old, old))
    database.initialize()
    assert len(database.list_backups()) == 2


def test_manual_backup_returns_path_and_lists_newest_first(tmp_path):
    database = Database(tmp_path / DB_NAME)
    first = database.backup_database("manual")
    assert first.is_file()
    listed = database.list_backups()
    assert listed[0] == first
    # Restorable: the backup opens as a real database with our tables.
    backup = sqlite3.connect(first)
    try:
        tables = {row[0] for row in backup.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"jobs", "users", "settings"} <= tables
    finally:
        backup.close()

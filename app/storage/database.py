"""SQLite persistence layer for jobs, files, terminology and observability."""
from __future__ import annotations
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.core.paths import ensure_dir

UTC = timezone.utc
# Canonical database file. The product was renamed to KALIMA while the file
# stayed ``jbooktranslate.db``; renaming by move would point the app at an
# empty database and orphan the real one with no error, so the migration below
# copies (never moves) and the old file stays as a pre-rename backup.
LEGACY_DB_NAME = "jbooktranslate.db"
DB_NAME = "kalima.db"
# Test isolation: KALIMA_DB_PATH points the whole app (including the `db`
# singleton below) at another SQLite file. Pytest sets it before any app
# import (see tests/conftest.py), so a running server keeps data/kalima.db
# while tests use a temp file — no shutdown needed.
DB_ENV_VAR = "KALIMA_DB_PATH"


def resolve_db_path() -> Path:
    """Return the live database file, honouring KALIMA_DB_PATH first."""
    override = (os.environ.get(DB_ENV_VAR) or "").strip().strip("\"'")
    if override:
        return Path(override).expanduser()
    return ensure_dir("data") / DB_NAME


DB_PATH = resolve_db_path()
# Bump when the schema or any _migrate_* changes: a bump takes exactly one
# timestamped backup BEFORE migrating. See backup_database().
SCHEMA_VERSION = 3
BACKUP_KEEP = 5
BACKUP_MAX_AGE_SECONDS = 86400

class Database:
    def __init__(self, path: str | Path | None = None):
        # path=None resolves via the env var at call time, not def time: a
        # default arg of DB_PATH would freeze the import-time value and ignore
        # a later KALIMA_DB_PATH set by tests/conftest.py.
        resolved = resolve_db_path() if path is None else Path(path)
        self.path = resolved; self.path.parent.mkdir(parents=True, exist_ok=True); self._lock = threading.RLock(); self._adopt_legacy_file_for(self.path); self.initialize()

    @staticmethod
    def _adopt_legacy_file_for(path: Path) -> Path | None:
        """Copy the pre-rename database into place. Returns the backup path kept.

        Only when the canonical file is missing, its legacy sibling exists,
        and the target is the canonical name: a copy, never a move, so the
        old file survives as the pre-rename backup.
        """
        path = Path(path)
        if path.name != DB_NAME or path.exists():
            return None
        legacy = path.parent / LEGACY_DB_NAME
        if not legacy.is_file():
            return None
        import shutil

        shutil.copy2(legacy, path)
        print(f"Database renamed by copy: {legacy.name} -> {path.name} (original kept as backup)")
        return legacy

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row; connection.execute("PRAGMA journal_mode=WAL"); connection.execute("PRAGMA foreign_keys=ON"); return connection

    def initialize(self):
        schema = """
        CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, filename TEXT NOT NULL, input_path TEXT NOT NULL, filetype TEXT NOT NULL, source_language TEXT NOT NULL, target_language TEXT NOT NULL, model TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL, progress_completed INTEGER NOT NULL DEFAULT 0, progress_total INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, output_path TEXT, error TEXT, estimated_cost REAL NOT NULL DEFAULT 0, input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0, retry_count INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS job_events (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, timestamp TEXT NOT NULL, level TEXT NOT NULL, event TEXT NOT NULL, message TEXT NOT NULL, recoverable INTEGER NOT NULL DEFAULT 1, data_json TEXT, FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS job_chunks (job_id TEXT NOT NULL, chunk_id TEXT NOT NULL, status TEXT NOT NULL, source_text TEXT, translated_text TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(job_id, chunk_id), FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, path TEXT NOT NULL, kind TEXT NOT NULL, size_bytes INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS glossaries (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS glossary_terms (id INTEGER PRIMARY KEY AUTOINCREMENT, glossary_id INTEGER NOT NULL, source_term TEXT NOT NULL, target_term TEXT NOT NULL, notes TEXT DEFAULT '', UNIQUE(glossary_id, source_term), FOREIGN KEY(glossary_id) REFERENCES glossaries(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS translation_memory (id INTEGER PRIMARY KEY AUTOINCREMENT, source_text TEXT NOT NULL, translated_text TEXT NOT NULL, source_language TEXT NOT NULL, target_language TEXT NOT NULL, source TEXT DEFAULT 'manual', confidence REAL DEFAULT 1, last_used_at TEXT NOT NULL, UNIQUE(source_text, source_language, target_language));
        CREATE TABLE IF NOT EXISTS translation_profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, system_prompt TEXT NOT NULL, temperature REAL DEFAULT 0.2, preserve_html INTEGER DEFAULT 1, preserve_quotes INTEGER DEFAULT 1, glossary_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(glossary_id) REFERENCES glossaries(id) ON DELETE SET NULL);
        CREATE TABLE IF NOT EXISTS providers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, base_url TEXT NOT NULL, api_key_ref TEXT DEFAULT '', default_model TEXT DEFAULT '', enabled INTEGER DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL);
        -- The monitor reads one job's events in time order
        -- (WHERE job_id=? ORDER BY timestamp), and job_events is append-only,
        -- so it outgrows every other table on large books. Without this the
        -- read is a full table scan on every monitor refresh.
        -- job_chunks needs no twin: its PRIMARY KEY starts with job_id, so
        -- WHERE job_id=? already uses the PK's leftmost prefix.
        CREATE INDEX IF NOT EXISTS idx_job_events_job_time ON job_events(job_id, timestamp);
        """
        with self._lock, self.connect() as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            stored = None
            if "settings" in tables:
                row = connection.execute("SELECT value_json FROM settings WHERE key='schema_version'").fetchone()
                stored = json.loads(row[0]) if row else 0
            if stored is not None and stored < SCHEMA_VERSION:
                self._backup_locked("migrate")
            connection.executescript(schema); self._seed_defaults(connection)
            self._migrate_library(connection)
            self._migrate_account_portal(connection)
            self._migrate_auth(connection)
            connection.execute("""CREATE TABLE IF NOT EXISTS book_glossaries (
                book_id INTEGER NOT NULL REFERENCES library_books(id) ON DELETE CASCADE,
                source_language TEXT NOT NULL, target_language TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 0, terms_json TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY(book_id, source_language, target_language)
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS book_glossary_proposals (
                book_id INTEGER NOT NULL REFERENCES library_books(id) ON DELETE CASCADE,
                source_language TEXT NOT NULL, target_language TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT 'preflight',
                terms_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                PRIMARY KEY(book_id, source_language, target_language, origin)
            )""")
            connection.execute(
                "INSERT INTO settings(key, value_json, updated_at) VALUES ('schema_version', ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
                (json.dumps(SCHEMA_VERSION), datetime.now(UTC).isoformat()),
            )
        self._scheduled_backup(stored is not None)

    def backup_dir(self) -> Path:
        directory = self.path.parent / "backups"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def list_backups(self) -> list[Path]:
        """Backup files, newest first. Never raises on a missing directory."""
        directory = self.path.parent / "backups"
        if not directory.is_dir():
            return []
        return sorted(
            (entry for entry in directory.iterdir()
             if entry.is_file() and entry.name.startswith("kalima-") and entry.suffix == ".db"),
            reverse=True,
        )

    def _backup_locked(self, reason: str) -> Path:
        """Copy the live database with the SQLite backup API (WAL-safe).

        Call with self._lock held. Raw file copies of a WAL-mode database can
        catch a mid-write state; backup() copies a consistent snapshot.
        """
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        target = self.backup_dir() / f"kalima-{stamp}.db"
        source = sqlite3.connect(self.path, timeout=30)
        try:
            dest = sqlite3.connect(target)
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()
        for stale in self.list_backups()[BACKUP_KEEP:]:
            try:
                stale.unlink()
                print(f"Database backup pruned: {stale.name}")
            except OSError:
                pass
        print(f"Database backup ({reason}): {target.name}")
        return target

    def backup_database(self, reason: str = "manual") -> Path:
        """Take a timestamped backup now. Returns the backup path."""
        with self._lock:
            return self._backup_locked(reason)

    def _scheduled_backup(self, has_history: bool) -> None:
        """Once-a-day safety copy without a scheduler thread.

        Runs at init: backs up when the newest copy is older than 24h, or when
        a versioned database has no backup at all. Brand-new files (no history
        yet) are skipped — there is nothing to protect on first creation.
        """
        if not has_history:
            return
        try:
            with self._lock:
                backups = self.list_backups()
                if backups:
                    age = datetime.now(UTC).timestamp() - backups[0].stat().st_mtime
                    if age < BACKUP_MAX_AGE_SECONDS:
                        return
                self._backup_locked("scheduled")
        except OSError as exc:
            print(f"Scheduled database backup skipped: {exc}")

    @staticmethod
    def _migrate_library(connection):
        """Add the library index without disturbing existing installations."""
        connection.execute("""CREATE TABLE IF NOT EXISTS library_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT DEFAULT '',
            description TEXT DEFAULT '',
            cover_path TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0
        )""")
        existing = {row[1] for row in connection.execute("PRAGMA table_info(files)").fetchall()}
        columns = {
            "book_id": "INTEGER",
            "display_name": "TEXT DEFAULT ''",
            "extension": "TEXT DEFAULT ''",
            "mime_type": "TEXT DEFAULT ''",
            "language": "TEXT DEFAULT ''",
            "checksum": "TEXT DEFAULT ''",
            "is_readable": "INTEGER NOT NULL DEFAULT 0",
            "page_count": "INTEGER NOT NULL DEFAULT 0",
            "chapter_count": "INTEGER NOT NULL DEFAULT 0",
            "last_opened_at": "TEXT",
            "last_read_location": "TEXT",
        }
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE files ADD COLUMN {name} {definition}")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_files_book_id ON files(book_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_library_books_archived ON library_books(archived)")

    @staticmethod
    def _migrate_account_portal(connection):
        """Create local account, billing, marketplace, and order tables."""
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, display_name TEXT NOT NULL, email TEXT DEFAULT '', organization TEXT DEFAULT '', locale TEXT NOT NULL DEFAULT 'fa', plan TEXT NOT NULL DEFAULT 'free', credit_balance INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS credit_packages (id TEXT PRIMARY KEY, name_fa TEXT NOT NULL, name_en TEXT NOT NULL, credits INTEGER NOT NULL, price_usd REAL NOT NULL, bonus_percent INTEGER NOT NULL DEFAULT 0, recommended INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS billing_transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, kind TEXT NOT NULL, reference_id TEXT NOT NULL, amount_usd REAL NOT NULL DEFAULT 0, credits INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS account_api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, name TEXT NOT NULL, token_prefix TEXT NOT NULL, token_hash TEXT NOT NULL, scopes TEXT NOT NULL, created_at TEXT NOT NULL, last_used_at TEXT, revoked_at TEXT);
        CREATE TABLE IF NOT EXISTS marketplace_items (id TEXT PRIMARY KEY, kind TEXT NOT NULL, title_fa TEXT NOT NULL, title_en TEXT NOT NULL, description_fa TEXT NOT NULL, description_en TEXT NOT NULL, owner_name TEXT NOT NULL, language_pair TEXT NOT NULL, price_usd REAL NOT NULL DEFAULT 0, rating REAL NOT NULL DEFAULT 0, installs INTEGER NOT NULL DEFAULT 0, featured INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS account_marketplace (account_id INTEGER NOT NULL, item_id TEXT NOT NULL, installed_at TEXT NOT NULL, PRIMARY KEY(account_id,item_id));
        CREATE TABLE IF NOT EXISTS translation_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, title TEXT NOT NULL, service_type TEXT NOT NULL, source_language TEXT NOT NULL, target_language TEXT NOT NULL, word_count INTEGER NOT NULL DEFAULT 0, budget_usd REAL NOT NULL DEFAULT 0, deadline TEXT, notes TEXT DEFAULT '', status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS business_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, request_type TEXT NOT NULL, company_name TEXT DEFAULT '', contact_name TEXT NOT NULL, email TEXT NOT NULL, details TEXT DEFAULT '', status TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        timestamp = datetime.now(UTC).isoformat()
        connection.execute("INSERT OR IGNORE INTO accounts(id,display_name,locale,plan,created_at,updated_at) VALUES (1,'J Book User','fa','free',?,?)", (timestamp, timestamp))
        packages = [
            ("starter", "شروع", "Starter", 100, 5.0, 0, 0),
            ("creator", "نویسنده", "Creator", 500, 20.0, 10, 1),
            ("publisher", "ناشر", "Publisher", 2000, 65.0, 20, 0),
        ]
        connection.executemany("INSERT OR IGNORE INTO credit_packages(id,name_fa,name_en,credits,price_usd,bonus_percent,recommended) VALUES (?,?,?,?,?,?,?)", packages)
        items = [
            ("literary-fa", "template", "سبک ادبی فارسی", "Persian literary style", "الگوی ترجمه برای رمان و نثر ادبی", "Translation style for fiction and literary prose", "J Book", "EN→FA", 0, 4.8, 1),
            ("medical-en-fa", "glossary", "واژه‌نامه پزشکی", "Medical glossary", "اصطلاحات ثابت پزشکی و دارویی", "Consistent medical and pharmaceutical terms", "J Book", "EN→FA", 9, 4.9, 1),
            ("legal-en-fa", "glossary", "واژه‌نامه حقوقی", "Legal glossary", "اصطلاحات قرارداد و حقوق", "Contract and legal terminology", "J Book", "EN→FA", 7, 4.7, 0),
            ("technical-clear", "template", "سبک فنی روان", "Clear technical style", "ترجمه دقیق و خوانا برای کتاب‌های تخصصی", "Accurate readable style for technical books", "J Book", "EN→FA", 0, 4.6, 0),
        ]
        connection.executemany("INSERT OR IGNORE INTO marketplace_items(id,kind,title_fa,title_en,description_fa,description_en,owner_name,language_pair,price_usd,rating,featured) VALUES (?,?,?,?,?,?,?,?,?,?,?)", items)

    @staticmethod
    def _migrate_auth(connection):
        """Create local password-auth tables without disturbing existing installs."""
        connection.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id)")
        existing_users = {row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        if "email_verified" not in existing_users:
            connection.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
        for column in ("google_sub", "apple_sub"):
            if column not in existing_users:
                connection.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
                existing_users.add(column)
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub) WHERE google_sub IS NOT NULL"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_apple_sub ON users(apple_sub) WHERE apple_sub IS NOT NULL"
        )
        connection.execute("""CREATE TABLE IF NOT EXISTS oauth_states (
            state_hash TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS auth_otps (
            email TEXT PRIMARY KEY,
            code_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            used INTEGER NOT NULL DEFAULT 0,
            sent_count INTEGER NOT NULL DEFAULT 0,
            window_started_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS auth_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_key TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_auth_attempts_scope ON auth_attempts(scope_key, created_at)")
        # Sessions carry their last activity so the device list can show it.
        # Old rows are backfilled from created_at (the login moment), which is
        # the honest value when nothing newer was ever recorded.
        existing_sessions = {row[1] for row in connection.execute("PRAGMA table_info(auth_sessions)").fetchall()}
        if "last_seen_at" not in existing_sessions:
            connection.execute("ALTER TABLE auth_sessions ADD COLUMN last_seen_at TEXT")
        connection.execute("UPDATE auth_sessions SET last_seen_at=created_at WHERE last_seen_at IS NULL")
        # Login/logout audit trail. Bounded per user (see record_auth_event):
        # a brute-force storm must not turn the security log into the bloat.
        connection.execute("""CREATE TABLE IF NOT EXISTS auth_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            event TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ip TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT ''
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_auth_events_user_time ON auth_events(user_id, created_at)")

    @staticmethod
    def _seed_defaults(connection):
        timestamp = datetime.now(UTC).isoformat()
        defaults = [("ادبی", "Translate naturally while preserving the author's literary voice.", .2), ("دانشگاهی", "Translate accurately with consistent academic terminology.", .1), ("فنی", "Translate precisely and preserve technical terms and formatting.", .1), ("روان", "Produce fluent, natural and accessible target-language prose.", .3)]
        connection.executemany("INSERT OR IGNORE INTO translation_profiles(name, system_prompt, temperature, preserve_html, preserve_quotes, created_at, updated_at) VALUES (?, ?, ?, 1, 1, ?, ?)", [(name, prompt, temperature, timestamp, timestamp) for name, prompt, temperature in defaults])

    def execute(self, sql: str, params: tuple = (), *, many: list[tuple] | None = None) -> int:
        with self._lock, self.connect() as connection:
            cursor = connection.cursor(); cursor.executemany(sql, many) if many is not None else cursor.execute(sql, params); return cursor.lastrowid or cursor.rowcount

    def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock, self.connect() as connection:
            row = connection.execute(sql, params).fetchone(); return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock, self.connect() as connection: return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def upsert_job(self, job: dict) -> None:
        self.execute("""INSERT INTO jobs(id, filename, input_path, filetype, source_language, target_language, model, mode, status, progress_completed, progress_total, created_at, updated_at, output_path, error, estimated_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, progress_completed=excluded.progress_completed, progress_total=excluded.progress_total, updated_at=excluded.updated_at, output_path=excluded.output_path, error=excluded.error""", (job["id"], job["filename"], job["input_path"], job["filetype"], job["source_language"], job["target_language"], job["model"], job["mode"], job["status"], job.get("progress", {}).get("completed", 0), job.get("progress", {}).get("total", 0), job["created_at"], job["updated_at"], job.get("output_path"), job.get("error"), job.get("estimated_cost", 0.0)))

    def record_event(self, job_id: str | None, level: str, event: str, message: str, recoverable: bool = True, data: Any = None) -> None:
        self.execute("INSERT INTO job_events(job_id, timestamp, level, event, message, recoverable, data_json) VALUES (?, ?, ?, ?, ?, ?, ?)", (job_id, datetime.now(UTC).isoformat(), level, event, message, int(recoverable), json.dumps(data, ensure_ascii=False) if data is not None else None))

db = Database()

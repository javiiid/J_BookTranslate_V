"""SQLite persistence layer for jobs, files, terminology and observability."""
from __future__ import annotations
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.core.paths import ensure_dir

UTC = timezone.utc
DB_PATH = ensure_dir("data") / "jbooktranslate.db"

class Database:
    def __init__(self, path: str | Path = DB_PATH):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self._lock = threading.RLock(); self.initialize()

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
        """
        with self._lock, self.connect() as connection:
            connection.executescript(schema); self._seed_defaults(connection)
            self._migrate_library(connection)
            self._migrate_account_portal(connection)
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

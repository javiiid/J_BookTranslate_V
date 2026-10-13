"""Pytest isolation: never touch the real data/kalima.db.

The app builds a process-wide ``db = Database()`` singleton at import time
(see app/storage/database.py). Without isolation that singleton opens the
live database, so a running ``python -m app.web`` holds the SQLite/WAL lock
and tests fail spuriously.

Two layers, both cheap:

1. Import-time: KALIMA_DB_PATH is pointed at a session placeholder under
   .test-tmp/ (gitignored, always writable — unlike the system temp dir)
   BEFORE any app module is imported. conftest.py loads before test
   modules, so the singleton initialises against the placeholder.
2. Per-test: an autouse fixture swaps the singleton (and the already-bound
   ``db`` references in app.web / app.account.service) for a fresh
   tmp_path database, and points KALIMA_DB_PATH at it so any ``Database()``
   built mid-test lands in the same sandbox.

The server process never sees this env var, so it keeps the real file.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_DB = REPO_ROOT / ".test-tmp" / "pytest-session" / "kalima.db"

# Layer 1: must run at conftest import, before any `import app....` in tests.
os.environ.setdefault("KALIMA_DB_PATH", str(SESSION_DB))
SESSION_DB.parent.mkdir(parents=True, exist_ok=True)

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every `db` singleton holder at a fresh per-test database."""
    from app.storage.database import DB_ENV_VAR, Database
    import app.storage.database as db_module

    tmp_db = Database(tmp_path / "kalima-test.db")
    monkeypatch.setattr(db_module, "db", tmp_db)
    monkeypatch.setenv(DB_ENV_VAR, str(tmp_db.path))
    # Modules that did `from app.storage.database import db` at their top
    # level hold the old object; rebind them when already imported. Modules
    # imported later (e.g. app.web inside a test) pick up the patched
    # db_module.db naturally — except these two, which bind at import.
    for module_name in ("app.web", "app.account.service"):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "db"):
            monkeypatch.setattr(module, "db", tmp_db)
    return tmp_db

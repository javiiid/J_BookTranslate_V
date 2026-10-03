"""SQLite persistence and atomic reservations shared by all worker threads."""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(ValueError):
    pass


class BudgetExceeded(ValueError):
    pass


class Store:
    def __init__(self, database):
        self.database = database
        with database.connect() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS calibrations (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS calibration_cache (key TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS calibration_operations (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, request_key TEXT NOT NULL, payload_hash TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(session_id,request_key));
                CREATE TABLE IF NOT EXISTS calibration_budgets (id TEXT PRIMARY KEY, sample_spent INTEGER NOT NULL DEFAULT 0, full_spent INTEGER NOT NULL DEFAULT 0, sample_reserved INTEGER NOT NULL DEFAULT 0, full_reserved INTEGER NOT NULL DEFAULT 0, sample_calls INTEGER NOT NULL DEFAULT 0, cost_spent INTEGER NOT NULL DEFAULT 0, cost_reserved INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS calibration_attempts (id TEXT PRIMARY KEY, budget_id TEXT NOT NULL, phase TEXT NOT NULL, reserved INTEGER NOT NULL, cost_reserved INTEGER NOT NULL, status TEXT NOT NULL, usage TEXT, created_at TEXT NOT NULL);
            ''')

    @contextmanager
    def transaction(self):
        connection = self.database.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create(self, data):
        with self.transaction() as c:
            c.execute("INSERT INTO calibrations VALUES (?,?,?)", (data["id"], data["revision"], json.dumps(data, ensure_ascii=False)))
            c.execute("INSERT OR IGNORE INTO calibration_budgets(id) VALUES (?)", (data["budget_id"],))

    def get(self, identifier):
        row = self.database.fetch_one("SELECT data FROM calibrations WHERE id=?", (identifier,))
        if not row:
            raise LookupError("جلسهٔ نمونه پیدا نشد.")
        return json.loads(row["data"])

    def change(self, identifier, action, revision=None):
        with self.transaction() as c:
            row = c.execute("SELECT data FROM calibrations WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise LookupError("جلسهٔ نمونه پیدا نشد.")
            data = json.loads(row["data"])
            if revision is not None and (type(revision) is not int or revision != data["revision"]):
                raise Conflict("تنظیمات در صفحهٔ دیگری تغییر کرده؛ صفحه را تازه کنید.")
            action(data)
            data["updated_at"] = now()
            c.execute("UPDATE calibrations SET revision=?,data=? WHERE id=?", (data["revision"], json.dumps(data, ensure_ascii=False), identifier))
        return data

    def list(self):
        rows = self.database.fetch_all("SELECT data FROM calibrations ORDER BY rowid DESC LIMIT 30")
        return [json.loads(row["data"]) for row in rows]

    def cached(self, key):
        row = self.database.fetch_one("SELECT data FROM calibration_cache WHERE key=?", (key,))
        return json.loads(row["data"]) if row else None

    def cache(self, key, result):
        self.database.execute("INSERT OR REPLACE INTO calibration_cache VALUES (?,?)", (key, json.dumps(result, ensure_ascii=False)))

    def budget(self, identifier):
        return self.database.fetch_one("SELECT * FROM calibration_budgets WHERE id=?", (identifier,))

    def reserve(self, session, tokens, cost, phase):
        identifier = uuid.uuid4().hex
        with self.transaction() as c:
            b = c.execute("SELECT * FROM calibration_budgets WHERE id=?", (session["budget_id"],)).fetchone()
            policy = session["budget"]
            if b["sample_spent"] + b["full_spent"] + b["sample_reserved"] + b["full_reserved"] + tokens > policy["total_tokens"]:
                raise BudgetExceeded("سقف توکن کل کتاب کافی نیست. بودجه را بازبینی کنید.")
            if phase == "sample" and (b["sample_spent"] + b["sample_reserved"] + tokens > policy["sample_tokens"] or b["sample_calls"] >= policy["max_calls"]):
                raise BudgetExceeded("سقف هزینهٔ نمونه یا تعداد درخواست‌ها رسیده است. بودجه را بازبینی کنید.")
            if policy.get("max_cost_micros") is not None:
                if cost is None:
                    raise BudgetExceeded("قیمت تأییدشدهٔ مدل در تنظیمات موجود نیست؛ سقف دلاری قابل اعمال نیست.")
                if b["cost_spent"] + b["cost_reserved"] + cost > policy["max_cost_micros"]:
                    raise BudgetExceeded("سقف دلاری کتاب کافی نیست.")
            c.execute(f"UPDATE calibration_budgets SET {phase}_reserved={phase}_reserved+?, cost_reserved=cost_reserved+?, sample_calls=sample_calls+? WHERE id=?", (tokens, cost or 0, int(phase == "sample"), session["budget_id"]))
            c.execute("INSERT INTO calibration_attempts VALUES (?,?,?,?,?,?,?,?)", (identifier, session["budget_id"], phase, tokens, cost or 0, "dispatching", None, now()))
        return identifier

    def settle(self, identifier, tokens, cost, usage):
        with self.transaction() as c:
            a = c.execute("SELECT * FROM calibration_attempts WHERE id=?", (identifier,)).fetchone()
            if a["status"] == "settled":
                return
            phase = a["phase"]
            c.execute(f"UPDATE calibration_budgets SET {phase}_reserved={phase}_reserved-?, {phase}_spent={phase}_spent+?, cost_reserved=cost_reserved-?, cost_spent=cost_spent+? WHERE id=?", (a["reserved"], tokens, a["cost_reserved"], cost if cost is not None else a["cost_reserved"], a["budget_id"]))
            c.execute("UPDATE calibration_attempts SET status='settled',usage=? WHERE id=?", (json.dumps(usage), identifier))

    def uncertain(self, identifier):
        self.database.execute("UPDATE calibration_attempts SET status='uncertain' WHERE id=? AND status='dispatching'", (identifier,))

    def save_operation(self, operation, request_key, payload_hash):
        with self.transaction() as c:
            row = c.execute("SELECT data,payload_hash FROM calibration_operations WHERE session_id=? AND request_key=?", (operation["session_id"], request_key)).fetchone()
            if row:
                if row["payload_hash"] != payload_hash:
                    raise Conflict("شناسهٔ درخواست تکراری با تنظیمات متفاوت ارسال شده است.")
                return json.loads(row["data"]), False
            c.execute("INSERT INTO calibration_operations VALUES (?,?,?,?,?)", (operation["id"], operation["session_id"], request_key, payload_hash, json.dumps(operation, ensure_ascii=False)))
        return operation, True

    def operation(self, identifier):
        row = self.database.fetch_one("SELECT data FROM calibration_operations WHERE id=?", (identifier,))
        if not row:
            raise LookupError("عملیات پیدا نشد.")
        return json.loads(row["data"])

    def update_operation(self, operation):
        self.database.execute("UPDATE calibration_operations SET data=? WHERE id=?", (json.dumps(operation, ensure_ascii=False), operation["id"]))

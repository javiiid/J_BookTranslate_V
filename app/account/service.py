"""Local persistence services for the product account portal."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from app.storage.database import db

UTC = timezone.utc
PLANS = {
    "free": {"name_fa": "رایگان", "name_en": "Free", "monthly_price": 0, "features": ["translation", "library"]},
    "pro": {"name_fa": "حرفه‌ای", "name_en": "Pro", "monthly_price": 19, "features": ["translation", "library", "glossary", "memory", "marketplace"]},
    "publisher": {"name_fa": "ناشر", "name_en": "Publisher", "monthly_price": 79, "features": ["pro", "team", "publisher_dashboard", "priority"]},
    "enterprise": {"name_fa": "سازمانی", "name_en": "Enterprise", "monthly_price": None, "features": ["publisher", "on_premise", "sso", "audit", "sla"]},
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def account_overview() -> dict:
    account = db.fetch_one("SELECT * FROM accounts WHERE id=1") or {}
    counts = {
        "books": (db.fetch_one("SELECT COUNT(*) AS count FROM library_books WHERE archived=0") or {"count": 0})["count"],
        "jobs": (db.fetch_one("SELECT COUNT(*) AS count FROM jobs") or {"count": 0})["count"],
        "completed_jobs": (db.fetch_one("SELECT COUNT(*) AS count FROM jobs WHERE status='completed'") or {"count": 0})["count"],
        "glossaries": (db.fetch_one("SELECT COUNT(*) AS count FROM glossaries") or {"count": 0})["count"],
        "memory_entries": (db.fetch_one("SELECT COUNT(*) AS count FROM translation_memory") or {"count": 0})["count"],
        "api_keys": (db.fetch_one("SELECT COUNT(*) AS count FROM account_api_keys WHERE revoked_at IS NULL") or {"count": 0})["count"],
        "open_orders": (db.fetch_one("SELECT COUNT(*) AS count FROM translation_orders WHERE status NOT IN ('completed','cancelled')") or {"count": 0})["count"],
    }
    recent_transactions = db.fetch_all("SELECT id,kind,reference_id,amount_usd,credits,status,created_at FROM billing_transactions ORDER BY id DESC LIMIT 8")
    return {"account": account, "plan": PLANS.get(account.get("plan", "free"), PLANS["free"]), "counts": counts, "transactions": recent_transactions}


def update_account(payload: dict) -> dict:
    display_name = str(payload.get("display_name", "")).strip()[:100]
    email = str(payload.get("email", "")).strip()[:180]
    organization = str(payload.get("organization", "")).strip()[:160]
    locale = str(payload.get("locale", "fa")).lower()
    if not display_name:
        raise ValueError("Display name is required.")
    if locale not in {"fa", "en"}:
        raise ValueError("Unsupported locale.")
    db.execute("UPDATE accounts SET display_name=?,email=?,organization=?,locale=?,updated_at=? WHERE id=1", (display_name, email, organization, locale, now()))
    return db.fetch_one("SELECT * FROM accounts WHERE id=1") or {}


def plans_catalog() -> list[dict]:
    return [{"id": plan_id, **data} for plan_id, data in PLANS.items()]


def credit_packages() -> list[dict]:
    return db.fetch_all("SELECT * FROM credit_packages WHERE active=1 ORDER BY credits")


def start_checkout(kind: str, reference_id: str) -> dict:
    if kind == "credits":
        item = db.fetch_one("SELECT * FROM credit_packages WHERE id=? AND active=1", (reference_id,))
        if not item:
            raise LookupError("Credit package not found.")
        amount, credits = float(item["price_usd"]), int(item["credits"] * (100 + item["bonus_percent"]) / 100)
    elif kind == "marketplace":
        item = db.fetch_one("SELECT * FROM marketplace_items WHERE id=? AND active=1", (reference_id,))
        if not item:
            raise LookupError("Marketplace item not found.")
        amount, credits = float(item["price_usd"]), 0
    elif kind == "plan":
        item = PLANS.get(reference_id)
        if not item:
            raise LookupError("Plan not found.")
        amount, credits = float(item["monthly_price"] or 0), 0
    else:
        raise ValueError("Unsupported checkout type.")
    transaction_id = db.execute("INSERT INTO billing_transactions(account_id,kind,reference_id,amount_usd,credits,status,created_at) VALUES (1,?,?,?,?,?,?)", (kind, reference_id, amount, credits, "pending", now()))
    return {"id": transaction_id, "status": "pending", "amount_usd": amount, "message": "Checkout created. Connect a payment provider before production billing."}


def api_keys() -> list[dict]:
    return db.fetch_all("SELECT id,name,token_prefix,scopes,created_at,last_used_at,revoked_at FROM account_api_keys ORDER BY id DESC")


def create_api_key(name: str, scopes: str = "translate:write jobs:read") -> dict:
    name = str(name).strip()[:80]
    if not name:
        raise ValueError("API key name is required.")
    token = "jbt_live_" + secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    key_id = db.execute("INSERT INTO account_api_keys(account_id,name,token_prefix,token_hash,scopes,created_at) VALUES (1,?,?,?,?,?)", (name, token[:16], digest, scopes[:200], now()))
    return {"id": key_id, "name": name, "token": token, "token_prefix": token[:16], "scopes": scopes}


def revoke_api_key(key_id: int) -> None:
    db.execute("UPDATE account_api_keys SET revoked_at=? WHERE id=? AND account_id=1", (now(), key_id))


def marketplace(kind: str = "") -> list[dict]:
    params = (kind,) if kind else ()
    where = "AND m.kind=?" if kind else ""
    return db.fetch_all(f"""SELECT m.*, CASE WHEN a.item_id IS NULL THEN 0 ELSE 1 END AS installed
        FROM marketplace_items m LEFT JOIN account_marketplace a ON a.item_id=m.id AND a.account_id=1
        WHERE m.active=1 {where} ORDER BY m.featured DESC,m.rating DESC""", params)


def install_marketplace_item(item_id: str) -> dict:
    item = db.fetch_one("SELECT * FROM marketplace_items WHERE id=? AND active=1", (item_id,))
    if not item:
        raise LookupError("Marketplace item not found.")
    if float(item["price_usd"]) > 0:
        return start_checkout("marketplace", item_id)
    db.execute("INSERT OR IGNORE INTO account_marketplace(account_id,item_id,installed_at) VALUES (1,?,?)", (item_id, now()))
    db.execute("UPDATE marketplace_items SET installs=installs+1 WHERE id=?", (item_id,))
    return {"status": "installed", "item_id": item_id}


def orders() -> list[dict]:
    return db.fetch_all("SELECT * FROM translation_orders WHERE account_id=1 ORDER BY id DESC")


def create_order(payload: dict) -> dict:
    title = str(payload.get("title", "")).strip()[:200]
    service_type = str(payload.get("service_type", "specialized")).strip()[:40]
    source_language = str(payload.get("source_language", "EN")).strip().upper()[:12]
    target_language = str(payload.get("target_language", "FA")).strip().upper()[:12]
    if not title:
        raise ValueError("Order title is required.")
    timestamp = now()
    order_id = db.execute("""INSERT INTO translation_orders(account_id,title,service_type,source_language,target_language,word_count,budget_usd,deadline,notes,status,created_at,updated_at)
        VALUES (1,?,?,?,?,?,?,?,?,?,?,?)""", (title, service_type, source_language, target_language, max(0, int(payload.get("word_count", 0))), max(0, float(payload.get("budget_usd", 0))), str(payload.get("deadline", ""))[:30] or None, str(payload.get("notes", ""))[:2000], "submitted", timestamp, timestamp))
    return db.fetch_one("SELECT * FROM translation_orders WHERE id=?", (order_id,)) or {}


def create_business_request(payload: dict) -> dict:
    request_type = str(payload.get("request_type", "enterprise")).strip()[:40]
    contact_name = str(payload.get("contact_name", "")).strip()[:120]
    email = str(payload.get("email", "")).strip()[:180]
    if request_type not in {"enterprise", "publisher", "author", "api"}:
        raise ValueError("Unsupported request type.")
    if not contact_name or not email:
        raise ValueError("Contact name and email are required.")
    request_id = db.execute("INSERT INTO business_requests(account_id,request_type,company_name,contact_name,email,details,status,created_at) VALUES (1,?,?,?,?,?,?,?)", (request_type, str(payload.get("company_name", ""))[:160], contact_name, email, str(payload.get("details", ""))[:3000], "new", now()))
    return {"id": request_id, "status": "new"}


def publisher_overview() -> dict:
    languages = db.fetch_all("SELECT target_language AS language,COUNT(*) AS jobs FROM jobs GROUP BY target_language ORDER BY jobs DESC")
    return {
        "books": (db.fetch_one("SELECT COUNT(*) AS count FROM library_books WHERE archived=0") or {"count": 0})["count"],
        "active_projects": (db.fetch_one("SELECT COUNT(*) AS count FROM jobs WHERE status IN ('queued','running','paused')") or {"count": 0})["count"],
        "delivered": (db.fetch_one("SELECT COUNT(*) AS count FROM jobs WHERE status='completed'") or {"count": 0})["count"],
        "estimated_spend": (db.fetch_one("SELECT COALESCE(SUM(estimated_cost),0) AS total FROM jobs") or {"total": 0})["total"],
        "languages": languages,
    }

"""Local password authentication for KALIMA.

Single-user machine, stdlib only: PBKDF2-HMAC-SHA256 for password storage
(no new dependency for one hash function), ``secrets`` for session tokens.
The token itself never touches the database -- only its SHA-256 digest --
so a leaked database dump is not a login.

Threat model notes, stated plainly:

* The server binds loopback only and every mutating route already passes the
  Host/Origin guards in ``app/web.py``. Sessions ride an HttpOnly
  ``SameSite=Lax`` cookie, so page script cannot read the token and a
  cross-site top-level GET cannot spend it.
* There is no brute-force lockout. On a loopback-only server the attacker
  already runs code on the machine, where the database (and therefore the
  hashes) is directly readable -- a lockout would be theatre, not defence.

Every function takes the database as a parameter (like ``app/glossary``),
so tests pass ``Database(tmp_path / ...)`` and never touch the real file.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

SESSION_COOKIE = "kalima_session"
SESSION_DAYS = 30

_HASH_ALGORITHM = "pbkdf2-sha256"
_PBKDF2_ITERATIONS = 210_000
_SALT_BYTES = 16
_MIN_PASSWORD_LENGTH = 8
_MAX_PASSWORD_LENGTH = 200
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def hash_password(password: str) -> str:
    """Hash a password for storage. Format: ``algo$iters$salt$hash`` (base64)."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return "$".join((
        _HASH_ALGORITHM,
        str(_PBKDF2_ITERATIONS),
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    ))


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored hash. Never raises on bad input."""
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != _HASH_ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            base64.b64decode(salt.encode("ascii")),
            int(iterations),
        )
        return hmac.compare_digest(digest, base64.b64decode(expected.encode("ascii")))
    except (ValueError, TypeError, base64.binascii.Error):
        return False


def normalize_email(email: object) -> str:
    """Lowercase and validate an address. Raises ``ValueError`` when invalid."""
    address = str(email or "").strip().lower()
    if len(address) > 180 or not _EMAIL_PATTERN.match(address):
        raise ValueError("نشانی ایمیل معتبر نیست.")
    return address


def validate_password(password: object) -> str:
    """Enforce length bounds. Raises ``ValueError`` when invalid."""
    secret = str(password or "")
    if not _MIN_PASSWORD_LENGTH <= len(secret) <= _MAX_PASSWORD_LENGTH:
        raise ValueError("گذرواژه باید حداقل ۸ نویسه باشد.")
    return secret


def user_public(row: dict) -> dict:
    """The account shape the API returns. Never includes the password hash."""
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "created_at": row["created_at"],
    }


def signup(db, email: object, password: object, display_name: object = "") -> dict:
    """Create a user. Raises ``ValueError`` (bad input) or ``LookupError`` (taken)."""
    address = normalize_email(email)
    secret = validate_password(password)
    name = str(display_name or "").strip()[:100]
    if not name:
        raise ValueError("نام نمایشی لازم است.")
    if db.fetch_one("SELECT id FROM users WHERE email=?", (address,)):
        raise LookupError("این ایمیل قبلاً ثبت شده است.")
    timestamp = _now()
    user_id = db.execute(
        "INSERT INTO users(email, display_name, password_hash, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (address, name, hash_password(secret), timestamp, timestamp),
    )
    row = db.fetch_one("SELECT * FROM users WHERE id=?", (user_id,))
    assert row is not None
    return user_public(row)


def _dummy_verify() -> None:
    """Burn one hash on unknown emails so timing does not reveal who exists."""
    verify_password(secrets.token_hex(8), hash_password(secrets.token_hex(8)))


def login(db, email: object, password: object) -> tuple[dict, str]:
    """Check credentials and open a session. Returns (user, raw token).

    Unknown email and wrong password raise the same ``LookupError`` with the
    same message: the caller must not learn which half was wrong.
    """
    try:
        address = normalize_email(email)
    except ValueError:
        _dummy_verify()
        raise LookupError("ایمیل یا گذرواژه درست نیست.")
    row = db.fetch_one("SELECT * FROM users WHERE email=?", (address,))
    if row is None or not verify_password(str(password or ""), row["password_hash"]):
        if row is None:
            _dummy_verify()
        raise LookupError("ایمیل یا گذرواژه درست نیست.")
    token = secrets.token_urlsafe(32)
    timestamp = _now()
    db.execute(
        "INSERT INTO auth_sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (
            hashlib.sha256(token.encode("utf-8")).hexdigest(),
            row["id"],
            timestamp,
            (datetime.now(UTC) + timedelta(days=SESSION_DAYS)).isoformat(),
        ),
    )
    return user_public(row), token


def user_from_token(db, token: object) -> dict | None:
    """Resolve a session token to its user, or ``None`` when unknown/expired."""
    raw = str(token or "")
    if not raw:
        return None
    row = db.fetch_one(
        "SELECT u.*, s.expires_at AS expires_at FROM users u"
        " JOIN auth_sessions s ON s.user_id=u.id WHERE s.token_hash=?",
        (hashlib.sha256(raw.encode("utf-8")).hexdigest(),),
    )
    if row is None:
        return None
    try:
        expired = datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC)
    except (TypeError, KeyError, ValueError):
        return None
    if expired:
        db.execute(
            "DELETE FROM auth_sessions WHERE token_hash=?",
            (hashlib.sha256(raw.encode("utf-8")).hexdigest(),),
        )
        return None
    return user_public(row)


def logout(db, token: object) -> None:
    """Close a session. Unknown tokens are a no-op, never an error."""
    raw = str(token or "")
    if raw:
        db.execute(
            "DELETE FROM auth_sessions WHERE token_hash=?",
            (hashlib.sha256(raw.encode("utf-8")).hexdigest(),),
        )

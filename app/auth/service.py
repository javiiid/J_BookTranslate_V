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
# Device-list activity granularity: user_from_token touches last_seen_at at
# most this often, so request polling does not become WAL write churn.
LAST_SEEN_REFRESH_SECONDS = 300
# Login/logout audit trail keeps this many newest rows per user, so a
# brute-force storm cannot turn the security log into storage bloat.
AUTH_EVENT_KEEP = 200

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


def login(db, email: object, password: object, ip: object = None) -> tuple[dict, str]:
    """Check credentials and open a session. Returns (user, raw token).

    Unknown email and wrong password raise the same ``LookupError`` with the
    same message: the caller must not learn which half was wrong. Failures
    feed the DB-backed throttle (per email and, when known, per IP).
    """
    raw_ip = str(ip or "").strip()
    try:
        address = normalize_email(email)
    except ValueError:
        _dummy_verify()
        record_auth_failure(db, "password", "unknown")
        if raw_ip:
            record_auth_failure(db, "password-ip", raw_ip)
        raise LookupError("ایمیل یا گذرواژه درست نیست.")
    check_auth_throttle(db, "password", address)
    if raw_ip:
        check_auth_throttle(db, "password-ip", raw_ip)
    row = db.fetch_one("SELECT * FROM users WHERE email=?", (address,))
    if row is None or not verify_password(str(password or ""), row["password_hash"] or ""):
        if row is None:
            _dummy_verify()
        else:
            # A wrong password on a real account is exactly what the owner's
            # security log is for. Unknown emails stay out: logging them would
            # let anyone write arbitrary rows keyed by nothing.
            record_auth_event(db, row["id"], "login_failed", ip=raw_ip, detail="password")
        record_auth_failure(db, "password", address)
        if raw_ip:
            record_auth_failure(db, "password-ip", raw_ip)
        raise LookupError("ایمیل یا گذرواژه درست نیست.")
    token = secrets.token_urlsafe(32)
    timestamp = _now()
    db.execute(
        "INSERT INTO auth_sessions(token_hash, user_id, created_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
        (
            hashlib.sha256(token.encode("utf-8")).hexdigest(),
            row["id"],
            timestamp,
            (datetime.now(UTC) + timedelta(days=SESSION_DAYS)).isoformat(),
            timestamp,
        ),
    )
    record_auth_event(db, row["id"], "login", ip=raw_ip, detail="password")
    return user_public(row), token


def user_from_token(db, token: object) -> dict | None:
    """Resolve a session token to its user, or ``None`` when unknown/expired."""
    raw = str(token or "")
    if not raw:
        return None
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    row = db.fetch_one(
        "SELECT u.*, s.expires_at AS expires_at, s.last_seen_at AS last_seen_at FROM users u"
        " JOIN auth_sessions s ON s.user_id=u.id WHERE s.token_hash=?",
        (digest,),
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
            (digest,),
        )
        return None
    _touch_last_seen(db, digest, row.get("last_seen_at"))
    return user_public(row)


def _touch_last_seen(db, digest: str, last_seen: object) -> None:
    """Record session activity, at most once per ``LAST_SEEN_REFRESH_SECONDS``.

    Opportunistic on purpose: user_from_token runs on nearly every
    authenticated request, and a write per request would be pure WAL churn.
    A 5-minute granularity is plenty for a "last active" device list.
    """
    try:
        fresh = (
            last_seen
            and datetime.now(UTC) - datetime.fromisoformat(str(last_seen))
            < timedelta(seconds=LAST_SEEN_REFRESH_SECONDS)
        )
    except (TypeError, ValueError):
        fresh = False
    if not fresh:
        db.execute(
            "UPDATE auth_sessions SET last_seen_at=? WHERE token_hash=?",
            (_now(), digest),
        )


def logout(db, token: object) -> None:
    """Close a session. Unknown tokens are a no-op, never an error."""
    raw = str(token or "")
    if raw:
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        row = db.fetch_one("SELECT user_id FROM auth_sessions WHERE token_hash=?", (digest,))
        db.execute("DELETE FROM auth_sessions WHERE token_hash=?", (digest,))
        if row is not None:
            record_auth_event(db, row["user_id"], "logout")


def _session_user_id(db, token: object) -> int | None:
    """User id behind a live session, or None when unknown/expired."""
    row = user_from_token(db, token)
    if row is None:
        return None
    return row["id"]


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def list_sessions(db, token: object) -> list[dict]:
    """Live sessions of the caller, newest first. Raises LookupError when unknown."""
    user_id = _session_user_id(db, token)
    if user_id is None:
        raise LookupError("وارد نشده‌اید.")
    current = _token_hash(str(token or ""))
    rows = db.fetch_all(
        "SELECT token_hash, created_at, expires_at, last_seen_at FROM auth_sessions"
        " WHERE user_id=? ORDER BY created_at DESC",
        (user_id,),
    )
    return [
        {
            "id": row["token_hash"][:16],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            # Old rows predate the column; the migrate backfills from
            # created_at, and this fallback keeps the shape honest anyway.
            "last_seen_at": row.get("last_seen_at") or row["created_at"],
            "current": row["token_hash"] == current,
        }
        for row in rows
    ]


def revoke_session(db, token: object, session_id: object) -> None:
    """Close one of the caller's sessions by id prefix. Raises on unknown."""
    user_id = _session_user_id(db, token)
    if user_id is None:
        raise LookupError("وارد نشده‌اید.")
    prefix = str(session_id or "").strip().lower()
    if not prefix or len(prefix) < 8 or any(c not in "0123456789abcdef" for c in prefix):
        raise ValueError("شناسهٔ نشست نامعتبر است.")
    matches = db.fetch_all(
        "SELECT token_hash FROM auth_sessions WHERE user_id=? AND token_hash LIKE ?",
        (user_id, prefix + "%"),
    )
    if len(matches) != 1:
        raise LookupError("نشست پیدا نشد.")
    db.execute(
        "DELETE FROM auth_sessions WHERE user_id=? AND token_hash=?",
        (user_id, matches[0]["token_hash"]),
    )
    # Prefix only: the full hash is secret-equivalent, the list shows the
    # same 16 chars, and 8 are enough to correlate the two.
    record_auth_event(db, user_id, "session_revoked", detail=matches[0]["token_hash"][:8])


def revoke_all_sessions(db, token: object) -> int:
    """Close every session of the caller except the current one.

    Returns the number of sessions closed. This is the recovery path for a
    leaked cookie: one call invalidates everything the caller is not holding.
    """
    user_id = _session_user_id(db, token)
    if user_id is None:
        raise LookupError("وارد نشده‌اید.")
    current = _token_hash(str(token or ""))
    others = db.fetch_all(
        "SELECT token_hash FROM auth_sessions WHERE user_id=? AND token_hash!=?",
        (user_id, current),
    )
    if others:
        db.execute(
            "DELETE FROM auth_sessions WHERE user_id=? AND token_hash!=?",
            (user_id, current),
        )
        record_auth_event(db, user_id, "sessions_revoked", detail=str(len(others)))
    return len(others)


def change_password(db, token: object, current_password: object, new_password: object) -> dict:
    """Change password after proving the current one; other sessions die.

    Wrong current password raises the same LookupError as login, so the
    endpoint is not a password oracle. Returns the public user.
    """
    raw = str(token or "")
    user_id = _session_user_id(db, raw)
    if user_id is None:
        raise LookupError("وارد نشده‌اید.")
    row = db.fetch_one("SELECT * FROM users WHERE id=?", (user_id,))
    if row is None or not verify_password(str(current_password or ""), row["password_hash"] or ""):
        raise LookupError("گذرواژهٔ فعلی درست نیست.")
    secret = validate_password(new_password)
    timestamp = _now()
    db.execute(
        "UPDATE users SET password_hash=?, updated_at=? WHERE id=?",
        (hash_password(secret), timestamp, user_id),
    )
    revoke_all_sessions(db, raw)
    record_auth_event(db, user_id, "password_changed")
    return user_public(db.fetch_one("SELECT * FROM users WHERE id=?", (user_id,)))


# ============================================================
# LOGIN/LOGOUT AUDIT TRAIL
# ============================================================
#
# Who came in, from where, and what happened to their sessions. The device
# list answers "what is open now"; this answers "what happened". Bounded to
# AUTH_EVENT_KEEP newest rows per user on every insert.


def record_auth_event(db, user_id: int | None, event: str, ip: object = "", detail: object = "") -> None:
    """Append one audit row and prune the user's tail. Never raises."""
    try:
        db.execute(
            "INSERT INTO auth_events(user_id, event, created_at, ip, detail) VALUES (?, ?, ?, ?, ?)",
            (user_id, str(event)[:40], _now(), str(ip or "")[:80], str(detail or "")[:200]),
        )
        if user_id is not None:
            db.execute(
                "DELETE FROM auth_events WHERE user_id=? AND id NOT IN"
                " (SELECT id FROM auth_events WHERE user_id=? ORDER BY id DESC LIMIT ?)",
                (user_id, user_id, AUTH_EVENT_KEEP),
            )
    except (OSError, ValueError, TypeError):
        # Observability must never break authentication itself.
        pass


def list_auth_events(db, token: object, limit: object = 50) -> list[dict]:
    """Newest security events of the caller. Raises LookupError when unknown."""
    user_id = _session_user_id(db, token)
    if user_id is None:
        raise LookupError("وارد نشده‌اید.")
    try:
        count = max(1, min(100, int(str(limit or 50))))
    except (TypeError, ValueError):
        count = 50
    return db.fetch_all(
        "SELECT id, event, created_at, ip, detail FROM auth_events"
        " WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, count),
    )


# ============================================================
# LOGIN ABUSE THROTTLE (DB-backed)
# ============================================================
#
# The old loopback-only reasoning ("no brute-force lockout, it would be
# theatre") dies at launch: password and OTP endpoints now share a durable
# attempt log with progressive rejection. Counts live in the database so a
# restart does not reset the attacker's budget.

THROTTLE_WINDOW_SECONDS = 600
THROTTLE_MAX_FAILURES = 10


def _throttle_key(kind: str, scope: str) -> str:
    return f"{kind}:{scope.strip().lower()}"


def record_auth_failure(db, kind: str, scope: str) -> None:
    """Log one failed attempt for independent (kind, scope) throttling."""
    db.execute(
        "INSERT INTO auth_attempts(scope_key, created_at) VALUES (?, ?)",
        (_throttle_key(kind, str(scope or "")), _now()),
    )


def check_auth_throttle(db, kind: str, scope: str) -> None:
    """Raise LookupError when the scope exhausted its failure budget."""
    cutoff = (datetime.now(UTC) - timedelta(seconds=THROTTLE_WINDOW_SECONDS)).isoformat()
    row = db.fetch_one(
        "SELECT COUNT(*) AS count FROM auth_attempts WHERE scope_key=? AND created_at>?",
        (_throttle_key(kind, str(scope or "")), cutoff),
    )
    if row is not None and (row["count"] or 0) >= THROTTLE_MAX_FAILURES:
        raise LookupError("تلاش‌های ناموفق زیاد است؛ چند دقیقه دیگر تلاش کنید.")


# ============================================================
# PASSWORDLESS EMAIL OTP
# ============================================================

OTP_TTL_SECONDS = 600
OTP_MAX_ATTEMPTS = 5
OTP_MAX_SENDS_PER_WINDOW = 3
OTP_WINDOW_SECONDS = 600


def _smtp_configured() -> bool:
    try:
        from app.core.config import read_config_safe

        return bool((read_config_safe().get("smtp") or {}).get("enabled"))
    except (OSError, AttributeError, TypeError, ValueError):
        return False


def _otp_sender(kind: str = "log"):
    """Build the OTP sender. ``log`` writes to the server log (dev default)."""
    if kind == "smtp":
        return _smtp_otp_sender()
    return _log_otp_sender()


def _log_otp_sender():
    def send(email, code):
        print(f"[auth] OTP for {email}: {code} (log sender — no SMTP configured)")
        return "log"

    return send


def _smtp_otp_sender():
    from app.core.config import read_config_safe

    settings = (read_config_safe().get("smtp") or {})
    if not settings.get("enabled"):
        return _log_otp_sender()

    def send(email, code):
        import smtplib
        from email.message import EmailMessage

        message = EmailMessage()
        message["From"] = settings.get("from", "kalima@localhost")
        message["To"] = email
        message["Subject"] = "کد ورود کالیما"
        message.set_content(f"کد ورود شما: {code}\nاین کد ۱۰ دقیقه اعتبار دارد.")
        with smtplib.SMTP(str(settings.get("host", "localhost")), int(settings.get("port", 25))) as server:
            if settings.get("user"):
                server.login(str(settings.get("user")), str(settings.get("password", "")))
            server.send_message(message)
        return "smtp"

    return send


def _otp_hash(email: str, code: str) -> str:
    return hashlib.sha256(f"{email}\n{code}".encode("utf-8")).hexdigest()


def request_email_code(db, email: object, sender=None) -> dict:
    """Issue (or re-issue) a login code. Uniform success shape, always.

    Well-formed but unknown addresses get the same response as known ones so
    the endpoint cannot enumerate accounts. Malformed addresses raise
    ValueError like signup does.
    """
    address = normalize_email(email)
    timestamp = _now()
    row = db.fetch_one("SELECT * FROM auth_otps WHERE email=?", (address,))
    window_start = (
        datetime.now(UTC) - timedelta(seconds=OTP_WINDOW_SECONDS)
    ).isoformat()
    sends = 0
    if row is not None and str(row.get("window_started_at") or "") >= window_start:
        sends = int(row.get("sent_count") or 0)
    if sends >= OTP_MAX_SENDS_PER_WINDOW:
        raise LookupError("کد زیادی درخواست شده؛ چند دقیقه دیگر تلاش کنید.")
    code = f"{secrets.randbelow(1000000):06d}"
    send = sender or _otp_sender("smtp" if _smtp_configured() else "log")
    channel = send(address, code)
    if row is None:
        db.execute(
            "INSERT INTO auth_otps(email, code_hash, expires_at, attempts, used, sent_count, window_started_at, created_at)"
            " VALUES (?, ?, ?, 0, 0, 1, ?, ?)",
            (address, _otp_hash(address, code),
             (datetime.now(UTC) + timedelta(seconds=OTP_TTL_SECONDS)).isoformat(),
             timestamp, timestamp),
        )
    else:
        fresh_window = str(row.get("window_started_at") or "") < window_start
        db.execute(
            "UPDATE auth_otps SET code_hash=?, expires_at=?, attempts=0, used=0,"
            " sent_count=?, window_started_at=?, created_at=? WHERE email=?",
            (_otp_hash(address, code),
             (datetime.now(UTC) + timedelta(seconds=OTP_TTL_SECONDS)).isoformat(),
             1 if fresh_window else sends + 1,
             timestamp if fresh_window else row.get("window_started_at"),
             timestamp, address),
        )
    return {"sent": True, "channel": channel}


def verify_email_code(db, email: object, code: object) -> tuple[dict, str]:
    """Verify a login code; creates the account on first use. Returns (user, token)."""
    address = normalize_email(email)
    check_auth_throttle(db, "otp", address)
    row = db.fetch_one("SELECT * FROM auth_otps WHERE email=?", (address,))
    digest = _otp_hash(address, str(code or "").strip())
    valid = (
        row is not None
        and not row.get("used")
        and str(row.get("expires_at") or "") > _now()
        and int(row.get("attempts") or 0) < OTP_MAX_ATTEMPTS
        and secrets.compare_digest(str(row.get("code_hash") or ""), digest)
    )
    if not valid:
        record_auth_failure(db, "otp", address)
        if row is not None:
            attempts = int(row.get("attempts") or 0) + 1
            db.execute(
                "UPDATE auth_otps SET attempts=?, used=? WHERE email=?",
                (attempts, 1 if attempts >= OTP_MAX_ATTEMPTS else 0, address),
            )
        raise LookupError("کد ورود درست نیست یا منقضی شده است.")
    db.execute("UPDATE auth_otps SET used=1 WHERE email=?", (address,))
    existing = db.fetch_one("SELECT * FROM users WHERE email=?", (address,))
    timestamp = _now()
    if existing is None:
        name = address.split("@")[0][:100] or address
        # Empty hash, never NULL: older installs created users.password_hash
        # NOT NULL, and verify_password("") is always False anyway.
        user_id = db.execute(
            "INSERT INTO users(email, display_name, password_hash, created_at, updated_at)"
            " VALUES (?, ?, '', ?, ?)",
            (address, name, timestamp, timestamp),
        )
        existing = db.fetch_one("SELECT * FROM users WHERE id=?", (user_id,))
    db.execute("UPDATE users SET email_verified=1, updated_at=? WHERE id=?", (timestamp, existing["id"]))
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO auth_sessions(token_hash, user_id, created_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
        (
            hashlib.sha256(token.encode("utf-8")).hexdigest(),
            existing["id"],
            timestamp,
            (datetime.now(UTC) + timedelta(days=SESSION_DAYS)).isoformat(),
            timestamp,
        ),
    )
    record_auth_event(db, existing["id"], "login", detail="email-code")
    return user_public(db.fetch_one("SELECT * FROM users WHERE id=?", (existing["id"],))), token

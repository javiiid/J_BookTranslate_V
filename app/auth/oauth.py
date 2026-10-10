"""OAuth login (Google, Apple): authorization-code flow, stdlib HTTP only."""
from __future__ import annotations

import hashlib
import json
import secrets
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from app.auth.service import SESSION_DAYS

UTC = timezone.utc

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

STATE_TTL_SECONDS = 600


def _now() -> str:
    return datetime.now(UTC).isoformat()


def provider_status() -> dict:
    """Which social providers are fully configured (safe to offer as buttons).

    A provider counts as configured only when every key its start endpoint
    requires is present — the UI hides anything else instead of showing a
    button that can only fail.
    """
    google = oauth_config("google")
    apple = oauth_config("apple")
    return {
        "google": bool(str(google.get("client_id") or "").strip() and str(google.get("redirect_uri") or "").strip()),
        "apple": bool(
            str(apple.get("client_id") or "").strip()
            and str(apple.get("team_id") or "").strip()
            and str(apple.get("key_id") or "").strip()
            and str(apple.get("private_key") or "").strip()
            and str(apple.get("redirect_uri") or "").strip()
        ),
    }


def oauth_config(provider: str) -> dict:
    """Provider settings from config.yaml. Missing keys are the caller's error."""
    try:
        from app.core.config import read_config_safe

        return (read_config_safe().get("oauth") or {}).get(provider) or {}
    except (OSError, AttributeError, TypeError, ValueError):
        return {}


def frontend_origin() -> str:
    """Where the React SPA lives (dev: http://127.0.0.1:5173, prod: same origin).

    OAuth callbacks are top-level navigations on the BACKEND host, so the
    session cookie is set for the backend host. Redirecting back to the SPA
    origin keeps login/logout in one UI. Empty means same-origin (production
    single-origin deploy); set ``oauth.frontend_origin`` for dev.
    """
    try:
        from app.core.config import read_config_safe

        return str((read_config_safe().get("oauth") or {}).get("frontend_origin") or "").rstrip("/")
    except (OSError, AttributeError, TypeError, ValueError):
        return ""


def _require_config(provider: str, *keys: str) -> dict:
    settings = oauth_config(provider)
    missing = [key for key in keys if not str(settings.get(key) or "").strip()]
    if missing:
        raise ValueError(
            f"ورود با {provider} پیکربندی نشده است "
            f"(config.yaml → oauth.{provider}: {', '.join(missing)})."
        )
    return settings


def _http_post(url: str, fields: dict, timeout: float = 20.0) -> dict:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_get(url: str, timeout: float = 20.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def issue_state(db, provider: str) -> str:
    """One-time state token binding start → callback. Returns the raw state."""
    raw = secrets.token_urlsafe(24)
    db.execute(
        "INSERT INTO oauth_states(state_hash, provider, created_at) VALUES (?, ?, ?)",
        (hashlib.sha256(raw.encode("utf-8")).hexdigest(), provider, _now()),
    )
    return raw


def consume_state(db, provider: str, state: object) -> None:
    """Validate and burn a state token. Any mismatch is a hard failure."""
    raw = str(state or "")
    if not raw:
        raise ValueError("وضعیت ورود نامعتبر است.")
    row = db.fetch_one(
        "SELECT * FROM oauth_states WHERE state_hash=? AND provider=?",
        (hashlib.sha256(raw.encode("utf-8")).hexdigest(), provider),
    )
    if row is None:
        raise ValueError("وضعیت ورود نامعتبر است.")
    db.execute(
        "DELETE FROM oauth_states WHERE state_hash=?",
        (hashlib.sha256(raw.encode("utf-8")).hexdigest(),),
    )
    try:
        age = (datetime.now(UTC) - datetime.fromisoformat(row["created_at"])).total_seconds()
    except (TypeError, KeyError, ValueError):
        raise ValueError("وضعیت ورود نامعتبر است.")
    if age > STATE_TTL_SECONDS:
        raise ValueError("وضعیت ورود منقضی شده است.")


def google_start(db, redirect_after: str = "/library") -> dict:
    """Build the Google consent URL. The state is stored for the callback."""
    settings = _require_config("google", "client_id", "redirect_uri")
    state = issue_state(db, "google")
    params = urllib.parse.urlencode({
        "client_id": settings["client_id"],
        "redirect_uri": settings["redirect_uri"],
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": secrets.token_urlsafe(16),
        "access_type": "online",
        "prompt": "select_account",
    })
    return {"auth_url": f"{GOOGLE_AUTH_URL}?{params}", "state": state}


def _open_session(db, user_id: int) -> str:
    """Open a session exactly like password login does."""
    token = secrets.token_urlsafe(32)
    timestamp = _now()
    db.execute(
        "INSERT INTO auth_sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (
            hashlib.sha256(token.encode("utf-8")).hexdigest(),
            user_id,
            timestamp,
            (datetime.now(UTC) + timedelta(days=SESSION_DAYS)).isoformat(),
        ),
    )
    return token


def _link_or_create_oauth_user(db, *, provider: str, sub: str, email: str, name: str, verified: bool):
    """Find by provider sub, else by verified email, else create. Returns row."""
    column = "google_sub" if provider == "google" else "apple_sub"
    row = db.fetch_one(f"SELECT * FROM users WHERE {column}=?", (sub,))
    if row is not None:
        return row
    if verified:
        row = db.fetch_one("SELECT * FROM users WHERE email=?", (email,))
        if row is not None:
            db.execute(
                f"UPDATE users SET {column}=?, email_verified=1, updated_at=? WHERE id=?",
                (sub, _now(), row["id"]),
            )
            return db.fetch_one("SELECT * FROM users WHERE id=?", (row["id"],))
    timestamp = _now()
    user_id = db.execute(
        f"INSERT INTO users(email, display_name, password_hash, {column}, email_verified, created_at, updated_at)"
        " VALUES (?, ?, '', ?, ?, ?, ?)",
        (email, (name or email.split('@')[0])[:100], sub, 1 if verified else 0, timestamp, timestamp),
    )
    return db.fetch_one("SELECT * FROM users WHERE id=?", (user_id,))


def _public_user(db, user_id: int) -> dict:
    from app.auth.service import user_public

    return user_public(db.fetch_one("SELECT * FROM users WHERE id=?", (user_id,)))


def google_callback(db, code: object, state: object, http_post=None, http_get=None) -> tuple[dict, str]:
    """Finish Google login. Returns (public user, raw session token)."""
    from app.auth.service import normalize_email

    settings = _require_config("google", "client_id", "client_secret", "redirect_uri")
    consume_state(db, "google", state)
    if not str(code or "").strip():
        raise ValueError("کد ورود گوگل ارسال نشد.")
    post = http_post or _http_post
    get = http_get or _http_get
    try:
        tokens = post(GOOGLE_TOKEN_URL, {
            "code": str(code).strip(),
            "client_id": settings["client_id"],
            "client_secret": settings["client_secret"],
            "redirect_uri": settings["redirect_uri"],
            "grant_type": "authorization_code",
        })
    except Exception as exc:
        raise LookupError(f"تبادل کد گوگل ناموفق بود: {exc}")
    raw_id_token = str((tokens or {}).get("id_token") or "")
    if not raw_id_token:
        raise LookupError("گوگل شناسهٔ کاربر را برنگرداند.")
    try:
        claims = get(f"{GOOGLE_TOKENINFO_URL}?id_token={urllib.parse.quote(raw_id_token)}")
    except Exception as exc:
        raise LookupError(f"تأیید شناسهٔ گوگل ناموفق بود: {exc}")
    # Verify server-to-server: the token must be ours, issued by Google.
    if str((claims or {}).get("aud") or "") != str(settings["client_id"]):
        raise LookupError("شناسهٔ گوگل برای این برنامه نیست.")
    if str((claims or {}).get("iss") or "") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise LookupError("صادرکنندهٔ شناسهٔ گوگل نامعتبر است.")
    try:
        address = normalize_email(claims.get("email"))
    except (ValueError, TypeError, AttributeError):
        raise LookupError("گوگل ایمیل معتبر برنگرداند.")
    sub = str(claims.get("sub") or "")
    if not sub:
        raise LookupError("گوگل شناسهٔ کاربر را برنگرداند.")
    verified = bool(claims.get("email_verified"))
    row = _link_or_create_oauth_user(
        db, provider="google", sub=sub, email=address,
        name=str(claims.get("name") or ""), verified=verified,
    )
    return _public_user(db, row["id"]), _open_session(db, row["id"])


# ============================================================
# APPLE (requires `cryptography` — see requirements.txt)
# ============================================================

APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


def apple_start(db) -> dict:
    """Build the Apple consent URL."""
    settings = _require_config("apple", "client_id", "redirect_uri")
    state = issue_state(db, "apple")
    params = urllib.parse.urlencode({
        "client_id": settings["client_id"],
        "redirect_uri": settings["redirect_uri"],
        "response_type": "code",
        "scope": "name email",
        "response_mode": "query",
        "state": state,
        "nonce": secrets.token_urlsafe(16),
    })
    return {"auth_url": f"{APPLE_AUTH_URL}?{params}", "state": state}


def _apple_client_secret(settings: dict) -> str:
    """Sign the client_secret JWT (ES256). Needs the `cryptography` package."""
    try:
        import jwt
    except ImportError:
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec, utils
        except ImportError:
            raise ValueError(
                "ورود با اپل به بستهٔ cryptography نیاز دارد؛ نصب نیست."
            )
        key_data = str(settings.get("private_key") or "")
        if "PRIVATE KEY" not in key_data:
            raise ValueError("کلید خصوصی اپل در config.yaml معتبر نیست (oauth.apple.private_key).")
        private_key = serialization.load_pem_private_key(key_data.encode("utf-8"), password=None)
        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            raise ValueError("کلید خصوصی اپل باید EC (P-256) باشد.")
        now = int(time.time())
        header = {"kid": settings.get("key_id"), "alg": "ES256"}
        payload = {
            "iss": settings.get("team_id"), "iat": now, "exp": now + 3600,
            "aud": "https://appleid.apple.com", "sub": settings["client_id"],
        }
        signing_input = (
            _b64(json.dumps(header, separators=(",", ":")).encode())
            + b"." + _b64(json.dumps(payload, separators=(",", ":")).encode())
        )
        der = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = utils.decode_dss_signature(der)
        raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return (signing_input + b"." + _b64(raw)).decode("ascii")
    # PyJWT path, if a project ever prefers it.
    now = int(time.time())
    return jwt.encode(
        {"iss": settings.get("team_id"), "iat": now, "exp": now + 3600,
         "aud": "https://appleid.apple.com", "sub": settings["client_id"]},
        str(settings.get("private_key") or ""),
        algorithm="ES256",
        headers={"kid": settings.get("key_id")},
    )


def _b64(data: bytes) -> bytes:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _b64dec(data: str) -> bytes:
    import base64

    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _verify_apple_identity_token(raw_token: str, http_get=None) -> dict:
    """Verify an Apple identityToken against Apple's JWKS (RS256)."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
    except ImportError:
        raise ValueError("ورود با اپل به بستهٔ cryptography نیاز دارد؛ نصب نیست.")
    get = http_get or _http_get
    try:
        header_b64, payload_b64, signature_b64 = str(raw_token).split(".")
        header = json.loads(_b64dec(header_b64))
        payload = json.loads(_b64dec(payload_b64))
    except (ValueError, TypeError):
        raise LookupError("شناسهٔ اپل خراب است.")
    try:
        jwks = get(APPLE_JWKS_URL)
    except Exception as exc:
        raise LookupError(f"دریافت کلیدهای اپل ناموفق بود: {exc}")
    keys = [k for k in (jwks or {}).get("keys", []) if k.get("kid") == header.get("kid")]
    if not keys:
        raise LookupError("کلید امضای اپل پیدا نشد.")
    numbers = rsa.RSAPublicNumbers(
        int.from_bytes(_b64dec(keys[0]["e"]), "big"),
        int.from_bytes(_b64dec(keys[0]["n"]), "big"),
    )
    verifier = numbers.public_key()
    signed = f"{header_b64}.{payload_b64}".encode("ascii")
    try:
        verifier.verify(_b64dec(signature_b64), signed, padding.PKCS1v15(), hashes.SHA256())
    except Exception:
        raise LookupError("امضای شناسهٔ اپل نامعتبر است.")
    now = int(time.time())
    if int(payload.get("exp", 0)) < now:
        raise LookupError("شناسهٔ اپل منقضی شده است.")
    if str(payload.get("iss") or "") != "https://appleid.apple.com":
        raise LookupError("صادرکنندهٔ شناسهٔ اپل نامعتبر است.")
    return payload


def apple_callback(db, code: object, state: object, http_post=None, http_get=None) -> tuple[dict, str]:
    """Finish Apple login. Returns (public user, raw session token)."""
    from app.auth.service import normalize_email

    settings = _require_config(
        "apple", "client_id", "team_id", "key_id", "private_key", "redirect_uri"
    )
    consume_state(db, "apple", state)
    if not str(code or "").strip():
        raise ValueError("کد ورود اپل ارسال نشد.")
    post = http_post or _http_post
    secret = _apple_client_secret(settings)
    try:
        tokens = post(APPLE_TOKEN_URL, {
            "code": str(code).strip(),
            "client_id": settings["client_id"],
            "client_secret": secret,
            "redirect_uri": settings["redirect_uri"],
            "grant_type": "authorization_code",
        })
    except Exception as exc:
        raise LookupError(f"تبادل کد اپل ناموفق بود: {exc}")
    raw_id_token = str((tokens or {}).get("id_token") or "")
    if not raw_id_token:
        raise LookupError("اپل شناسهٔ کاربر را برنگرداند.")
    claims = _verify_apple_identity_token(raw_id_token, http_get)
    if str(claims.get("aud") or "") != str(settings["client_id"]):
        raise LookupError("شناسهٔ اپل برای این برنامه نیست.")
    email = str(claims.get("email") or "")
    address = normalize_email(email) if email else f"apple-{claims.get('sub')}@privaterelay.appleid.com"
    sub = str(claims.get("sub") or "")
    if not sub:
        raise LookupError("اپل شناسهٔ کاربر را برنگرداند.")
    row = _link_or_create_oauth_user(
        db, provider="apple", sub=sub, email=address,
        name="", verified=bool(email and claims.get("email_verified")),
    )
    return _public_user(db, row["id"]), _open_session(db, row["id"])

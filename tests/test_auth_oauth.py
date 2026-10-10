# ============================================================
# OAuth Login Tests (Google + Apple)
# ============================================================
#
# No real network is used: HTTP is stubbed at the function boundary.
# Apple crypto uses freshly generated test keys, never real secrets.
#
# ============================================================

import time

import pytest

from app.auth import oauth
from app.storage.database import Database


@pytest.fixture
def database(tmp_path):
    return Database(tmp_path / "oauth.db")


@pytest.fixture
def google_settings(monkeypatch):
    settings = {
        "google": {
            "client_id": "test-google-client-id",
            "client_secret": "test-secret",
            "redirect_uri": "http://127.0.0.1:8765/api/auth/oauth/google/callback",
        }
    }
    monkeypatch.setattr(oauth, "oauth_config", lambda provider: settings.get(provider, {}))
    return settings["google"]


def google_claims(settings, **overrides):
    claims = {
        "aud": settings["client_id"],
        "iss": "https://accounts.google.com",
        "sub": "google-sub-1",
        "email": "person@example.com",
        "email_verified": True,
        "name": "Test Person",
    }
    claims.update(overrides)
    return claims


def stub_http(claims):
    def http_post(url, fields):
        assert "token" in url
        return {"id_token": "stub-id-token"}

    def http_get(url):
        assert "tokeninfo" in url
        return dict(claims)

    return http_post, http_get


# ============================================================
# GOOGLE
# ============================================================

def test_google_start_needs_config(database):
    with pytest.raises(ValueError) as exc:
        oauth.google_start(database)
    assert "oauth.google" in str(exc.value)


def test_provider_status_reflects_config(database, monkeypatch):
    assert oauth.provider_status() == {"google": False, "apple": False}
    monkeypatch.setattr(
        oauth, "oauth_config",
        lambda provider: {"client_id": "x", "redirect_uri": "http://x/cb"} if provider == "google" else {},
    )
    assert oauth.provider_status() == {"google": True, "apple": False}


def test_google_login_creates_and_relinks_user(database, google_settings):
    started = oauth.google_start(database, )
    assert started["auth_url"].startswith("https://accounts.google.com/")
    http_post, http_get = stub_http(google_claims(google_settings))
    user, token = oauth.google_callback(database, "auth-code", started["state"], http_post, http_get)
    assert user["email"] == "person@example.com"
    row = database.fetch_one("SELECT * FROM users WHERE email=?", ("person@example.com",))
    assert row["google_sub"] == "google-sub-1"
    assert row["email_verified"] == 1
    from app.auth import service

    assert service.user_from_token(database, token) is not None
    # State is single-use.
    with pytest.raises(ValueError):
        oauth.google_callback(database, "auth-code", started["state"], http_post, http_get)
    # Second login links the same user, no duplicate.
    started = oauth.google_start(database)
    user2, _ = oauth.google_callback(database, "auth-code", started["state"], http_post, http_get)
    assert user2["id"] == user["id"]
    assert database.fetch_one("SELECT COUNT(*) AS c FROM users")["c"] == 1


def test_google_rejects_wrong_audience(database, google_settings):
    started = oauth.google_start(database)
    http_post, http_get = stub_http(google_claims(google_settings, aud="someone-else"))
    with pytest.raises(LookupError):
        oauth.google_callback(database, "auth-code", started["state"], http_post, http_get)


def test_google_rejects_bad_state(database, google_settings):
    http_post, http_get = stub_http(google_claims(google_settings))
    with pytest.raises(ValueError):
        oauth.google_callback(database, "auth-code", "bogus-state", http_post, http_get)


def test_google_links_verified_email_to_password_account(database, google_settings):
    from app.auth import service

    service.signup(database, "person@example.com", "s3cret-pass", "Old Name")
    started = oauth.google_start(database)
    http_post, http_get = stub_http(google_claims(google_settings))
    user, _ = oauth.google_callback(database, "auth-code", started["state"], http_post, http_get)
    row = database.fetch_one("SELECT * FROM users WHERE email=?", ("person@example.com",))
    assert user["id"] == row["id"]
    assert row["google_sub"] == "google-sub-1"
    # Password login still works on the linked account.
    linked, _ = service.login(database, "person@example.com", "s3cret-pass")
    assert linked["id"] == user["id"]


# ============================================================
# APPLE
# ============================================================

def apple_test_keys():
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa

    signing = ec.generate_private_key(ec.SECP256R1())
    pem = signing.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    verifier = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = verifier.public_key().public_numbers()
    return signing, pem, verifier, public


def b64url(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def apple_id_token(verifier, kid, payload):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    header = b64url(b'{"kid":"' + kid.encode() + b'","alg":"RS256"}')
    body = b64url(__import__("json").dumps(payload, separators=(",", ":")).encode())
    signature = verifier.sign(f"{header}.{body}".encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{body}.{b64url(signature)}"


@pytest.fixture
def apple_setup(monkeypatch, database):
    signing, pem, verifier, public = apple_test_keys()

    def ntob(number, length):
        return number.to_bytes(length, "big")

    jwks = {"keys": [{
        "kty": "RSA", "kid": "test-kid", "use": "sig", "alg": "RS256",
        "n": b64url(ntob(public.n, 256)), "e": b64url(ntob(public.e, 3)),
    }]}
    settings = {
        "apple": {
            "client_id": "com.example.kalima",
            "team_id": "TEAM123",
            "key_id": "KEY123",
            "private_key": pem,
            "redirect_uri": "http://127.0.0.1:8765/api/auth/oauth/apple/callback",
        }
    }
    monkeypatch.setattr(oauth, "oauth_config", lambda provider: settings.get(provider, {}))

    def payload(**overrides):
        claims = {
            "iss": "https://appleid.apple.com",
            "aud": "com.example.kalima",
            "exp": int(time.time()) + 3600,
            "sub": "apple-sub-1",
            "email": "person@example.com",
            "email_verified": True,
        }
        claims.update(overrides)
        return claims

    return {"settings": settings["apple"], "verifier": verifier, "jwks": jwks, "payload": payload}


def test_apple_login_verifies_signature_and_links(database, apple_setup):
    started = oauth.apple_start(database)
    assert started["auth_url"].startswith("https://appleid.apple.com/")
    raw = apple_id_token(apple_setup["verifier"], "test-kid", apple_setup["payload"]())

    def http_post(url, fields):
        assert "appleid.apple.com/auth/token" in url
        assert fields["client_secret"]
        return {"id_token": raw}

    def http_get(url):
        assert url == oauth.APPLE_JWKS_URL
        return apple_setup["jwks"]

    user, token = oauth.apple_callback(database, "auth-code", started["state"], http_post, http_get)
    assert user["email"] == "person@example.com"
    row = database.fetch_one("SELECT * FROM users WHERE email=?", ("person@example.com",))
    assert row["apple_sub"] == "apple-sub-1"
    from app.auth import service

    assert service.user_from_token(database, token) is not None


def test_apple_rejects_tampered_token(database, apple_setup):
    started = oauth.apple_start(database)
    raw = apple_id_token(apple_setup["verifier"], "test-kid", apple_setup["payload"]())
    tampered = raw[:-4] + ("AAAA" if not raw.endswith("AAAA") else "BBBB")

    def http_post(url, fields):
        return {"id_token": tampered}

    def http_get(url):
        return apple_setup["jwks"]

    with pytest.raises(LookupError):
        oauth.apple_callback(database, "auth-code", started["state"], http_post, http_get)

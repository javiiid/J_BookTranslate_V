"""Local password authentication: hashing, signup/login/logout, sessions."""
from __future__ import annotations

import hashlib

import pytest

from app.auth import service
from app.storage.database import Database


@pytest.fixture
def database(tmp_path):
    return Database(tmp_path / "auth.db")


def test_auth_tables_exist_after_migrate(database):
    names = {row["name"] for row in database.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'auth_sessions')")}
    assert names == {"users", "auth_sessions"}


def test_password_hash_verifies_and_wrong_password_fails():
    stored = service.hash_password("correct horse 123")
    assert service.verify_password("correct horse 123", stored)
    assert not service.verify_password("correct horse 124", stored)


def test_password_hash_is_salted_and_versioned():
    first, second = service.hash_password("same secret"), service.hash_password("same secret")
    assert first != second
    assert first.startswith("pbkdf2-sha256$")


def test_malformed_hash_never_raises():
    assert not service.verify_password("anything", "not-a-hash")
    assert not service.verify_password("anything", "")
    assert not service.verify_password("anything", "pbkdf2-sha256$abc$def$ghi")


def test_signup_returns_public_user_without_hash(database):
    user = service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    assert user["email"] == "user@example.com"
    assert user["display_name"] == "Test User"
    assert "password_hash" not in user
    row = database.fetch_one("SELECT password_hash FROM users WHERE email=?", ("user@example.com",))
    assert row["password_hash"] != "s3cret-pass"


def test_email_is_normalized(database):
    user = service.signup(database, "  USER@Example.COM ", "s3cret-pass", "Test User")
    assert user["email"] == "user@example.com"


def test_signup_duplicate_email_raises_lookup(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    with pytest.raises(LookupError):
        service.signup(database, "user@example.com", "other-pass", "Other User")


@pytest.mark.parametrize("email", ["", "not-an-email", "a@b", "x" * 200 + "@example.com"])
def test_signup_rejects_bad_email(database, email):
    with pytest.raises(ValueError):
        service.signup(database, email, "s3cret-pass", "Test User")


@pytest.mark.parametrize("password", ["short", "", "x" * 201])
def test_signup_rejects_bad_password(database, password):
    with pytest.raises(ValueError):
        service.signup(database, "user@example.com", password, "Test User")


def test_signup_requires_display_name(database):
    with pytest.raises(ValueError):
        service.signup(database, "user@example.com", "s3cret-pass", "   ")


def test_login_returns_user_and_token(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    user, token = service.login(database, "user@example.com", "s3cret-pass")
    assert user["email"] == "user@example.com"
    assert token
    stored = database.fetch_one("SELECT token_hash FROM auth_sessions")
    assert stored["token_hash"] == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert stored["token_hash"] != token


def test_unknown_email_and_wrong_password_share_one_error(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    with pytest.raises(LookupError) as unknown:
        service.login(database, "nobody@example.com", "s3cret-pass")
    with pytest.raises(LookupError) as wrong:
        service.login(database, "user@example.com", "wrong-pass")
    assert str(unknown.value) == str(wrong.value)


def test_token_resolves_user_and_unknown_token_resolves_nothing(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, token = service.login(database, "user@example.com", "s3cret-pass")
    assert service.user_from_token(database, token)["email"] == "user@example.com"
    assert service.user_from_token(database, "bogus") is None
    assert service.user_from_token(database, "") is None


def test_logout_revokes_session(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, token = service.login(database, "user@example.com", "s3cret-pass")
    service.logout(database, token)
    assert service.user_from_token(database, token) is None
    service.logout(database, "bogus")


def test_expired_session_is_rejected_and_cleaned(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, token = service.login(database, "user@example.com", "s3cret-pass")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    database.execute("UPDATE auth_sessions SET expires_at='2000-01-01T00:00:00+00:00' WHERE token_hash=?", (digest,))
    assert service.user_from_token(database, token) is None
    assert database.fetch_one("SELECT 1 FROM auth_sessions WHERE token_hash=?", (digest,)) is None

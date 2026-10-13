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


def test_change_password_needs_current_and_kills_other_sessions(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, first = service.login(database, "user@example.com", "s3cret-pass")
    _, second = service.login(database, "user@example.com", "s3cret-pass")
    with pytest.raises(LookupError):
        service.change_password(database, first, "wrong-pass", "new-secret-pass")
    assert service.user_from_token(database, first) is not None
    assert service.user_from_token(database, second) is not None
    user = service.change_password(database, first, "s3cret-pass", "new-secret-pass")
    assert user["email"] == "user@example.com"
    assert service.user_from_token(database, first) is not None
    assert service.user_from_token(database, second) is None
    _, third = service.login(database, "user@example.com", "new-secret-pass")
    assert third
    with pytest.raises(LookupError):
        service.login(database, "user@example.com", "s3cret-pass")


def test_list_and_revoke_single_session(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, first = service.login(database, "user@example.com", "s3cret-pass")
    _, second = service.login(database, "user@example.com", "s3cret-pass")
    items = service.list_sessions(database, first)
    assert len(items) == 2
    assert sum(1 for item in items if item["current"]) == 1
    other = next(item for item in items if not item["current"])
    service.revoke_session(database, first, other["id"])
    assert service.user_from_token(database, first) is not None
    assert service.user_from_token(database, second) is None
    with pytest.raises(LookupError):
        service.revoke_session(database, first, other["id"])
    with pytest.raises(ValueError):
        service.revoke_session(database, first, "xyz")
    with pytest.raises(LookupError):
        service.list_sessions(database, "bogus")


def test_revoke_all_keeps_only_caller(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, first = service.login(database, "user@example.com", "s3cret-pass")
    _, second = service.login(database, "user@example.com", "s3cret-pass")
    _, third = service.login(database, "user@example.com", "s3cret-pass")
    closed = service.revoke_all_sessions(database, first)
    assert closed == 2
    assert service.user_from_token(database, first) is not None
    assert service.user_from_token(database, second) is None
    assert service.user_from_token(database, third) is None
    assert service.revoke_all_sessions(database, first) == 0
    with pytest.raises(LookupError):
        service.revoke_all_sessions(database, "bogus")


def make_capturing_sender(captured):
    def send(email, code):
        captured.append((email, code))
        return "test"

    return send


def test_email_code_login_creates_account_and_session(database):
    captured = []
    result = service.request_email_code(database, "new@example.com", sender=make_capturing_sender(captured))
    assert result == {"sent": True, "channel": "test"}
    assert len(captured) == 1
    email, code = captured[0]
    assert email == "new@example.com"
    user, token = service.verify_email_code(database, "new@example.com", code)
    assert user["email"] == "new@example.com"
    assert service.user_from_token(database, token) is not None
    row = database.fetch_one("SELECT email_verified, password_hash FROM users WHERE email=?", ("new@example.com",))
    assert row["email_verified"] == 1
    assert row["password_hash"] == ""
    # Password login refuses passwordless accounts without revealing why.
    with pytest.raises(LookupError):
        service.login(database, "new@example.com", "anything")


def test_email_code_wrong_attempts_invalidate(database):
    captured = []
    service.request_email_code(database, "new@example.com", sender=make_capturing_sender(captured))
    for _ in range(5):
        with pytest.raises(LookupError):
            service.verify_email_code(database, "new@example.com", "000000")
    _, code = captured[0]
    with pytest.raises(LookupError):
        service.verify_email_code(database, "new@example.com", code)


def test_email_code_expiry_and_resend_window(database):
    captured = []
    service.request_email_code(database, "new@example.com", sender=make_capturing_sender(captured))
    database.execute("UPDATE auth_otps SET expires_at='2000-01-01T00:00:00+00:00' WHERE email=?", ("new@example.com",))
    with pytest.raises(LookupError):
        service.verify_email_code(database, "new@example.com", captured[0][1])
    for _ in range(2):
        service.request_email_code(database, "new@example.com", sender=make_capturing_sender(captured))
    with pytest.raises(LookupError):
        service.request_email_code(database, "new@example.com", sender=make_capturing_sender(captured))


def test_email_code_responses_do_not_enumerate(database):
    captured = []
    assert service.request_email_code(database, "ghost@example.com", sender=make_capturing_sender(captured))["sent"] is True
    with pytest.raises(ValueError):
        service.request_email_code(database, "not-an-email", sender=make_capturing_sender(captured))


def test_password_login_throttle_after_failures(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    service.signup(database, "other@example.com", "s3cret-pass", "Other User")
    for _ in range(10):
        with pytest.raises(LookupError):
            service.login(database, "user@example.com", "wrong-pass", ip="10.0.0.9")
    with pytest.raises(LookupError) as throttled:
        service.login(database, "user@example.com", "s3cret-pass", ip="10.0.0.9")
    assert "تلاش‌های ناموفق" in str(throttled.value)
    # Per-email scope follows the address to a clean IP.
    with pytest.raises(LookupError):
        service.login(database, "user@example.com", "s3cret-pass", ip="10.0.0.10")
    # An untouched account on a clean IP is unaffected.
    _, token = service.login(database, "other@example.com", "s3cret-pass", ip="10.0.0.10")
    assert token


def test_auth_tables_include_events_and_last_seen(database):
    tables = {row["name"] for row in database.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'auth_sessions', 'auth_events')")}
    assert tables == {"users", "auth_sessions", "auth_events"}
    columns = {row["name"] for row in database.fetch_all("PRAGMA table_info(auth_sessions)")}
    assert "last_seen_at" in columns
    indexes = {row["name"] for row in database.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='auth_events'")}
    assert "idx_auth_events_user_time" in indexes


def test_login_and_logout_are_recorded(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, token = service.login(database, "user@example.com", "s3cret-pass", ip="10.0.0.1")
    events = service.list_auth_events(database, token)
    assert [event["event"] for event in events] == ["login"]
    assert events[0]["detail"] == "password"
    assert events[0]["ip"] == "10.0.0.1"
    service.logout(database, token)
    # The logged-out token cannot read the trail; a fresh login can.
    _, fresh = service.login(database, "user@example.com", "s3cret-pass")
    assert [event["event"] for event in service.list_auth_events(database, fresh)] == [
        "login", "logout", "login",
    ]


def test_wrong_password_on_known_account_is_recorded_but_unknown_email_is_not(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    with pytest.raises(LookupError):
        service.login(database, "user@example.com", "wrong-pass")
    with pytest.raises(LookupError):
        service.login(database, "ghost@example.com", "wrong-pass")
    _, token = service.login(database, "user@example.com", "s3cret-pass")
    kinds = [(event["event"], event["detail"]) for event in service.list_auth_events(database, token)]
    assert ("login_failed", "password") in kinds
    assert sum(1 for kind in kinds if kind[0] == "login_failed") == 1


def test_email_code_login_is_recorded(database):
    captured = []
    service.request_email_code(database, "new@example.com", sender=make_capturing_sender(captured))
    _, token = service.verify_email_code(database, "new@example.com", captured[0][1])
    assert service.list_auth_events(database, token)[0]["detail"] == "email-code"


def test_last_seen_starts_at_login_and_refreshes_when_stale(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, token = service.login(database, "user@example.com", "s3cret-pass")
    items = service.list_sessions(database, token)
    assert len(items) == 1
    assert items[0]["last_seen_at"] == items[0]["created_at"]
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    database.execute(
        "UPDATE auth_sessions SET last_seen_at='2000-01-01T00:00:00+00:00' WHERE token_hash=?", (digest,))
    assert service.user_from_token(database, token) is not None
    row = database.fetch_one("SELECT last_seen_at FROM auth_sessions WHERE token_hash=?", (digest,))
    assert row["last_seen_at"] != "2000-01-01T00:00:00+00:00"
    assert service.list_sessions(database, token)[0]["last_seen_at"] == row["last_seen_at"]
    # A fresh stamp is left alone: no write churn on every request.
    assert service.user_from_token(database, token) is not None
    kept = database.fetch_one("SELECT last_seen_at FROM auth_sessions WHERE token_hash=?", (digest,))
    assert kept["last_seen_at"] == row["last_seen_at"]


def test_revoke_and_password_change_are_recorded(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, first = service.login(database, "user@example.com", "s3cret-pass")
    _, second = service.login(database, "user@example.com", "s3cret-pass")
    items = service.list_sessions(database, first)
    other = next(item for item in items if not item["current"])
    service.revoke_session(database, first, other["id"])
    _, third = service.login(database, "user@example.com", "s3cret-pass")
    assert third
    service.change_password(database, first, "s3cret-pass", "new-secret-pass")
    events = {event["event"]: event["detail"] for event in service.list_auth_events(database, first)}
    assert events["session_revoked"] == other["id"][:8]
    assert events["sessions_revoked"] == "1"
    assert events["password_changed"] == ""


def test_auth_events_are_pruned_to_newest_keep(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, token = service.login(database, "user@example.com", "s3cret-pass")
    user = service.user_from_token(database, token)
    assert user is not None
    for number in range(210):
        service.record_auth_event(database, user["id"], "login", detail=str(number))
    details = {row["detail"] for row in database.fetch_all("SELECT detail FROM auth_events")}
    assert len(details) == service.AUTH_EVENT_KEEP
    assert "209" in details
    assert "0" not in details


def test_list_auth_events_requires_login_and_caps_limit(database):
    service.signup(database, "user@example.com", "s3cret-pass", "Test User")
    _, token = service.login(database, "user@example.com", "s3cret-pass")
    with pytest.raises(LookupError):
        service.list_auth_events(database, "bogus")
    assert len(service.list_auth_events(database, token, 500)) <= 100
    assert len(service.list_auth_events(database, token, "junk")) >= 1

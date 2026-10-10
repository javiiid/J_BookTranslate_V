# ============================================================
# Model Fallback Tests
# ============================================================
#
# A cheaper fallback model serves a chunk only after the primary
# model exhausts all retries — instead of the job dying.
#
# No real API request is sent. No API tokens are consumed.
#
# ============================================================

from pathlib import Path

import pytest

import app.core.retry as retry_module
from app.calibration.documents import make_epub
from app.calibration.runner import translate_unit_with_fallback
from app.calibration.service import CalibrationService
from app.core.retry import RetryError
from app.storage.database import Database
from app.translation.translator import (
    process_translations,
    translate_chunk,
)


# ============================================================
# FAKES
# ============================================================

class FakeAPIError(Exception):
    """Fake API exception with an HTTP status code."""

    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    """Fail on the primary model, succeed on the fallback model."""

    def __init__(self, primary_model, fail_times=99):
        self.primary_model = primary_model
        self.fail_times = fail_times
        self.primary_calls = 0
        self.fallback_calls = 0

    def create(self, model, messages, temperature, **kwargs):
        if model == self.primary_model:
            self.primary_calls += 1
            if self.primary_calls <= self.fail_times:
                raise FakeAPIError("Service Unavailable", 503)
        else:
            self.fallback_calls += 1
        return FakeResponse("متن ترجمه‌شده")


class FakeChat:
    def __init__(self, completions):
        self.completions = completions


class FakeClient:
    def __init__(self, completions):
        self.chat = FakeChat(completions)


def no_sleep():
    """Disable real backoff waiting for the whole test module."""
    original = retry_module.interruptible_sleep
    retry_module.interruptible_sleep = (
        lambda seconds, stop_event=None: None
    )
    return original


import contextlib


@contextlib.contextmanager
def fast_retries():
    original = no_sleep()
    try:
        yield
    finally:
        retry_module.interruptible_sleep = original


PRIMARY = "gpt-5.6-terra"
FALLBACK = "gemini-3.1-flash-lite"


def make_client(fail_times=99):
    completions = FakeCompletions(PRIMARY, fail_times=fail_times)
    return FakeClient(completions), completions


# ============================================================
# TRANSLATE_CHUNK
# ============================================================

def test_fallback_serves_chunk_after_primary_exhausts():
    client, completions = make_client(fail_times=99)
    record = []
    with fast_retries():
        result = translate_chunk(
            client=client,
            text="Hello world.",
            chunk_id="chunk-0",
            from_lang="EN",
            to_lang="FA",
            model=PRIMARY,
            filetype="epub",
            fallback_model=FALLBACK,
            fallback_record=record,
        )
    assert result == "متن ترجمه‌شده"
    assert completions.primary_calls == 5
    assert completions.fallback_calls == 1
    assert record == ["chunk-0"]


def test_no_fallback_configured_keeps_old_behavior():
    client, completions = make_client(fail_times=99)
    with fast_retries():
        try:
            translate_chunk(
                client=client,
                text="Hello world.",
                chunk_id="chunk-0",
                model=PRIMARY,
                filetype="epub",
            )
            raise AssertionError("expected RetryError")
        except RetryError:
            pass
    assert completions.primary_calls == 5
    assert completions.fallback_calls == 0


def test_primary_recovery_never_touches_fallback():
    client, completions = make_client(fail_times=2)
    record = []
    with fast_retries():
        result = translate_chunk(
            client=client,
            text="Hello world.",
            chunk_id="chunk-0",
            model=PRIMARY,
            filetype="epub",
            fallback_model=FALLBACK,
            fallback_record=record,
        )
    assert result == "متن ترجمه‌شده"
    assert completions.primary_calls == 3
    assert completions.fallback_calls == 0
    assert record == []


def test_non_retryable_error_never_falls_back():
    client, completions = make_client()

    def unauthorized(model, messages, temperature, **kwargs):
        if model == PRIMARY:
            completions.primary_calls += 1
            raise FakeAPIError("Unauthorized", 401)
        completions.fallback_calls += 1
        return FakeResponse("متن ترجمه‌شده")

    completions.create = unauthorized
    with fast_retries():
        try:
            translate_chunk(
                client=client,
                text="Hello world.",
                chunk_id="chunk-0",
                model=PRIMARY,
                filetype="epub",
                fallback_model=FALLBACK,
                fallback_record=[],
            )
            raise AssertionError("expected the 401 to propagate")
        except FakeAPIError as exc:
            assert exc.status_code == 401
    assert completions.primary_calls == 1
    assert completions.fallback_calls == 0


def test_invalid_fallback_model_rejected():
    client, _ = make_client()
    with fast_retries():
        try:
            translate_chunk(
                client=client,
                text="Hello world.",
                chunk_id="chunk-0",
                model=PRIMARY,
                fallback_model="no-such-model",
            )
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
        try:
            translate_chunk(
                client=client,
                text="Hello world.",
                chunk_id="chunk-0",
                model=PRIMARY,
                fallback_model=PRIMARY,
            )
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


def test_process_translations_completes_job_on_fallback(tmp_path):
    client, completions = make_client(fail_times=99)
    paths = {
        "job_dir": tmp_path,
        "translations_file": tmp_path / "translations.json",
    }
    chunks = [(f"chunk-{i}", f"Source sentence {i}.") for i in range(2)]
    with fast_retries():
        translations, _, _ = process_translations(
            client,
            chunks,
            {},
            "resume",
            "EN",
            "FA",
            paths,
            model=PRIMARY,
            filetype="epub",
            fallback_model=FALLBACK,
        )
    assert len(translations) == 2
    assert completions.primary_calls == 10
    assert completions.fallback_calls == 2
    import json

    record = json.loads((tmp_path / "fallback.json").read_text(encoding="utf-8"))
    assert record["fallback_model"] == FALLBACK
    assert sorted(record["chunks"]) == ["chunk-0", "chunk-1"]


# ============================================================
# CALIBRATION PROFILE
# ============================================================

def make_service(tmp_path):
    database = Database(tmp_path / "test.db")
    return CalibrationService(database, tmp_path / "calibrations")


def make_book(tmp_path):
    book = tmp_path / "book.epub"
    make_epub(
        book,
        [("Chapter 1", "<p>" + "Hello world. " * 50 + "</p>")],
        "Test Book",
    )
    return book


def test_calibration_create_accepts_cheaper_fallback(tmp_path):
    service = make_service(tmp_path)
    payload = service.create(
        make_book(tmp_path),
        "book.epub",
        {"model": "gpt-5.6-luna", "final_model": PRIMARY, "fallback_model": FALLBACK},
    )
    assert payload["profile"]["fallback_model"] == FALLBACK


def test_calibration_create_rejects_bad_fallback(tmp_path):
    service = make_service(tmp_path)
    book = make_book(tmp_path)
    # Unknown model.
    with pytest.raises(ValueError):
        service.create(book, "book.epub", {"final_model": PRIMARY, "fallback_model": "no-such-model"})
    # Same as final.
    with pytest.raises(ValueError):
        service.create(book, "book.epub", {"final_model": PRIMARY, "fallback_model": PRIMARY})
    # Pricier than final (terra costs more than luna).
    with pytest.raises(ValueError):
        service.create(
            book, "book.epub",
            {"model": "gpt-5.6-luna", "final_model": "gpt-5.6-luna", "fallback_model": PRIMARY},
        )


def test_calibration_edit_sets_clears_and_revalidates_fallback(tmp_path):
    service = make_service(tmp_path)
    created = service.create(
        make_book(tmp_path), "book.epub", {"model": "gpt-5.6-luna", "final_model": PRIMARY}
    )
    identifier = created["id"]
    edited = service.edit(identifier, {"fallback_model": FALLBACK, "revision": created["revision"]})
    assert edited["profile"]["fallback_model"] == FALLBACK
    cleared = service.edit(identifier, {"fallback_model": None, "revision": edited["revision"]})
    assert cleared["profile"]["fallback_model"] is None
    # Changing final_model to something the fallback is NOT cheaper than fails.
    edited = service.edit(identifier, {"fallback_model": "gpt-5.6-luna", "revision": cleared["revision"]})
    with pytest.raises(ValueError):
        service.edit(identifier, {"final_model": FALLBACK, "revision": edited["revision"]})


# ============================================================
# CALIBRATED RUNNER HELPER
# ============================================================

class StubService:
    """Only translate_unit matters to the helper under test."""

    def __init__(self, fail_primary_times=99):
        self.fail_primary_times = fail_primary_times
        self.primary_calls = 0
        self.fallback_calls = 0

    def translate_unit(self, session, unit, model, phase="full"):
        if model == PRIMARY:
            self.primary_calls += 1
            if self.primary_calls <= self.fail_primary_times:
                raise FakeAPIError("Service Unavailable", 503)
            return {"html": "<p>primary</p>"}, "key-primary"
        self.fallback_calls += 1
        return {"html": "<p>fallback</p>"}, "key-fallback"


def test_runner_helper_falls_back_on_retryable_error():
    service = StubService()
    unit = {"id": "u1"}
    result, key, fell_back = translate_unit_with_fallback(
        service, {}, unit, PRIMARY, FALLBACK
    )
    assert fell_back is True
    assert result["origin"] == "fallback"
    assert result["model"] == FALLBACK
    assert service.primary_calls == 1
    assert service.fallback_calls == 1


def test_runner_helper_skips_fallback_for_non_retryable():
    service = StubService()

    def deny(session, unit, model, phase="full"):
        raise FakeAPIError("Unauthorized", 401)

    service.translate_unit = deny
    try:
        translate_unit_with_fallback(service, {}, {"id": "u1"}, PRIMARY, FALLBACK)
        raise AssertionError("expected the 401 to propagate")
    except FakeAPIError as exc:
        assert exc.status_code == 401
    assert service.fallback_calls == 0


def test_runner_helper_without_fallback_raises():
    service = StubService()
    try:
        translate_unit_with_fallback(service, {}, {"id": "u1"}, PRIMARY, None)
        raise AssertionError("expected the 503 to propagate")
    except FakeAPIError:
        pass
    assert service.fallback_calls == 0

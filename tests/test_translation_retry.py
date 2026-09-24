# ============================================================
# Translation Retry Integration Test
# ============================================================
#
# This test verifies that translate_chunk()
# correctly uses the centralized retry system.
#
# No real API request is sent.
# No API tokens are consumed.
#
# Test scenario:
#
#   Attempt 1 -> 503
#   Attempt 2 -> 503
#   Attempt 3 -> SUCCESS
#
# Expected result:
#
#   - translate_chunk() retries automatically
#   - temporary 503 errors are retried
#   - backoff is executed
#   - successful translation is returned
#   - total API calls = 3
#
# ============================================================

from unittest.mock import Mock

from app.translation.translator import translate_chunk
from app.core.retry import RetryError


# ============================================================
# FAKE API ERROR
# ============================================================

class FakeAPIError(Exception):
    """
    Fake API exception used to simulate
    an OpenAI-compatible HTTP error.
    """

    def __init__(
        self,
        message,
        status_code,
    ):
        super().__init__(message)

        self.status_code = status_code


# ============================================================
# FAKE API RESPONSE
# ============================================================

class FakeMessage:
    """Fake API message object."""

    def __init__(self, content):
        self.content = content


class FakeChoice:
    """Fake API choice object."""

    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    """Fake API response object."""

    def __init__(self, content):
        self.choices = [
            FakeChoice(content)
        ]


# ============================================================
# FAKE API CLIENT
# ============================================================

class FakeCompletions:
    """
    Fake chat.completions implementation.

    Behavior:

        Call 1 -> 503
        Call 2 -> 503
        Call 3 -> success
    """

    def __init__(self):

        self.call_count = 0

    def create(
        self,
        model,
        messages,
        temperature,
        **kwargs,
    ):
        self.call_count += 1

        print(
            f"Fake API call #{self.call_count}"
        )

        # ----------------------------------------------------
        # First request -> 503
        # ----------------------------------------------------

        if self.call_count == 1:

            print(
                "Simulating HTTP 503..."
            )

            raise FakeAPIError(
                "Service Unavailable",
                status_code=503,
            )

        # ----------------------------------------------------
        # Second request -> 503
        # ----------------------------------------------------

        if self.call_count == 2:

            print(
                "Simulating HTTP 503..."
            )

            raise FakeAPIError(
                "Service Unavailable",
                status_code=503,
            )

        # ----------------------------------------------------
        # Third request -> success
        # ----------------------------------------------------

        print(
            "Simulating successful API response..."
        )

        return FakeResponse(
            "<html><body>Translated text</body></html>"
        )


class FakeChat:
    """Fake chat API."""

    def __init__(self):

        self.completions = FakeCompletions()


class FakeClient:
    """Fake OpenAI-compatible client."""

    def __init__(self):

        self.chat = FakeChat()


# ============================================================
# TEST 1
# RETRY 503 UNTIL SUCCESS
# ============================================================

def test_translation_retry_success():

    print()
    print("=" * 60)
    print("TEST 1: 503 RETRY -> SUCCESS")
    print("=" * 60)

    client = FakeClient()

    # --------------------------------------------------------
    # IMPORTANT:
    # Patch retry sleep so the test does NOT actually wait.
    # --------------------------------------------------------

    import app.core.retry as retry_module

    original_sleep = retry_module.interruptible_sleep

    retry_module.interruptible_sleep = (
        lambda seconds, stop_event=None: print(
            f"[TEST] Skipping {seconds:g}s wait"
        )
    )

    try:

        result = translate_chunk(
            client=client,
            text="<html><body>Hello</body></html>",
            chunk_id="chunk-0",
            from_lang="EN",
            to_lang="FA",
            model="gpt-5.6-terra",
            filetype="epub",
        )

    finally:

        retry_module.interruptible_sleep = (
            original_sleep
        )

    # --------------------------------------------------------
    # Validate translation
    # --------------------------------------------------------

    assert result == (
        "<html><body>Translated text</body></html>"
    )

    # --------------------------------------------------------
    # Validate retry count
    # --------------------------------------------------------

    assert client.chat.completions.call_count == 3

    print()
    print(
        "✓ Translation returned successfully."
    )

    print(
        "✓ 503 error was retried."
    )

    print(
        "✓ Two failed attempts were followed "
        "by one successful attempt."
    )

    print(
        "✓ Total API calls: 3"
    )

    print(
        "✓ TEST 1 PASSED"
    )


# ============================================================
# TEST 2
# RETRY EXHAUSTION
# ============================================================

def test_translation_retry_exhausted():

    print()
    print("=" * 60)
    print("TEST 2: RETRY EXHAUSTION")
    print("=" * 60)

    client = FakeClient()

    # --------------------------------------------------------
    # Make every request fail with 503.
    # --------------------------------------------------------

    def always_fail(
        model,
        messages,
        temperature,
        **kwargs,
    ):
        client.chat.completions.call_count += 1

        print(
            f"Fake API call #{client.chat.completions.call_count}"
        )

        raise FakeAPIError(
            "Service Unavailable",
            status_code=503,
        )

    client.chat.completions.create = always_fail

    # --------------------------------------------------------
    # Disable real waiting.
    # --------------------------------------------------------

    import app.core.retry as retry_module

    original_sleep = retry_module.interruptible_sleep

    retry_module.interruptible_sleep = (
        lambda seconds, stop_event=None: print(
            f"[TEST] Skipping {seconds:g}s wait"
        )
    )

    try:

        try:

            translate_chunk(
                client=client,
                text="<html><body>Hello</body></html>",
                chunk_id="chunk-1",
                from_lang="EN",
                to_lang="FA",
                model="gpt-5.6-terra",
                filetype="epub",
            )

            raise AssertionError(
                "translate_chunk() should have failed "
                "after retry exhaustion."
            )

        except RetryError as error:

            print()
            print(
                "✓ RetryError received."
            )

            assert error.last_exception is not None

            assert (
                getattr(
                    error.last_exception,
                    "status_code",
                    None,
                )
                == 503
            )

    finally:

        retry_module.interruptible_sleep = (
            original_sleep
        )

    # --------------------------------------------------------
    # MAX_RETRIES = 5
    # Therefore total attempts must be 5.
    # --------------------------------------------------------

    assert (
        client.chat.completions.call_count
        == 5
    )

    print(
        "✓ Retry attempts exhausted correctly."
    )

    print(
        "✓ Total API calls: 5"
    )

    print(
        "✓ TEST 2 PASSED"
    )


# ============================================================
# TEST 3
# NON-RETRYABLE ERROR
# ============================================================

def test_translation_non_retryable_error():

    print()
    print("=" * 60)
    print("TEST 3: NON-RETRYABLE ERROR")
    print("=" * 60)

    client = FakeClient()

    # --------------------------------------------------------
    # Simulate HTTP 400.
    #
    # 400 is NOT retryable.
    # --------------------------------------------------------

    def bad_request(
        model,
        messages,
        temperature,
        **kwargs,
    ):
        client.chat.completions.call_count += 1

        print(
            f"Fake API call #{client.chat.completions.call_count}"
        )

        raise FakeAPIError(
            "Bad Request",
            status_code=400,
        )

    client.chat.completions.create = bad_request

    try:

        translate_chunk(
            client=client,
            text="<html><body>Hello</body></html>",
            chunk_id="chunk-2",
            from_lang="EN",
            to_lang="FA",
            model="gpt-5.6-terra",
            filetype="epub",
        )

        raise AssertionError(
            "translate_chunk() should have raised "
            "the non-retryable error."
        )

    except FakeAPIError as error:

        assert (
            error.status_code
            == 400
        )

    # --------------------------------------------------------
    # 400 must NOT be retried.
    # --------------------------------------------------------

    assert (
        client.chat.completions.call_count
        == 1
    )

    print(
        "✓ HTTP 400 was not retried."
    )

    print(
        "✓ Total API calls: 1"
    )

    print(
        "✓ TEST 3 PASSED"
    )


# ============================================================
# TEST RUNNER
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("TRANSLATION RETRY INTEGRATION TEST")
    print("=" * 60)

    test_translation_retry_success()

    test_translation_retry_exhausted()

    test_translation_non_retryable_error()

    print()
    print("=" * 60)
    print("ALL TRANSLATION RETRY TESTS PASSED ✓")
    print("=" * 60)
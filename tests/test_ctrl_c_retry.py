# ============================================================
# Ctrl+C During Retry Test
# ============================================================
#
# This test verifies that Ctrl+C can interrupt the retry
# backoff immediately.
#
# No real API request is sent.
# No real waiting is performed.
# No API tokens are consumed.
#
# Test scenario:
#
#   API call #1
#       ↓
#   HTTP 503
#       ↓
#   Retry backoff
#       ↓
#   Ctrl+C
#       ↓
#   STOP IMMEDIATELY
#
# Expected:
#
#   - KeyboardInterrupt is raised
#   - No second API request is made
#   - RetryError is NOT raised
#   - Retry system does not continue
#
# ============================================================

from unittest.mock import Mock

from app.core.retry import retry_operation


# ============================================================
# FAKE API ERROR
# ============================================================

class FakeAPIError(Exception):
    """
    Fake API error used to simulate HTTP 503.
    """

    def __init__(
        self,
        message="Service Unavailable",
        status_code=503,
    ):
        super().__init__(message)

        self.status_code = status_code


# ============================================================
# TEST 1
# CTRL+C DURING RETRY WAIT
# ============================================================

def test_ctrl_c_during_retry_wait():

    print()
    print("=" * 60)
    print("TEST 1: CTRL+C DURING RETRY WAIT")
    print("=" * 60)

    # --------------------------------------------------------
    # Track API calls.
    # --------------------------------------------------------

    api_call_count = {
        "value": 0
    }

    # --------------------------------------------------------
    # Fake operation.
    #
    # First API request fails with 503.
    #
    # If retry happens, this function would be called again.
    # That must NOT happen.
    # --------------------------------------------------------

    def fake_operation():

        api_call_count["value"] += 1

        print(
            f"Fake API call #{api_call_count['value']}"
        )

        raise FakeAPIError(
            status_code=503
        )

    # --------------------------------------------------------
    # Fake sleep.
    #
    # Instead of actually waiting 5 seconds, simulate
    # Ctrl+C immediately.
    # --------------------------------------------------------

    def interrupting_sleep(seconds):

        print()
        print(
            f"[TEST] Retry waiting for {seconds:g}s..."
        )

        print(
            "[TEST] Simulating Ctrl+C..."
        )

        raise KeyboardInterrupt

    # --------------------------------------------------------
    # Execute retry system.
    # --------------------------------------------------------

    try:

        retry_operation(
            operation=fake_operation,

            max_attempts=5,

            base_delay=5,

            max_delay=80,

            sleep_func=interrupting_sleep,
        )

        raise AssertionError(
            "retry_operation() should have raised "
            "KeyboardInterrupt."
        )

    except KeyboardInterrupt:

        print()
        print(
            "✓ KeyboardInterrupt received."
        )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Only the first API request should have happened.
    #
    # If this is 2 or more, retry continued after Ctrl+C.
    # --------------------------------------------------------

    assert (
        api_call_count["value"]
        == 1
    )

    print(
        "✓ No additional API request was made."
    )

    print(
        "✓ Retry stopped immediately."
    )

    print(
        "✓ TEST 1 PASSED"
    )


# ============================================================
# TEST 2
# CTRL+C MUST NOT BECOME RetryError
# ============================================================

def test_ctrl_c_is_not_retry_error():

    print()
    print("=" * 60)
    print("TEST 2: CTRL+C IS NOT RetryError")
    print("=" * 60)

    api_call_count = {
        "value": 0
    }

    def fake_operation():

        api_call_count["value"] += 1

        raise FakeAPIError(
            status_code=503
        )

    def interrupting_sleep(seconds):

        print(
            f"[TEST] Simulating Ctrl+C "
            f"during {seconds:g}s backoff..."
        )

        raise KeyboardInterrupt

    try:

        retry_operation(
            operation=fake_operation,

            max_attempts=5,

            base_delay=5,

            max_delay=80,

            sleep_func=interrupting_sleep,
        )

        raise AssertionError(
            "Expected KeyboardInterrupt."
        )

    except KeyboardInterrupt:

        print(
            "✓ Correct exception: KeyboardInterrupt"
        )

    except Exception as error:

        raise AssertionError(
            f"Ctrl+C was converted into "
            f"{type(error).__name__}"
        )

    assert (
        api_call_count["value"]
        == 1
    )

    print(
        "✓ Ctrl+C was not converted into RetryError."
    )

    print(
        "✓ TEST 2 PASSED"
    )


# ============================================================
# TEST 3
# RETRY STILL WORKS WITHOUT CTRL+C
# ============================================================

def test_retry_still_works_after_interrupt_test():

    print()
    print("=" * 60)
    print("TEST 3: NORMAL RETRY STILL WORKS")
    print("=" * 60)

    api_call_count = {
        "value": 0
    }

    def fake_operation():

        api_call_count["value"] += 1

        print(
            f"Fake API call #{api_call_count['value']}"
        )

        if api_call_count["value"] < 3:

            raise FakeAPIError(
                status_code=503
            )

        return "SUCCESS"

    sleep_calls = []

    def fake_sleep(seconds):

        sleep_calls.append(seconds)

        print(
            f"[TEST] Skipping {seconds:g}s wait"
        )

    result = retry_operation(
        operation=fake_operation,

        max_attempts=5,

        base_delay=5,

        max_delay=80,

        sleep_func=fake_sleep,
    )

    # --------------------------------------------------------
    # Validate result.
    # --------------------------------------------------------

    assert result == "SUCCESS"

    # --------------------------------------------------------
    # 503 -> retry -> 503 -> retry -> success
    # --------------------------------------------------------

    assert (
        api_call_count["value"]
        == 3
    )

    # --------------------------------------------------------
    # Backoff should be:
    #
    # attempt 1 -> 5 seconds
    # attempt 2 -> 10 seconds
    # --------------------------------------------------------

    assert sleep_calls == [
        5,
        10,
    ]

    print(
        "✓ Retry still works normally."
    )

    print(
        "✓ API calls: 3"
    )

    print(
        "✓ Backoff: 5s -> 10s"
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
    print("CTRL+C RETRY SAFETY TEST")
    print("=" * 60)

    test_ctrl_c_during_retry_wait()

    test_ctrl_c_is_not_retry_error()

    test_retry_still_works_after_interrupt_test()

    print()
    print("=" * 60)
    print("ALL CTRL+C RETRY TESTS PASSED ✓")
    print("=" * 60)
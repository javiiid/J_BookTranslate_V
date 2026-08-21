# ============================================================
# Retry System Tests
# ============================================================

from app.core.retry import (
    calculate_backoff,
    should_retry,
    retry_operation,
    RetryError,
)


# ============================================================
# Fake HTTP Exception
# ============================================================

class FakeAPIError(Exception):
    """
    Fake API exception used for offline testing.
    """

    def __init__(self, status_code, message="API error"):
        super().__init__(message)
        self.status_code = status_code


# ============================================================
# Test 1 - Backoff Calculation
# ============================================================

def test_backoff():

    print("[1/6] Testing backoff calculation...")

    assert calculate_backoff(1) == 5
    assert calculate_backoff(2) == 10
    assert calculate_backoff(3) == 20
    assert calculate_backoff(4) == 40
    assert calculate_backoff(5) == 80

    print("✓ Backoff calculation passed.")


# ============================================================
# Test 2 - Retryable Errors
# ============================================================

def test_retryable_errors():

    print("[2/6] Testing retryable errors...")

    retryable_codes = [
        429,
        500,
        502,
        503,
        504,
    ]

    for status_code in retryable_codes:

        error = FakeAPIError(status_code)

        assert should_retry(error)

        print(
            f"✓ HTTP {status_code} is retryable."
        )


# ============================================================
# Test 3 - Permanent Errors
# ============================================================

def test_permanent_errors():

    print("[3/6] Testing permanent errors...")

    permanent_codes = [
        400,
        401,
        403,
        404,
    ]

    for status_code in permanent_codes:

        error = FakeAPIError(status_code)

        assert not should_retry(error)

        print(
            f"✓ HTTP {status_code} is permanent."
        )


# ============================================================
# Test 4 - Retry Until Success
# ============================================================

def test_retry_until_success():

    print("[4/6] Testing retry until success...")

    attempts = {
        "count": 0
    }

    sleep_calls = []

    def fake_sleep(seconds):

        sleep_calls.append(seconds)

    def operation():

        attempts["count"] += 1

        if attempts["count"] < 3:

            raise FakeAPIError(503)

        return "SUCCESS"

    result = retry_operation(
        operation,
        max_attempts=5,
        sleep_func=fake_sleep,
    )

    assert result == "SUCCESS"

    assert attempts["count"] == 3

    assert sleep_calls == [
        5,
        10,
    ]

    print("✓ Retry succeeded after temporary errors.")
    print(
        f"✓ Attempts: {attempts['count']}"
    )
    print(
        f"✓ Backoff sequence: {sleep_calls}"
    )


# ============================================================
# Test 5 - Permanent Error Stops Immediately
# ============================================================

def test_permanent_error():

    print(
        "[5/6] Testing permanent error handling..."
    )

    attempts = {
        "count": 0
    }

    def fake_sleep(seconds):

        raise AssertionError(
            "Permanent error should not sleep."
        )

    def operation():

        attempts["count"] += 1

        raise FakeAPIError(404)

    try:

        retry_operation(
            operation,
            max_attempts=5,
            sleep_func=fake_sleep,
        )

        raise AssertionError(
            "Expected FakeAPIError."
        )

    except FakeAPIError as error:

        assert error.status_code == 404

    assert attempts["count"] == 1

    print(
        "✓ Permanent error stopped immediately."
    )
    print(
        f"✓ Attempts: {attempts['count']}"
    )


# ============================================================
# Test 6 - Retry Exhaustion
# ============================================================

def test_retry_exhaustion():

    print("[6/6] Testing retry exhaustion...")

    attempts = {
        "count": 0
    }

    sleep_calls = []

    def fake_sleep(seconds):

        sleep_calls.append(seconds)

    def operation():

        attempts["count"] += 1

        raise FakeAPIError(503)

    try:

        retry_operation(
            operation,
            max_attempts=5,
            sleep_func=fake_sleep,
        )

        raise AssertionError(
            "Expected RetryError."
        )

    except RetryError as error:

        assert error.last_exception is not None

        assert (
            error.last_exception.status_code
            == 503
        )

    assert attempts["count"] == 5

    assert sleep_calls == [
        5,
        10,
        20,
        40,
    ]

    print(
        "✓ Retry exhaustion handled correctly."
    )

    print(
        f"✓ Total attempts: {attempts['count']}"
    )

    print(
        f"✓ Backoff sequence: {sleep_calls}"
    )


# ============================================================
# Test Runner
# ============================================================

def main():

    print()
    print("=" * 60)
    print("RETRY SYSTEM TEST")
    print("=" * 60)
    print()
    print(
        "IMPORTANT: This test sends NO API requests."
    )
    print(
        "Token usage: 0"
    )
    print()

    test_backoff()

    print()

    test_retryable_errors()

    print()

    test_permanent_errors()

    print()

    test_retry_until_success()

    print()

    test_permanent_error()

    print()

    test_retry_exhaustion()

    print()
    print("=" * 60)
    print("RETRY SYSTEM TEST PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
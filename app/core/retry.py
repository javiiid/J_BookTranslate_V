# ============================================================
# Retry Utilities
# ============================================================

import time
from threading import Event
from typing import Callable, Optional, Set


# ============================================================
# Retryable HTTP Status Codes
# ============================================================

DEFAULT_RETRYABLE_STATUS_CODES: Set[int] = {
    429,  # Rate limit
    500,  # Internal server error
    502,  # Bad gateway
    503,  # Service unavailable
    504,  # Gateway timeout
}


# ============================================================
# Retry Error
# ============================================================

class RetryError(Exception):
    """
    Raised when an operation fails after all retry attempts.
    """

    def __init__(
        self,
        message: str,
        last_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.last_exception = last_exception


# ============================================================
# Status Code Detection
# ============================================================

def get_status_code(exception: Exception) -> Optional[int]:
    """
    Extract an HTTP status code from an exception.

    Supports both:

        exception.status_code

    and:

        exception.response.status_code
    """

    # --------------------------------------------------------
    # Direct status_code
    # --------------------------------------------------------

    status_code = getattr(
        exception,
        "status_code",
        None,
    )

    if status_code is not None:

        try:
            return int(status_code)

        except (TypeError, ValueError):
            pass

    # --------------------------------------------------------
    # Response status_code
    # --------------------------------------------------------

    response = getattr(
        exception,
        "response",
        None,
    )

    if response is not None:

        status_code = getattr(
            response,
            "status_code",
            None,
        )

        if status_code is not None:

            try:
                return int(status_code)

            except (TypeError, ValueError):
                pass

    return None


# ============================================================
# Retry Decision
# ============================================================

def should_retry(
    exception: Exception,
    retryable_status_codes: Optional[Set[int]] = None,
) -> bool:
    """
    Determine whether an exception should be retried.

    Only configured temporary HTTP errors are retryable.
    """

    if retryable_status_codes is None:

        retryable_status_codes = (
            DEFAULT_RETRYABLE_STATUS_CODES
        )

    status_code = get_status_code(
        exception
    )

    return (
        status_code
        in retryable_status_codes
    )


# ============================================================
# Exponential Backoff
# ============================================================

def calculate_backoff(
    attempt: int,
    base_delay: float = 5.0,
    max_delay: float = 80.0,
) -> float:
    """
    Calculate exponential retry delay.

    Example:

        attempt 1 -> 5 seconds
        attempt 2 -> 10 seconds
        attempt 3 -> 20 seconds
        attempt 4 -> 40 seconds
        attempt 5 -> 80 seconds
    """

    if attempt < 1:

        attempt = 1

    if base_delay < 0:

        raise ValueError(
            "base_delay cannot be negative."
        )

    if max_delay < 0:

        raise ValueError(
            "max_delay cannot be negative."
        )

    delay = (
        base_delay
        * (2 ** (attempt - 1))
    )

    return min(
        delay,
        max_delay,
    )


# ============================================================
# Interruptible Sleep
# ============================================================

def interruptible_sleep(
    seconds: float,
    stop_event: Optional[Event] = None,
) -> None:
    """
    Wait for a specified amount of time.

    If stop_event is provided and becomes set,
    KeyboardInterrupt is raised immediately.
    """

    if seconds <= 0:

        return

    # --------------------------------------------------------
    # Normal sleep
    # --------------------------------------------------------

    if stop_event is None:

        time.sleep(seconds)

        return

    # --------------------------------------------------------
    # Interruptible sleep
    # --------------------------------------------------------

    interrupted = stop_event.wait(
        seconds
    )

    if interrupted:

        raise KeyboardInterrupt


# ============================================================
# Retry Operation
# ============================================================

def retry_operation(
    operation: Callable,
    max_attempts: int = 5,
    base_delay: float = 5.0,
    max_delay: float = 80.0,
    retryable_status_codes: Optional[Set[int]] = None,
    sleep_func: Optional[Callable] = None,
    stop_event: Optional[Event] = None,
):
    """
    Execute an operation with retry support.

    Temporary errors are retried.

    Permanent errors are raised immediately.

    Parameters
    ----------
    operation:
        Function that performs the operation.

    max_attempts:
        Maximum number of total attempts.

    base_delay:
        Initial retry delay.

    max_delay:
        Maximum retry delay.

    retryable_status_codes:
        HTTP status codes that should be retried.

    sleep_func:
        Optional custom sleep function.

        Useful for tests so the test suite does not
        actually wait.

    stop_event:
        Optional Event used to interrupt retry waiting.

    Returns
    -------
    Any
        Result returned by operation().

    Raises
    ------
    RetryError
        If all retry attempts fail.

    KeyboardInterrupt
        If retry waiting is interrupted.

    Exception
        Immediately for non-retryable errors.
    """

    # ========================================================
    # Validate arguments
    # ========================================================

    if max_attempts < 1:

        raise ValueError(
            "max_attempts must be at least 1."
        )

    if base_delay < 0:

        raise ValueError(
            "base_delay cannot be negative."
        )

    if max_delay < 0:

        raise ValueError(
            "max_delay cannot be negative."
        )

    # ========================================================
    # Default Sleep Function
    # ========================================================

    if sleep_func is None:

        sleep_func = (
            lambda seconds:
                interruptible_sleep(
                    seconds,
                    stop_event,
                )
        )

    # ========================================================
    # Retry Loop
    # ========================================================

    last_exception = None

    for attempt in range(
        1,
        max_attempts + 1,
    ):

        try:

            # ------------------------------------------------
            # Execute operation
            # ------------------------------------------------

            return operation()

        # ====================================================
        # Ctrl+C
        # ====================================================

        except KeyboardInterrupt:

            print(
                "\nRetry interrupted by user."
            )

            raise

        # ====================================================
        # Operation Error
        # ====================================================

        except Exception as exception:

            last_exception = exception

            status_code = get_status_code(
                exception
            )

            # ------------------------------------------------
            # Permanent Error
            # ------------------------------------------------

            if not should_retry(
                exception,
                retryable_status_codes,
            ):

                print(
                    f"\nNon-retryable error "
                    f"(status={status_code})."
                )

                raise

            # ------------------------------------------------
            # Retry Limit Reached
            # ------------------------------------------------

            if attempt >= max_attempts:

                break

            # ------------------------------------------------
            # Calculate Delay
            # ------------------------------------------------

            delay = calculate_backoff(
                attempt,
                base_delay,
                max_delay,
            )

            print()
            print(
                "-" * 60
            )

            print(
                "TEMPORARY ERROR"
            )

            print(
                f"Status code : {status_code}"
            )

            print(
                f"Attempt     : "
                f"{attempt}/{max_attempts}"
            )

            print(
                f"Next retry  : "
                f"{delay:g} seconds"
            )

            print(
                "Press Ctrl+C to stop."
            )

            print(
                "-" * 60
            )

            # ------------------------------------------------
            # Wait Before Retry
            # ------------------------------------------------

            sleep_func(
                delay
            )

    # ========================================================
    # Retry Exhausted
    # ========================================================

    raise RetryError(
        (
            "Operation failed after "
            f"{max_attempts} attempts."
        ),
        last_exception=last_exception,
    )
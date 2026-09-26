"""Adaptive rate limiting for provider requests.

The pipeline is network-bound, so throughput is set by how many requests are in
flight. Pushing that number up without pacing invites HTTP 429, and a 429 costs
a full round trip plus backoff - usually more expensive than the request that
was throttled.

This limiter is deliberately simple and dependency-free:

* a semaphore-free sliding window caps requests per minute
* every 429 lowers the ceiling and adds a cool-off, so the caller adapts
  instead of repeatedly discovering the limit
* success slowly raises the ceiling back toward the configured maximum
* waiting is interruptible, so "stop" stays responsive even mid-backoff

It is shared across threads, which is what makes it useful: the translation
engine runs several workers against one provider account.
"""
from __future__ import annotations

import threading
import time
from collections import deque


class AdaptiveRateLimiter:
    """Pace requests and shrink the window when the provider pushes back."""

    def __init__(
        self,
        max_requests_per_minute: int = 60,
        min_requests_per_minute: int = 4,
        cooloff_seconds: float = 5.0,
    ) -> None:
        self._max_rpm = max(1, int(max_requests_per_minute))
        self._floor_rpm = max(1, min(int(min_requests_per_minute), self._max_rpm))
        self._current_rpm = self._max_rpm
        self._cooloff = cooloff_seconds
        self._stamps: deque[float] = deque()
        self._blocked_until = 0.0
        self._last_sent = 0.0
        self._lock = threading.Lock()

    # -- introspection -----------------------------------------------------

    @property
    def current_rpm(self) -> int:
        with self._lock:
            return self._current_rpm

    def stats(self) -> dict[str, float]:
        with self._lock:
            return {
                "current_rpm": self._current_rpm,
                "max_rpm": self._max_rpm,
                "in_flight_window": len(self._stamps),
                "cooldown_remaining": max(0.0, self._blocked_until - time.monotonic()),
            }

    # -- pacing ------------------------------------------------------------

    def acquire(self, stop_event=None) -> bool:
        """Block until a request slot is free. Returns False if stopped.

        Both a sliding-window cap and a minimum gap are enforced. The window
        alone would still permit a burst that trips provider limits, because
        ten requests fired in one second is a hundred per ten seconds even
        though the rolling average looks fine.
        """
        while True:
            with self._lock:
                now = time.monotonic()
                # Drop stamps that have aged out of the window.
                while self._stamps and now - self._stamps[0] >= 60.0:
                    self._stamps.popleft()

                min_gap = 60.0 / max(1, self._current_rpm)
                gap_remaining = (
                    self._last_sent + min_gap - now if self._last_sent else 0.0
                )

                if self._blocked_until > now:
                    wait_for = self._blocked_until - now
                elif len(self._stamps) >= self._current_rpm:
                    wait_for = max(0.05, 60.0 - (now - self._stamps[0]))
                elif gap_remaining > 0:
                    wait_for = gap_remaining
                else:
                    self._stamps.append(now)
                    self._last_sent = now
                    return True

            if stop_event is not None and stop_event.is_set():
                return False
            # Sleep in slices so a stop request is noticed promptly.
            deadline = time.monotonic() + min(wait_for, 0.25)
            while time.monotonic() < deadline:
                if stop_event is not None and stop_event.is_set():
                    return False
                time.sleep(0.01)

    # -- feedback ----------------------------------------------------------

    def report_success(self) -> None:
        """Nudge the ceiling back up after sustained good behaviour."""
        with self._lock:
            if self._current_rpm < self._max_rpm:
                self._current_rpm = min(self._max_rpm, self._current_rpm + 1)

    def report_throttled(self, retry_after: float | None = None) -> None:
        """Halve the ceiling and hold everything back briefly.

        ``retry_after`` is the value of the provider's ``Retry-After`` header
        when present; it is authoritative, so it wins over the local guess.
        """
        with self._lock:
            self._current_rpm = max(self._floor_rpm, self._current_rpm // 2)
            pause = float(retry_after) if retry_after else self._cooloff
            self._blocked_until = max(
                self._blocked_until,
                time.monotonic() + max(0.0, pause),
            )

    def reset(self) -> None:
        with self._lock:
            self._current_rpm = self._max_rpm
            self._stamps.clear()
            self._blocked_until = 0.0
            self._last_sent = 0.0

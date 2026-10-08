"""Sliding-window counter rate limiter.

Windows are aligned to multiples of ``window_seconds`` (window ``n`` covers
``[n * W, (n + 1) * W)``). Each key stores a fixed-size record: the current
window, the count in it, the count in the window before it, and the time of its
last allowed request. The effective request count weights the previous window
by the share of it that still overlaps the sliding window.

Example (limit 3, window 10 s):

    >>> limiter = SlidingWindowLimiter(3, 10, clock=lambda: 0.0)
    >>> limiter.check("a").remaining
    2
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

__all__ = ["SlidingWindowLimiter", "CheckResult", "KeyState"]

logger = logging.getLogger(__name__)

_MAX_NUDGES = 256


def _default_clock() -> float:
    """Read ``time.monotonic`` at call time so it can be patched in tests."""
    return time.monotonic()


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one ``check`` call.

    Example: ``CheckResult(allowed=True, remaining=2, retry_after=0.0)``.
    ``retry_after`` is fractional seconds and is 0.0 when the request is allowed.
    """

    allowed: bool
    remaining: int
    retry_after: float


@dataclass(frozen=True)
class KeyState:
    """Read-only snapshot of one key's stored record.

    Example: ``KeyState(10.0, current=1, previous=3, last_activity=15.0)``.
    """

    window_start: float
    current: int
    previous: int
    last_activity: float


class _Entry:
    """Mutable per-key record (fixed size)."""

    __slots__ = ("window", "current", "previous", "last_activity")

    def __init__(
        self, window: int, current: int, previous: int, last_activity: float
    ) -> None:
        self.window = window
        self.current = current
        self.previous = previous
        self.last_activity = last_activity


def _validate_positive(name: str, value: object) -> None:
    try:
        ok = value > 0  # type: ignore[operator]  # `not (v > 0)` also rejects NaN
    except TypeError:
        ok = False
    if not ok:
        raise ValueError(f"{name} must be positive, got {value!r}")


class SlidingWindowLimiter:
    """In-memory sliding-window counter limiter, safe to share across threads.

    Args:
        limit: Maximum requests per sliding window (positive).
        window_seconds: Window length in seconds (positive).
        clock: Zero-argument callable returning seconds as a float. Defaults to
            ``time.monotonic``. It must never go backwards.

    Example:
        >>> t = [0.0]
        >>> limiter = SlidingWindowLimiter(3, 10, clock=lambda: t[0])
        >>> [limiter.check("a").allowed for _ in range(4)]
        [True, True, True, False]

    Note: ``len(limiter)`` is the tracked key count, so an empty limiter is falsy.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        _validate_positive("limit", limit)
        _validate_positive("window_seconds", window_seconds)
        self._limit = limit
        self._window = float(window_seconds)
        self._clock: Callable[[], float] = (
            clock if clock is not None else _default_clock
        )
        self._entries: Dict[str, _Entry] = {}
        self._lock = threading.Lock()
        self._bg_lock = threading.Lock()
        self._bg_thread: Optional[threading.Thread] = None
        self._bg_stop: Optional[threading.Event] = None

    # ------------------------------------------------------------------ math

    def _effective(self, window: int, current: int, previous: int, x: float) -> float:
        """Effective count at time ``x`` from raw state, without mutating it."""
        w = self._window
        gap = math.floor(x / w) - window
        if gap <= 0:
            frac = min(max((x - window * w) / w, 0.0), 1.0)
            return current + previous * (1.0 - frac)
        if gap == 1:
            frac = min(max((x - (window + 1) * w) / w, 0.0), 1.0)
            return current * (1.0 - frac)
        return 0.0

    def _effective_entry(self, entry: Optional[_Entry], x: float) -> float:
        if entry is None:
            return 0.0
        return self._effective(entry.window, entry.current, entry.previous, x)

    def _is_idle(self, entry: _Entry, now: float) -> bool:
        return now - entry.last_activity > 2 * self._window

    def _retry_after(self, entry: _Entry, now: float) -> float:
        """Smallest wait (seconds) after which a request would be allowed."""
        w = self._window
        limit = self._limit
        # Roll a copy of the state to the current window.
        cur_win = math.floor(now / w)
        gap = cur_win - entry.window
        if gap <= 0:
            win, cur, prev = entry.window, entry.current, entry.previous
        elif gap == 1:
            win, cur, prev = cur_win, 0, entry.current
        else:
            win, cur, prev = cur_win, 0, 0
        if cur >= limit:
            # Only the next window can bring the count below the limit.
            win, cur, prev = win + 1, 0, cur
        if prev > 0:
            target = win * w + w * (1.0 - (limit - cur) / prev)
        else:
            target = (win + 1) * w
        # Nudge upward until the real function says "allowed" strictly after now.
        t = max(target, math.nextafter(now, math.inf))
        for _ in range(_MAX_NUDGES):
            if self._effective_entry(entry, t) < limit:
                break
            t = math.nextafter(t, math.inf)
        retry = t - now
        for _ in range(_MAX_NUDGES):
            if retry > 0.0 and self._effective_entry(entry, now + retry) < limit:
                break
            retry = math.nextafter(max(retry, 0.0), math.inf)
        return retry

    # ------------------------------------------------------------ operations

    def check(self, key: str) -> CheckResult:
        """Record a request for ``key`` if allowed and report the outcome.

        Example (limit 3): a third request returns
        ``CheckResult(allowed=True, remaining=0, retry_after=0.0)`` and a fourth
        returns ``allowed=False`` with a positive ``retry_after``. A refused
        request changes no state.
        """
        with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry is not None and self._is_idle(entry, now):
                del self._entries[key]  # lazy eviction
                entry = None
            effective = self._effective_entry(entry, now)
            if effective < self._limit:
                cur_win = math.floor(now / self._window)
                if entry is None:
                    entry = _Entry(cur_win, 0, 0, now)
                    self._entries[key] = entry
                else:
                    gap = cur_win - entry.window
                    if gap == 1:
                        entry.previous, entry.current = entry.current, 0
                        entry.window = cur_win
                    elif gap >= 2:
                        entry.previous, entry.current = 0, 0
                        entry.window = cur_win
                entry.current += 1
                entry.last_activity = now
                remaining = max(0, math.floor(self._limit - (effective + 1.0)))
                return CheckResult(True, int(remaining), 0.0)
            assert entry is not None  # effective > 0 implies a stored entry
            return CheckResult(False, 0, float(self._retry_after(entry, now)))

    def reset(self, key: str) -> None:
        """Forget ``key``'s history; unknown keys are ignored."""
        with self._lock:
            self._entries.pop(key, None)

    def cleanup(self) -> None:
        """Remove every key idle for strictly more than two windows."""
        with self._lock:
            now = self._clock()
            idle = [k for k, e in self._entries.items() if self._is_idle(e, now)]
            for k in idle:
                del self._entries[k]

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def key_state(self, key: str) -> Optional[KeyState]:
        """Return a read-only snapshot of ``key``'s stored record, or ``None``."""
        with self._lock:
            e = self._entries.get(key)
            if e is None:
                return None
            return KeyState(
                e.window * self._window, e.current, e.previous, e.last_activity
            )

    # ----------------------------------------------------- background cleanup

    def start_background_cleanup(self, interval: float) -> None:
        """Run ``cleanup()`` every ``interval`` real seconds on a daemon thread.

        No-op if already running. Raises ``ValueError`` if ``interval`` is not
        positive. Example: ``limiter.start_background_cleanup(60)``.
        """
        _validate_positive("interval", interval)
        with self._bg_lock:
            if self._bg_thread is not None and self._bg_thread.is_alive():
                return
            stop = threading.Event()
            thread = threading.Thread(
                target=self._background_loop,
                args=(stop, interval),
                name="sliding-window-limiter-cleanup",
                daemon=True,
            )
            self._bg_stop = stop
            self._bg_thread = thread
            thread.start()

    def stop_background_cleanup(self) -> None:
        """Stop background cleanup and wait for the thread; safe to call twice."""
        with self._bg_lock:
            thread, stop = self._bg_thread, self._bg_stop
            if thread is None or stop is None:
                return
            stop.set()
            if thread is not threading.current_thread():
                thread.join()
            self._bg_thread = None
            self._bg_stop = None

    def _background_loop(self, stop: threading.Event, interval: float) -> None:
        while not stop.wait(interval):
            try:
                self.cleanup()
            except Exception:  # noqa: BLE001 - keep the loop alive, never silent
                logger.exception("background cleanup failed; will retry")

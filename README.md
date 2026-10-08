# sliding-window-limiter

In-memory sliding-window counter rate limiter. Python 3.10+, standard library only.

## Install and test

```
python3 -m pip install -e ".[dev]"
python3 -m pytest tests/test_limiter.py
```

## Usage

```python
from sliding_window_limiter import SlidingWindowLimiter

limiter = SlidingWindowLimiter(limit=3, window_seconds=10)

result = limiter.check("client-1")
if result.allowed:
    print(f"ok, {result.remaining} left")
else:
    print(f"retry in {result.retry_after:.3f}s")

limiter.reset("client-1")  # forget one client
limiter.cleanup()  # drop clients idle for more than 2 windows
limiter.start_background_cleanup(60)  # optional daemon thread, every 60 s
limiter.stop_background_cleanup()
```

`check` returns a frozen `CheckResult(allowed, remaining, retry_after)`.
`len(limiter)` is the number of tracked keys and `limiter.key_state(key)` returns a
read-only `KeyState` (or `None`).

## Behavior notes

- Windows are aligned to multiples of `window_seconds`. The previous window's count
  is weighted by the share of it still inside the sliding window. It is carried only
  when the current window directly follows the one of the last activity.
- `remaining` is computed after the request is recorded and rounded down, never negative.
- `retry_after` is fractional seconds: waiting exactly that long is enough. Round up
  yourself for an HTTP `Retry-After` header. Refused requests change no state.
- A key is idle when its last allowed request is strictly more than two windows old.
  Idle keys are dropped lazily by `check` and by `cleanup()`.
- Per-key state is fixed size: window, current count, previous count, last activity.
- All state is guarded by one lock, so the limiter is safe to share across threads.
- Pass `clock=` (a zero-argument callable returning seconds) for deterministic tests.
  The default is `time.monotonic`. The clock must not go backwards.

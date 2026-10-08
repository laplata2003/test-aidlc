# Unit Test Instructions: Sliding-Window Rate Limiter

## Framework Setup

- Language and runner: Python 3.10 or later with pytest 7 or later.
- Install the test dependency once: `python3 -m pip install pytest` (or `python3 -m pip install -e ".[dev]"` after Step 1 creates `pyproject.toml`).
- pytest is configured in `pyproject.toml` with `pythonpath = ["src"]` and `testpaths = ["tests"]`, so no package install is needed to run the tests.

## Run This Work's Tests

The exact command, scoped to this work's single test file:

```
python3 -m pytest tests/test_limiter.py
```

Run from the workspace root. There is no wider suite yet; the command above is the whole suite for this change.

## Expected Coverage

- One test (or one parametrized test) per acceptance-criteria group in `stories.md`, about 35 test functions in total.
- Every functional requirement (FR1 to FR5) and non-functional requirement (NFR1 to NFR4) is exercised by at least one test.
- No line-coverage floor applies to the express scope. If `pytest-cov` is installed, `python3 -m pytest tests/test_limiter.py --cov=sliding_window_limiter` is a useful extra, not a gate.

## Mocking and Stubbing Guidance

- **Time:** every time-dependent test uses the `FakeClock` fixture from `tests/conftest.py` and passes it to the limiter. Tests advance it with `advance(seconds)` or `set(t)`. They never call `time.sleep`.
- **No real-clock leakage:** tests for US1.7 replace `time.monotonic`, `time.time`, and `time.sleep` with functions that raise, using pytest's `monkeypatch`, to prove the limiter does not read them when a fake clock is supplied.
- **Default clock:** one test replaces `time.monotonic` with a controllable function and builds a limiter without a clock.
- **Threads:** thread tests use a `threading.Barrier` to release workers together, a frozen fake clock (a constant is thread-safe), and `join(timeout=...)` on every thread.
- **Background cleanup:** one test starts cleanup with an interval of 0.01 seconds and waits on a `threading.Event` set from a wrapper around `cleanup()`, with a 5 second timeout that only guards against a hang. This is the one test that uses a short real interval.
- **Standard-library-only check:** a test parses the source files under `src/` with `ast` and compares import roots with `sys.stdlib_module_names`.

## Test Data Management

- Constants used across tests: `limit = 3`, `window_seconds = 10`.
- Times are chosen as exact binary fractions where a fractional elapsed share is needed (7.5 and 2.5 seconds into a 10 second window), so effective counts are exact. Where a value is not exact (the 1.667 second `retry_after`), tests compare with `pytest.approx`.
- No files, databases, or network are used, and no cleanup between tests is needed.

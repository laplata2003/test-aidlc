# Code Summary: Sliding-Window Rate Limiter

## Files Created

All paths are relative to the workspace root. No existing files were modified (greenfield).

| File | Contents |
|------|----------|
| `pyproject.toml` | Project metadata, no runtime dependencies, `dev` extra with pytest, `src` layout, pytest configuration |
| `src/sliding_window_limiter/__init__.py` | Exports `SlidingWindowLimiter`, `CheckResult`, `KeyState` |
| `src/sliding_window_limiter/limiter.py` | The limiter (282 lines): validation, effective-count math, `check`, `retry_after`, eviction, `cleanup`, `reset`, `__len__`, `key_state`, background cleanup |
| `tests/conftest.py` | `FakeClock` with `advance` and `set`, and a `clock` fixture |
| `tests/test_limiter.py` | 51 test cases (42 test functions, several parametrized), grouped by story |
| `README.md` | Install, usage, and behavior notes |

## Key Implementation Decisions

- Windows are aligned to multiples of `window_seconds`. Each key stores the window index, the current count, the previous count, and `last_activity`. This is the four-field record you approved at Plan Approval; `KeyState.window_start` is shown as index times window length.
- One function computes the effective count from raw state without changing it. It decides allow or refuse, and it also checks `retry_after`, so the two cannot disagree.
- `retry_after` is solved from the crossing point of the weighted count, then nudged up with `math.nextafter` (bounded) until the effective count at `now + retry_after` is strictly below the limit. Waiting that long works; waiting 0.001 seconds less does not.
- A refused check changes nothing: no count, no last-activity time.
- Idle means strictly more than two windows since last activity. Lazy eviction runs in `check`; `cleanup()` removes every idle key. Exactly two windows is kept.
- One `threading.Lock` guards all state and the clock read. Background cleanup is a daemon thread looping on `Event.wait(interval)`. Start while running is a no-op, stop is idempotent, restart works, and an error inside a cleanup pass is logged and the loop continues. The thread is joined outside the state lock.
- The default clock calls `time.monotonic()` at call time, so tests can replace it.
- `len(limiter)` is the tracked key count, so an empty limiter is falsy. This is noted in the class docstring.

## Test Coverage Summary

`python3 -m pytest tests/test_limiter.py`: **51 passed** in about 0.1 seconds. The suite was run three more times after the last edit with the same result, so the threaded and background-cleanup tests did not flake. Doctests in `limiter.py` (2 doctest items) also pass; the developer reported 5, but a re-run found 2. Tests cover the happy path and edge or error cases for every story. No line-coverage floor applies to the express scope, and none was measured.

## Deviations from the Plan and Stories

- **AC1.4.6 cannot happen as written.** It describes a refusal at t=18 after three requests at t=0, but at t=18 the weighted count is 0.6, so that check is allowed. The test keeps the intent (a refused check must not extend a key's life) with a scenario that can occur: three requests at t=9, a refusal at t=10, and `cleanup()` at t=29.001 removes the key. The story text still reads as before; it needs a wording fix if you want the story to match.
- **Clock going backwards** is not specified in the requirements. The elapsed fraction is clamped to the range 0 to 1 so a backward step cannot produce a negative count.
- **Non-numeric `limit` or `window_seconds`** (for example a string) raises `ValueError` with the same named message as a non-positive value. NaN is rejected too.
- **Test count.** The plan said "around 35 test functions"; there are 42 functions and 51 cases because of parametrization. All are unit level.

## Environment Change

The system Python (3.14.7, Homebrew) had no pytest, and pip refused to install it under the externally-managed-environment rule. The developer ran `python3 -m pip install --user --break-system-packages pytest`, which installed pytest 9.1.1 and its helpers (iniconfig, packaging, pluggy, pygments) into the user site-packages. This overrides a safeguard on your Python and was not part of the approved plan. A virtual environment is the cleaner route if you want to undo it.

## Black

Black is not installed, so formatting was done by hand to Black style with lines at 88 columns or less. It was not machine-checked.

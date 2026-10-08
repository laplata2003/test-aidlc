# Test Results: Sliding-Window Rate Limiter

Run date: 2026-10-08. Python 3.14.7, pytest 9.1.1, macOS. Commands run from the workspace root.

## Build Status

**Success.** `pyproject.toml` parses (`sliding-window-limiter`, `requires-python >=3.10`, no runtime dependencies), all four Python files parse, and the package imports and exports `SlidingWindowLimiter`, `CheckResult`, `KeyState`. See `build-instructions.md`.

## Unit Tests

Command (the only distinct command in `unit-test-instructions.md`): `python3 -m pytest tests/test_limiter.py`

| Total | Passed | Failed | Skipped |
|-------|--------|--------|---------|
| 51 | 51 | 0 | 0 |

Doctests (`python3 -m pytest --doctest-modules src`): 2 passed. Integration, performance, and other test types: none generated, as the Minimal strategy specifies.

Repeat runs, to look for flakiness in the threaded and background tests: 8 further full runs (5 before and 3 after a test was tightened), all 51 passed.

## Failure Details

None.

## Coverage Report

Not measured. `pytest-cov` is not installed, and the express scope sets no coverage floor. Every acceptance criterion in `stories.md` has at least one test.

## Test Strength Check (mutation spot-check)

To see whether the tests would notice a broken limiter, eight deliberate bugs were applied one at a time to a scratch copy (the real source was not touched) and the suite was run against each.

| Bug introduced | Result |
|----------------|--------|
| Allow when the count equals the limit (`<` to `<=`) | Caught |
| Evict a key at exactly two idle windows (`>` to `>=`) | Caught |
| Previous-window weight inverted | Caught |
| `remaining` off by one | Caught |
| `reset()` does nothing | Caught |
| `retry_after` not nudged up to a safe value | Caught |
| `stop_background_cleanup()` does not wait for the thread | **Missed at first.** The stop test joined the thread itself, so it could not tell. The test now checks the thread is finished the moment `stop` returns, and catches this bug. |
| Skip the lazy eviction inside `check` | **Not detectable, and not a test gap.** A stale key is rolled forward by two or more windows to the same state a fresh key has, so the lazy eviction changes no result and no stored value. The code is kept because FR5.2 asks for it. |

## Story Criterion That Cannot Occur As Written

AC1.4.6 (in `stories.md`) says a key last active at t=0 is refused at t=18. At t=18 the weighted count is 0.6, so that check is allowed. The test keeps the intent (a refused check must not extend a key's life) with a scenario that can occur: three requests at t=9, a refusal at t=10, and `cleanup()` at t=29.001 removes the key. The story text was not changed.

## Counts to Correct

Earlier messages and the approved plan said the stories carry 49 acceptance criteria. The correct number is 43. The plan is fingerprinted, so it was left as approved.

## Target Verification Matrix

See `build-and-test-summary.md`.

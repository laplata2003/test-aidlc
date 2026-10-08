# Code Generation Plan: Sliding-Window Rate Limiter

Scope: express (zero Unit; one implementation pass). Test strategy: Minimal. Methodology: test-after. Project type: greenfield, Python 3.10+, pytest.

## Inputs

- Requirements: `inception/requirements-analysis/requirements.md` (FR1 to FR5, NFR1 to NFR4)
- Stories: `inception/user-stories/stories.md` (9 stories, acceptance criteria AC1.1.1 to AC2.2.6)
- No unit-of-work, design, or contract artifacts exist: the express plan skips them, so this plan is scoped from the requirements and stories.

## Target Layout (workspace root)

```
pyproject.toml                          project metadata, pytest configuration
README.md                               short usage guide
src/sliding_window_limiter/__init__.py  public exports
src/sliding_window_limiter/limiter.py   the whole implementation
tests/conftest.py                       FakeClock fixture
tests/test_limiter.py                   unit tests, grouped by story
```

## Public Interface (decided here; the requirements left names to this stage)

- `SlidingWindowLimiter(limit, window_seconds, clock=None)`
- `check(key) -> CheckResult` (frozen dataclass: `allowed: bool`, `remaining: int`, `retry_after: float`)
- `reset(key) -> None`
- `cleanup() -> None`
- `len(limiter)` gives the tracked key count; `key_state(key)` gives a read-only `KeyState` or `None`
- `start_background_cleanup(interval)` and `stop_background_cleanup()`

## Design Decisions

1. **Windows** are aligned to multiples of `window_seconds` (window index = floor(t / window_seconds)).
2. **Effective count** at time t for a key: same window as the stored one: `current + previous * (1 - f)`; the next window: `stored_current * (1 - f)`; two or more windows later: 0. `f` is the elapsed fraction of the current window.
3. **Check**: if the effective count is below `limit`, record the request and return `remaining = max(0, floor(limit - (effective + 1)))`. Otherwise refuse without changing any state.
4. **`retry_after`** is solved from the stored state in closed form (same-window crossing, otherwise the next-window crossing), then nudged up one float step at a time until the real effective-count function says "allowed" at `now + retry_after`. Waiting exactly `retry_after` works; waiting 0.001 s less does not.
5. **Eviction**: a key is idle when `now - last_activity` is strictly more than `2 * window_seconds`. Lazy eviction runs inside `check`; `cleanup()` removes every idle key. Refused checks do not update `last_activity`.
6. **Locking**: one `threading.Lock` guards all state; the clock is read inside it. Background cleanup is a daemon thread driven by a `threading.Event` (`Event.wait(interval)` as the timer) with its own lifecycle lock. Errors raised inside the background loop are logged with `logging` and the loop continues.
7. **Default clock** is a small function that calls `time.monotonic()` at call time, so tests can replace it.

## Decision to Confirm at Approval

**Per-key state has four fields, not three.** FR2.2 and AC1.1.5 say the per-key record holds only the window start, the current count, and the previous count, but FR5.2 and AC1.4.4 define idleness by *last activity*, which three fields cannot give exactly (activity at t=9 and at t=0 both look like window start 0). This plan stores a fourth field, `last_activity`, so eviction follows FR5.2 exactly. The record is still fixed-size, so NFR1 and NFR2 hold. AC1.1.5's test will therefore assert a fixed four-field record. The alternative is to evict by window start only, which keeps three fields but evicts some keys up to one window earlier than FR5.2 says (with no visible change in results). Choose "Request Changes" and say so if you prefer that.

## Implementation Steps

- [x] **Step 1: Project structure and production configuration skeleton.** Create `pyproject.toml` (name `sliding-window-limiter`, `requires-python >= 3.10`, no runtime dependencies, `pytest` in a `dev` extra, `pythonpath = ["src"]` and `testpaths = ["tests"]` for pytest), the `src/sliding_window_limiter/` package, and the `tests/` directory. Traces: NFR4.
- [x] **Step 2: Bootstrap the minimal test runner/configuration and record the exact unit-scoped command.** Add `tests/conftest.py` with a `FakeClock` fixture (callable returning a float; `advance(seconds)` and `set(t)`). Confirm the runner starts with `python3 -m pytest tests/test_limiter.py` and record it in `unit-test-instructions.md`. Traces: FR1.2, FR5.1.
- [x] **Step 3: Business logic: implement** `src/sliding_window_limiter/limiter.py`, in this order within the file:
  - [x] 3a. `CheckResult` and `KeyState` frozen dataclasses; constructor validation with named `ValueError` messages (US1.6; FR1, FR3.1).
  - [x] 3b. Window and effective-count helpers; `check` with recording, `remaining`, refusals, and `retry_after` (US1.1, US1.2, US1.3; FR2, FR3).
  - [x] 3c. Last-activity tracking, lazy eviction, `cleanup()`, `reset()`, `__len__`, `key_state()` (US1.4, US1.5; FR4, FR5.2, FR5.3, NFR2).
  - [x] 3d. Single lock around state; background cleanup `start`/`stop` with the lifecycle rules in US2.2 (US2.1, US2.2; FR5.4, FR5.5).
  - [x] 3e. `__init__.py` exports `SlidingWindowLimiter`, `CheckResult`, `KeyState`.
- [x] **Step 4: Business logic: write and run its tests** in `tests/test_limiter.py`, one group per story, after the implementation is complete:
  - [x] 4a. US1.6 and US1.7: configuration errors (limit and window cases), default and injected clock, no use of `time.monotonic`/`time.time`/`time.sleep` with a fake clock, determinism, stdlib-only imports.
  - [x] 4b. US1.1: first request, last allowed request, key independence, result types and immutability, fixed-size state after 10,000 requests.
  - [x] 4c. US1.2: refusal at the limit, repeated refusal, `retry_after` for the t=4 case, the t=10.0 boundary, and the t=15 worked example.
  - [x] 4d. US1.3: the 75%, 50%, 25% and 10% elapsed examples, rollover at t=10.0, and the window-gap cases (t=15, t=25, t=0.1 then t=19.9).
  - [x] 4e. US1.4 and US1.5: lazy eviction, `cleanup()` (all idle, mixed, boundary at exactly 2 windows, empty, refused check not extending life), `reset()` (known, other key, unknown key, key count).
  - [x] 4f. US2.1 and US2.2: threaded checks behind a barrier with joins and timeouts, concurrent `check`/`reset`/`cleanup`, concurrent `cleanup` never removing active keys, background cleanup never started, runs and cleans, stops cleanly as a daemon, double stop and double start, restart, bad interval.
  - [x] 4g. Run the suite with the command from Step 2; all tests must pass.
- [x] **Step 5: API / endpoint, repository / data access, frontend behavior, database.** Not applicable: this is an in-process library with no network, storage, or UI. Omitted on purpose.
- [x] **Step 6: Environment/build configuration.** Finish `pyproject.toml` (package discovery for `src/`), and confirm the package imports from a clean interpreter with only the standard library.
- [x] **Step 7: Documentation and traceability.** Add docstrings with example values to the public classes and methods, write `README.md` (install, usage, behavior notes), write `code-summary.md`, `source-manifest.json`, and `traceability.json` under the code-generation record directory.

## Story to Step Traceability

| Story | Implemented in | Tested in |
|-------|----------------|-----------|
| US1.1 Allow requests under the limit | Step 3a, 3b | Step 4b |
| US1.2 Block requests over the limit | Step 3b | Step 4c |
| US1.3 Recover smoothly as the window slides | Step 3b | Step 4d |
| US1.4 Clean up idle clients | Step 3c | Step 4e |
| US1.5 Reset one client | Step 3c | Step 4e |
| US1.6 Configure the limiter | Step 1, 3a | Step 4a |
| US1.7 Control time in tests | Step 2, 3b | Step 4a |
| US2.1 Safe use from several threads | Step 3d | Step 4f |
| US2.2 Optional periodic background cleanup | Step 3d | Step 4f |

## Test Volume Note

The Minimal strategy asks for one test per requirement and a happy-path test per component. The approved stories carry 49 acceptance criteria, so this plan writes one test per acceptance criterion group (around 35 test functions, several parametrized). That is above the usual 5 to 15 for Minimal, because the stories you added to the plan make each behavior its own check. It stays the narrowest effective level: unit tests only, no integration or end-to-end tests.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "org",
  "ordering": "implement each applicable testable layer, then write and run that layer's tests.",
  "scope": "express",
  "test_strategy": "minimal",
  "project_type": "greenfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    }
  ],
  "obligations": {
    "strategy": "minimal",
    "strategy_volume": [
      "One verifiable test per requirement at the narrowest effective level.",
      "At least one happy-path unit test per component.",
      "Unit tests are the default; a bugfix/security scope floor may require an integration or E2E regression when that is the narrowest level that reproduces the defect."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "test-after",
    "runner_step": "Bootstrap the minimal test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Bootstrap the minimal test runner/configuration and record the exact unit-scoped command.",
      "Data model / database behavior - implement.",
      "Data model / database behavior - write and run its tests after implementation.",
      "Repository / data access - implement.",
      "Repository / data access - write and run its tests after implementation.",
      "Business logic - implement.",
      "Business logic - write and run its tests after implementation.",
      "API / endpoint - implement.",
      "API / endpoint - write and run its tests after implementation.",
      "Frontend behavior - implement.",
      "Frontend behavior - write and run its tests after implementation.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:6cb23162168334768ff8f29699669845616670119c9eb58bf9bb05af6fefd3de",
  "contract_sha256": "sha256:283a836cf0757ed2efa4b5dd3135f3986eb59880b3017f4ba87a685cfebedfdb"
}
```

# Requirements: In-Memory Sliding-Window Rate Limiter

Depth: Minimal. Scope: express. Project type: greenfield.

## Sources

- [desc] Initial description: Create an in-memory rate-limiter with sliding-window logic and unit tests
- [scope] Workflow-selected scope: express
- [Q1] Language and test framework: Python with pytest
- [Q2] Algorithm: sliding window counter (weighted blend of the current and previous fixed windows)
- [Q3] Interface: `check(key)` returning `allowed`, `remaining`, `retryAfter`, plus `reset(key)`
- [Q4] Time and cleanup: injectable clock, lazy eviction on access, periodic background cleanup that can also be called on demand

## Intent Analysis

The user wants a reusable, in-process rate limiter that decides whether a request from a given client key is allowed within a rolling time window, backed by unit tests. The goal is correct, testable limiting behavior with bounded memory, not a networked or distributed service.

## Functional Requirements

### FR1: Limiter configuration
- FR1.1: The limiter shall be constructed with a maximum request count (`limit`) and a window length in seconds (`window_seconds`). [assumption] Both are positive numbers; construction with a non-positive value shall raise a `ValueError`.
- FR1.2: The limiter shall accept an optional clock, a zero-argument callable returning the current time in seconds as a float. When none is given, it shall use a monotonic system clock. [Q4]

### FR2: Sliding-window counting
- FR2.1: The limiter shall use the sliding window counter algorithm: for a key, the effective count at time `t` is `current_window_count + previous_window_count * (1 - elapsed_fraction)`, where `elapsed_fraction` is the share of the current fixed window already elapsed. [Q2]
- FR2.2: State per key shall be constant in size, holding only the current window start, the current window count, and the previous window count. [Q2]
- FR2.3: When more than one full window has passed since a key's last activity, the previous window count shall be treated as zero.

### FR3: Check operation
- FR3.1: `check(key)` shall return a result with `allowed` (bool), `remaining` (int), and `retry_after` (float seconds). [Q3]
- FR3.2: When the effective count is below `limit`, `check` shall record the request, return `allowed=True`, and set `remaining` to `limit` minus the recorded effective count, rounded down and not below zero. `retry_after` shall be `0.0`.
- FR3.3: When the effective count is at or above `limit`, `check` shall not record the request, return `allowed=False`, set `remaining` to `0`, and set `retry_after` to the seconds until a request would next be allowed, greater than `0.0`.
- FR3.4: Keys shall be tracked independently; activity on one key shall not change another key's result.

### FR4: Reset operation
- FR4.1: `reset(key)` shall discard all stored state for that key so the next `check(key)` behaves as the first request. [Q3]
- FR4.2: `reset` on an unknown key shall do nothing and shall not raise.

### FR5: Time handling and eviction
- FR5.1: All time reads shall go through the injected clock so tests can control time deterministically. [Q4]
- FR5.2: Lazy eviction: on access to a key whose last activity is more than two full windows old, the limiter shall drop that key's old state and treat the request as the first request. [Q4]
- FR5.3: A `cleanup()` method shall remove every key whose last activity is more than two full windows old, and shall be callable on demand. [Q4]
- FR5.4: The limiter shall provide an optional periodic background cleanup that calls `cleanup()` at a configurable interval, with a way to start and stop it. It shall not start unless requested. [Q4]
- FR5.5: Concurrent access from multiple threads shall not corrupt state; `check`, `reset`, and `cleanup` shall be safe to call together. [assumption]

## Non-Functional Requirements

- NFR1: Each `check` call shall run in constant time with respect to the number of past requests for that key.
- NFR2: Memory use shall be proportional to the number of active keys only, with a fixed small state per key. After `cleanup()` at a time more than two windows past all activity, the tracked key count shall be `0`.
- NFR3: Behavior shall be deterministic for a given sequence of keys and clock values.
- NFR4: The library shall use only the Python standard library at runtime; pytest is the only test dependency.

## Testing Requirements

Per the express scope, requirement-driven unit tests with one test per requirement as a floor, plus a happy path for each component, written in pytest. Tests shall use the injected clock and shall not sleep.

- T1: One test per functional requirement FR1.1 through FR5.5, including the error cases for FR1.1 and the unknown-key case for FR4.2.
- T2: A boundary test where a request lands exactly at the limit, and one at a window rollover.
- T3: A test for the background cleanup that starts and stops it and confirms it can be stopped cleanly. [assumption] This may use a short real interval; all other time-dependent tests use the fake clock.

## Constraints

- Python with pytest, as chosen in Q1.
- In-memory and single-process only; no persistence and no network.

## Assumptions

- [assumption] `limit` and `window_seconds` are set per limiter instance, not per key.
- [assumption] The result type is a small immutable object with the three named fields.
- [assumption] Python 3.10 or later; layout is a single package with a `tests/` directory. Exact names are left to Code Generation.
- [assumption] Invalid input beyond FR1.1, such as a non-hashable key, is not specially handled and fails as normal Python would.

## Out of Scope

- Distributed or shared-state limiting, persistence, and any web-framework middleware.
- Per-key custom limits, burst or token-bucket modes, and the sliding window log algorithm.
- Async-specific APIs.

## Open Questions

None blocking. The assumptions above are carried forward and can be changed at this stage's approval gate.

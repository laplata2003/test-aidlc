**Collaborator:** aidlc-quality-agent

## Contribution

Scope of review: testability of every acceptance criterion (AC) in `stories.md` against `requirements.md` (FR1 to FR5, NFR1 to NFR4) and T1 to T3. Examples below use `limit = 3`, `window_seconds = 10`, a fake clock, and windows aligned to multiples of `window_seconds` (see finding F2).

### A. Requirement coverage matrix

| Requirement | Covered by | Verdict |
|---|---|---|
| FR1.1 | AC1.1.4 | Covered. Split into parametrized cases (limit 0, limit negative, window 0, window negative). |
| FR1.2 | AC1.3.1 (injected clock only) | PARTIAL. The default monotonic clock when no clock is given has no AC. See F6. |
| FR2.1 | AC1.3.2, AC1.3.3 | Covered, but AC1.3.3 is vague. See F4. |
| FR2.2 | AC1.1.5 | Covered, but needs an observable. See F7. |
| FR2.3 | AC1.3.4 | Covered. Add the exact-one-window boundary. See F5. |
| FR3.1 | AC1.1.1, AC1.2.1 | PARTIAL. No AC for the result type (field names, `remaining` is an `int`, `retry_after` is a `float`, immutable). See F6. |
| FR3.2 | AC1.1.1, AC1.1.2, AC1.3.2 | PARTIAL. "Rounded down" and "not below zero" have no fractional example. See F4. |
| FR3.3 | AC1.2.1 to AC1.2.4 | Covered, but AC1.2.3 contradicts the strict boundary of AC1.2.4. See F1. |
| FR3.4 | AC1.1.3, AC1.5.2 | Covered. |
| FR4.1, FR4.2 | AC1.5.1, AC1.5.3 | Covered. |
| FR5.1 | AC1.3.1, AC1.4.4 | Covered, but "reads only from that function" needs a verifiable form. See F6. |
| FR5.2 | AC1.4.1 | Covered. Boundary missing. See F5. |
| FR5.3 | AC1.4.2, AC1.4.3 | Covered. Boundary missing. See F5. |
| FR5.4 | AC2.2.1 to AC2.2.4 | Covered, but AC2.2.2 is time-flaky as written. See F8. |
| FR5.5 | AC2.1.1, AC2.1.2 | Covered, but AC2.1.2 "state is consistent" is not pass/fail. See F9. |
| NFR1 | AC1.1.5 | Covered, but "takes no longer than" is a flaky timing assertion. See F7. |
| NFR2 | AC1.4.2 | Covered, needs a named observable for "tracked key count". See F7. |
| NFR3 | AC1.3.5 | Covered. |
| NFR4 | none | UNCOVERED. No story or AC. See F10. |
| T2 (window rollover) | AC1.2.4 covers the limit boundary only | PARTIAL. No AC for a request landing exactly on a window rollover. See F5. |

Uncovered requirement IDs: **NFR4** (no coverage), **FR1.2** (default-clock half), **FR3.1** (result type half).

### B. Findings and suggested wording

**F1. AC1.2.3 and AC1.2.4 contradict each other at the boundary (blocking for testability).**
Worked case: three requests at t=5 (window [0,10)). At t=5 `check` is refused. At t=10 the previous window count is 3 and `elapsed_fraction` is 0, so the effective count is 3.0, which is "at or above" the limit, so it is still refused. It is allowed only at t=10+delta for any delta > 0. So `retry_after` is the infimum (5.0), and "when time advances by `r`, the next `check` is allowed" fails under AC1.2.4. Decision needed from the lead, and the AC must state it. Recommended wording:
- AC1.2.3 (replace): Given "a" is refused with `retry_after = r`, when the clock advances by `r - 0.001`, then `check("a")` is still refused; when it advances by `r + 0.001`, then `check("a")` is allowed.
This keeps FR3.3 ("seconds until a request would next be allowed") satisfied as the infimum, and it is deterministic with a fake clock. Alternative: define `retry_after` to include a tiny epsilon, which then needs its own AC. Either way, the story must state which.

**F2. Window alignment is unspecified and changes every numeric example.**
FR2.1/FR2.2 say "current window start" but not whether windows are aligned to multiples of `window_seconds` on the clock axis or anchored at the key's first request. AC1.3.2 ("current window 50% elapsed") only has a defined meaning under one of them. Add to Assumptions in stories.md: "Windows are aligned to multiples of `window_seconds` on the clock axis (window start = floor(t / window_seconds) * window_seconds)." This also makes NFR3 trivially testable. If the lead prefers first-request anchoring, every example needs re-derivation. Must be recorded for Code Generation.

**F3. Concrete worked example for a non-trivial `retry_after` (add to US1.2).**
Given the clock at t=15, previous window (t 0 to 10) count 3, no requests yet in the current window: first `check` is allowed (effective 1.5 before, 2.5 after), second `check` at t=15 is allowed (2.5 before, 3.5 after, `remaining` 0), third `check` at t=15 is refused (3.5), and `retry_after` is approximately 1.6667 (the effective count 1 + 3*(1 - f) falls below 3 when f > 2/3, i.e. t > 16.667). Suggested AC1.2.5: "Given the sequence above, when the third check is refused, then `retry_after` equals 1.6667 within 1e-3 (use `pytest.approx`) and a `check` at t=16.7 is allowed." This pins the formula, not only "greater than 0.0".

**F4. Remaining rounding and clamping, and vague "barely counts" (US1.3, FR3.2).**
- AC1.3.3 "barely counts" is not pass/fail. Replace with: Given 3 requests in the previous window and the clock 75% through the current window (t=7.5 relative, an exact binary fraction), when I call `check`, then the effective count before the request is 0.75, `allowed` is true, and `remaining` is 1 (floor of 3 - 1.75). Avoid 90% in tests because 3 * (1 - 0.9) is 0.30000000000000004 in floating point; if kept, require `pytest.approx` for effective-count checks and assert on `remaining` only.
- Add AC1.3.6 (round down): Given 2 requests in the previous window and the clock 50% through the current window, when I call `check`, then effective is 1.0 before, 2.0 after, so `remaining` is 1. Add a second fractional case (previous count 1 at 25% elapsed gives 0.75 before, 1.75 after, `remaining` = floor(1.25) = 1).
- Add AC1.3.7 (not below zero): Given 3 requests in the previous window and the clock 10% through the current window (effective 2.7, allowed), when the request is recorded (effective 3.7), then `remaining` is 0, not negative.

**F5. Boundary and rollover coverage (T2 and FR5.2/FR5.3 are "more than two full windows").**
Add ACs so exact-boundary behavior is pinned, not left to the implementer:
- AC1.3.8 (rollover): Given 3 requests at t=9.99 in window [0,10), when I call `check` at exactly t=10.0, then the previous count is 3 with `elapsed_fraction` 0, so the effective count is 3.0 and the request is refused; at t=10.0 plus a clock step of 5.0 (t=15) the effective count is 1.5 and it is allowed. This is the T2 window-rollover test.
- AC1.3.4 (tighten): add the "exactly one full window" case. Given the last activity at t=5 (window 0), when I call `check` at t=25 (window 2, more than one full window after the end of window 0), then the previous count is zero; at t=15 (window 1) the previous count is still 3 (weighted).
- AC1.4.1/AC1.4.2 (boundary): state "more than two full windows" as a strict inequality and test both sides: Given last activity at t=0, when `cleanup()` runs at exactly t=20 (two windows), then the key is kept; when it runs at t=20.001, then the key is removed. Without this, an off-by-one in `>` vs `>=` passes the draft ACs.
- Define "last activity": does a refused `check` update last-activity time? The draft AC1.2.2 says refused attempts are not counted, but it does not say whether they keep the key alive. Add an AC (either answer is acceptable, but it must be stated). Recommended: a refused `check` does not record a request but does not change last activity either, so an abusive client cannot hold state forever; the key-count assertion then needs no ambiguity.
- Add AC1.4.5: `cleanup()` on an empty limiter does nothing and does not raise; `cleanup()` leaves keys within the one-to-two-window range in place with previous count treated as zero (FR2.3 and FR5.3 interaction).

**F6. Defaults and result type (FR1.2, FR3.1, FR5.1, NFR3).**
- New AC1.1.6 (default clock, FR1.2): Given a limiter constructed without a clock and `time.monotonic` patched with `monkeypatch` to a controllable function, when I call `check`, then the patched function is the one read.
- AC1.3.1 (make verifiable): Given a limiter built with a fake clock and `time.monotonic` and `time.time` patched to raise, when I run `check`, `reset`, and `cleanup`, then no exception occurs. This proves "reads only from that function".
- New AC1.1.7 (result type, FR3.1): Given any `check` result, then it has attributes `allowed` (bool), `remaining` (int), `retry_after` (float), and assigning to a field raises (immutable, per the Assumption).
- New AC1.5.4 (reset effect on count): Given "a" is tracked, when I call `reset("a")`, then the tracked key count drops by one.

**F7. Introspection: stories refer to internals the requirements do not name.**
AC1.1.5 "inspect the stored state", AC1.4.2 "tracked key count is 0", and AC2.2.x "thread" all need an observable that a test can read. Add to Assumptions: "The limiter exposes a read-only way to see the tracked key count (for example `len(limiter)` or a `tracked_keys` property) and the per-key state (window start, current count, previous count), exact names left to Code Generation." Also fix NFR1:
- AC1.1.5 (replace the timing clause): remove "check takes no longer than on the first call". Wall-clock timing assertions are flaky. Replace with a structural check: after 10,000 requests across many windows for one key, the per-key state has exactly three fields, the tracked key count is 1, and the state is the same size as after the first request. Optional NFR1 proxy: patch the clock to count reads and assert `check` performs a constant number of clock reads regardless of history.

**F8. Background cleanup determinism (US2.2, FR5.4, T3).**
Real intervals invite flaky tests. Recommended test design to put in the ACs:
- AC2.2.2 (rewrite): Given a limiter with a fake clock, three idle keys (clock advanced beyond two windows), and background cleanup started with interval 0.01 seconds, when I wait on a `threading.Event` that the test sets from a wrapped/spied `cleanup()` (timeout 5 seconds, never `time.sleep`), then the event is set and the tracked key count is 0. This asserts on a signal, not on elapsed time, so it cannot flake on a slow machine; the timeout only guards against a hang.
- AC2.2.3 (make pass/fail): Given background cleanup running, when I call stop, then within 5 seconds the thread is no longer alive (`not thread.is_alive()` or `threading.active_count()` back to the starting value) and the thread is a daemon so it cannot block interpreter exit. Add that stop is idempotent.
- Add the lifecycle sad paths FR5.4 leaves open (the lead must pick behaviors; suggested): AC2.2.5 stop without start does nothing and does not raise; AC2.2.6 starting twice either raises `RuntimeError` or is a no-op (state which; testable either way); AC2.2.7 start after stop works again.
- AC2.2.1: make the observable explicit: `threading.active_count()` is unchanged by construction.
- Optional AC2.2.8: if `cleanup()` raises inside the loop (for example a failing injected clock), the loop either survives or stops visibly, and stop still returns promptly.

**F9. Thread-safety determinism (US2.1).**
- AC2.1.1 is deterministic because the clock is frozen: 800 `check("a")` calls, `limit = 50`, exactly 50 allowed. Strengthen so it can actually fail without a lock: start all threads behind a `threading.Barrier` and lower `sys.setswitchinterval` to a tiny value in the test; always `join(timeout=...)` and assert no thread is alive to avoid a hung test run. Note in the AC that a passing run is evidence rather than proof, because CPython's GIL makes races rare; the lock design is verified by code review in later stages.
- AC2.1.2 "state is consistent" is not pass/fail. Replace with invariants that hold regardless of interleaving (the exact counts are non-deterministic, so do not assert them): no thread raised (collect exceptions in a list and assert it is empty); the number of allowed results for any key never exceeds `limit` within one frozen window between resets; the tracked key count is between 0 and the number of distinct keys used; counts in the per-key state are never negative. The fake clock used by threads must itself be thread-safe (a frozen constant is).
- Add AC2.1.3: `cleanup()` running concurrently with `check` on active keys never removes an active key (use a frozen clock so no key is idle).

**F10. NFR4 (stdlib only) has no story. Suggested new AC.**
Add to US1.1 (or a small Should Have story under Group 2): AC1.1.8: Given the installed package, when I inspect its runtime imports (an AST scan of the source for import roots, or `pyproject` `dependencies` being empty), then every imported module is in `sys.stdlib_module_names` (Python 3.10+). This is a single quick test and closes NFR4. Alternatively record NFR4 as "verified by Build and Test, not a story" in the traceability notes; either is acceptable, but it must not be silently dropped.

**F11. Smaller wording issues that affect pass/fail clarity.**
- AC1.1.1: add `isinstance` checks on field types (links to AC1.1.7).
- AC1.2.2: "the refused attempts were not counted against it" needs an observable: after the refusal, the per-key current count is still 3, or, equivalently, a refused-then-waited sequence behaves the same as with no refused attempts (use the F3 numbers).
- AC1.4.4 is a statement about the test method, not a behavior with a pass/fail. Restate or remove: "Given the fake clock is advanced past two windows, when `cleanup()` is called, then the idle key is removed with zero calls to `time.sleep` (patch `time.sleep` to raise)."
- AC1.3.5 should name how: run the same recorded (key, time) sequence on two fresh limiters and compare the list of results for equality.
- Add one sad-path note for clock regress: an injected clock that returns an earlier time than before. FR/NFR are silent; either add an Assumption "clock never decreases" (recommended, and consistent with the monotonic default) or an AC that elapsed time below zero never yields a negative effective count.
- US2.x dependency on US1.4: the dependency note says US2.1 and US2.2 depend on `cleanup()`. They remain independently testable once `cleanup()` exists, which is acceptable for INVEST, but US2.1 can run on `check` and `reset` alone, so list it as "independent, extended by cleanup".

### C. Suggested test-pyramid and traceability note for the stories
Every AC above maps to one pytest unit test with the fake clock except the two threaded ACs (US2.1, US2.2), which use Barrier/Event synchronization instead of sleeping. No AC needs an integration or e2e test. T3 allows a short real interval; with the Event-based design in F8 the interval can stay at 0.01 seconds and the timeout only protects against a hang. Add an "AC to FR/NFR trace" table to stories.md (the matrix in section A can be copied) so the traceability rule in the inception guardrails is met by the artifact itself.

## Positions

- OBJECT: AC1.2.3 as written contradicts AC1.2.4, since at the exact `retry_after` the effective count equals the limit and the request is still refused (F1).
- OBJECT: AC1.1.5 relies on a wall-clock timing comparison ("takes no longer than"), which is flaky and not a valid pass/fail; replace with a structural check (F7).
- OBJECT: AC2.2.2 and AC2.2.3 are not deterministic as written; they need an Event-based wait with a timeout instead of waiting for "the interval to elapse" (F8).
- OBJECT: AC2.1.2 "state is consistent" and AC1.3.3 "barely counts" are not pass/fail; replace with the invariants and numbers given (F9, F4).
- OBJECT: NFR4 has no story or AC, and FR1.2 (default clock) and FR3.1 (result type) are only partly covered (F6, F10).
- OBJECT: window alignment and "last activity" semantics are unspecified; both change expected values in the ACs and must be stated as assumptions (F2, F5).
- AGREE: Breakdown by workflow (Q1 = C) and separate stories for thread safety and background cleanup (Q2 = A); both give independent, separately testable ACs.
- AGREE: Priorities and the Must Have set (US1.1 to US1.4) as a complete working limiter; US1.5 as Should Have is fine.
- AGREE: Given/When/Then format and fake-clock approach satisfy the inception guardrail and the "tests shall not sleep" testing requirement.

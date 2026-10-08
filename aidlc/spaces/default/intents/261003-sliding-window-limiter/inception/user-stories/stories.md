# User Stories

Breakdown: by workflow, with thread safety and background cleanup as their own stories (answers to Q1 and Q2 in `user-stories-questions.md`). Stories add no new requirements; each traces to `requirements.md`. Where a story pins down something the requirements left open, it is tagged `[assumption]` and listed under Assumptions and Open Questions.

Interface names use Python snake_case: `check`, `reset`, `cleanup`, result fields `allowed`, `remaining`, `retry_after`, constructor arguments `limit` and `window_seconds`. (The Q3 answer wrote `retryAfter`; FR3.1 is authoritative.)

Constants used in the examples: `limit = 3`, `window_seconds = 10`, and a fake clock under the test's control. Windows are aligned to multiples of `window_seconds` on the clock axis (window 0 is [0, 10), window 1 is [10, 20), and so on). In every example, `remaining` is computed after the new request is recorded: `max(0, floor(limit - effective_count_after))`.

## Group 1: Core limiting workflow

### US1.1: Allow requests under the limit
**Priority:** Must Have
**As** Priya (application developer), **I want** each `check(key)` under the limit to be allowed and tell me how many further requests I could make right now, **so that** I can serve the request and show the client its remaining budget.

Acceptance criteria:
- AC1.1.1: Given a new limiter with `limit = 3`, when I call `check("a")`, then `allowed` is true, `remaining` is 2, and `retry_after` is 0.0.
- AC1.1.2: Given 2 requests already recorded for "a" in the current window, when I call `check("a")`, then `allowed` is true and `remaining` is 0.
- AC1.1.3: Given "a" is at its limit, when I call `check("b")`, then `allowed` is true and `remaining` is 2 (keys are independent).
- AC1.1.4: Given any `check` result, when I read its fields, then `allowed` is a bool, `remaining` is an int, and `retry_after` is a float, and assigning to any field raises an error.
- AC1.1.5: Given 10,000 requests for one key across many windows, when I read the limiter's tracked key count and that key's stored state, then the count is 1 and the state holds only the window start, the current count, and the previous count. (Structural check for FR2.2 and NFR1; no timing assertion.)

INVEST: independent; the smallest slice that produces a working limiter. Size: M.

### US1.2: Block requests over the limit
**Priority:** Must Have
**As** Priya, **I want** a request over the limit to be refused with the time to wait, **so that** I can return a "retry later" response with an accurate delay.

`retry_after` is fractional seconds, set only on a refusal. Rounding it up for an HTTP `Retry-After` header is the caller's job. [assumption] `retry_after` is the smallest wait after which the next request is allowed: waiting exactly `retry_after` is enough, and waiting 0.001 seconds less is not.

Acceptance criteria:
- AC1.2.1: Given 3 requests recorded for "a" in the current window, when I call `check("a")`, then `allowed` is false, `remaining` is 0, and `retry_after` is greater than 0.0.
- AC1.2.2: Given "a" was just refused, when I call `check("a")` again at the same instant, then it is refused again with the same `retry_after`, because refused attempts do not use up budget.
- AC1.2.3: Given 3 requests at t=0 and a refusal at t=4 with `retry_after = r` (about 6.0), when the clock reaches t = 4 + r, then `check("a")` is allowed; when it reaches t = 4 + r - 0.001, then it is still refused.
- AC1.2.4: Given 3 requests at t=0, when I call `check("a")` at exactly t=10.0 (window 1, previous count 3, nothing elapsed), then the effective count is 3.0, which is at the limit, so the request is refused with `retry_after` greater than 0.0.
- AC1.2.5: Given 3 requests at t=0 and then three `check("a")` calls at t=15, then the first two are allowed (effective counts 2.5 and 3.5 after recording, `remaining` 0 both times) and the third is refused with `retry_after` of about 1.667 (compare with `pytest.approx`); a `check` at t=16.7 is allowed.

INVEST: testable on its own with a fake clock; it shares the window math of US1.3. Size: M.

### US1.3: Recover smoothly as the window slides
**Priority:** Must Have
**As** Priya, **I want** the count from the previous window to fade out as the current window elapses, **so that** a burst at a window edge cannot let through double my limit.

Acceptance criteria:
- AC1.3.1: Given 3 requests in the previous window and the clock 75% through the current window (t=17.5), when I call `check`, then the effective count before the request is 0.75, `allowed` is true, and `remaining` is 1.
- AC1.3.2: Given 3 requests in the previous window and the clock 50% through the current window, when I call `check`, then the effective count before the request is 1.5, so it is allowed, and after recording it the effective count is 2.5 so `remaining` is 0.
- AC1.3.3: Given 2 requests in the previous window and the clock 50% through the current window, then `remaining` after the request is 1; given 1 request in the previous window at 25% elapsed, then the effective count after the request is 1.75 and `remaining` is 1 (rounded down).
- AC1.3.4: Given 3 requests in the previous window and the clock 10% through the current window, when I call `check`, then the effective count before the request is 2.7 so it is allowed, and `remaining` is 0, never negative.
- AC1.3.5: Given 3 requests at t=9.99, when I call `check` at exactly t=10.0, then it is refused (effective count 3.0); at t=15 the effective count is 1.5 and it is allowed.
- AC1.3.6: Given last activity at t=5 (window 0), when I call `check` at t=15 (window 1), then the previous count of 3 is carried at weight 0.5; when I call `check` at t=25 (window 2), then the previous count is treated as zero and the result is that of a first request. Given last activity at t=0.1 and a check at t=19.9, then the previous count is carried at weight 0.01 (compare with `pytest.approx`).

[assumption] "More than one full window since last activity" in FR2.3 is read as: the previous count is carried only when the current window directly follows the window of last activity, and is zero when two or more windows have passed. See Open Questions.

INVEST: shares code with US1.2; negotiable on example values, not on the weighting rule. Size: M.

### US1.4: Clean up idle clients
**Priority:** Must Have
**As** Priya, **I want** state for clients that have gone quiet to be removed, **so that** memory use follows active clients only.

"Last activity" is the time of the last request that was allowed and recorded. [assumption] A refused request does not extend a key's life, so an abusive client cannot hold its state forever. A key is idle when its last activity is strictly more than two windows (20 seconds in the examples) ago.

Acceptance criteria:
- AC1.4.1: Given "a" last active at t=0, when I call `check("a")` at t=20.001, then its stale state is replaced, the stored state shows current count 1 and previous count 0, and the result equals that of a first request.
- AC1.4.2: Given several keys with no activity for more than two windows, when I call `cleanup()`, then all of them are removed and the tracked key count is 0.
- AC1.4.3: Given a mix of idle and active keys, when I call `cleanup()`, then only the idle keys are removed and active keys keep their counts.
- AC1.4.4: Given "a" last active at t=0, when `cleanup()` runs at exactly t=20, then "a" is kept; when it runs at t=20.001, then "a" is removed.
- AC1.4.5: Given an empty limiter, when I call `cleanup()`, then nothing happens and no error is raised.
- AC1.4.6: Given 3 requests for "a" at t=9 and a refusal at t=10, when `cleanup()` runs at t=29.001, then "a" is removed (the refusal did not extend its life; last activity is still t=9, which is more than two windows earlier). [Corrected after Code Generation: the original example, a refusal at t=18 after activity at t=0, cannot occur because the weighted count has faded to 0.6 by then.]

INVEST: independent of the background timer (US2.2). Size: S.

### US1.5: Reset one client
**Priority:** Should Have
**As** Priya, **I want** to clear a single client's history, **so that** I can lift a limit after a manual review or a plan change.

Acceptance criteria:
- AC1.5.1: Given "a" is refused, when I call `reset("a")` and then `check("a")`, then it behaves as the first request (allowed, `remaining` 2).
- AC1.5.2: Given I reset "a", when I call `check("b")`, then "b" is unaffected.
- AC1.5.3: Given "z" has never been seen, when I call `reset("z")`, then nothing happens and no error is raised.
- AC1.5.4: Given "a" is tracked, when I call `reset("a")`, then the tracked key count drops by one.

INVEST: independent. Size: XS.

### US1.6: Configure the limiter
**Priority:** Must Have
**As** Priya, **I want** to set the limit, the window, and optionally the clock when I create the limiter, and to be told clearly when I get it wrong, **so that** a bad setting fails at startup instead of silently letting everything through.

Acceptance criteria:
- AC1.6.1: Given a `limit` of 0 or -1, when I construct the limiter, then it raises a `ValueError` whose message names `limit` and the value received (for example `limit must be positive, got 0`). [assumption] The message wording.
- AC1.6.2: Given a `window_seconds` of 0 or -5, when I construct the limiter, then it raises a `ValueError` whose message names `window_seconds` and the value received.
- AC1.6.3: Given no clock argument and `time.monotonic` replaced by a controllable function, when I call `check`, then the replaced function is the one read.
- AC1.6.4: Given a zero-argument callable returning seconds as a float, when I pass it as the clock, then the limiter uses it.
- AC1.6.5: Given the package source, when I scan its runtime imports, then every imported module is part of the Python standard library (`sys.stdlib_module_names`).

INVEST: independent; small. Covers FR1 and NFR4. Size: S.

### US1.7: Control time in tests
**Priority:** Must Have
**As** Tomas (test author), **I want** every time reading to go through the clock I supply, **so that** I can reproduce window-edge behavior exactly without sleeping.

Acceptance criteria:
- AC1.7.1: Given a limiter built with a fake clock and with `time.monotonic` and `time.time` replaced by functions that raise, when I run `check`, `reset`, and `cleanup`, then no error occurs.
- AC1.7.2: Given the same recorded sequence of (key, time) pairs, when I run it on two fresh limiters, then the two lists of results are equal.
- AC1.7.3: Given `time.sleep` replaced by a function that raises, when I advance the fake clock past two windows and call `check` and `cleanup`, then windows roll over and idle keys are removed without any waiting.

[assumption] The supplied clock never goes backwards; behavior if it does is not specified.

INVEST: independent. Size: S.

## Group 2: Operating the limiter

### US2.1: Safe use from several threads
**Priority:** Should Have
**As** Priya, **I want** `check`, `reset`, and `cleanup` to be safe to call together from several threads, **so that** my multi-threaded service never corrupts limiter state.

A passing run is evidence rather than proof, because the interpreter's global lock makes races rare; the locking design is confirmed in code review.

Acceptance criteria:
- AC2.1.1: Given 8 threads released together by a barrier, each making 100 `check("a")` calls with `limit = 50` and a frozen clock, when all threads have finished (joined with a timeout), then exactly 50 calls were allowed and no thread is still alive.
- AC2.1.2: Given threads calling `check`, `reset`, and `cleanup` at the same time, when they finish, then no thread raised an error, every result has `remaining` between 0 and `limit`, the tracked key count is between 0 and the number of distinct keys used, and no stored count is negative.
- AC2.1.3: Given a frozen clock and threads running `cleanup()` while others call `check` on active keys, when they finish, then no active key was removed.

INVEST: independent, extended by `cleanup()` from US1.4. Size: S.

### US2.2: Optional periodic background cleanup
**Priority:** Should Have
**As** Priya, **I want** to start a periodic cleanup with a chosen interval in seconds, **so that** a long-running service frees idle keys without my calling `cleanup()` by hand. **As** Tomas, **I want** to stop it cleanly, **so that** my test run never hangs.

The interval is real time, but key ages still come from the injected clock (FR5.1), so tests advance the fake clock and wait on a signal. [assumption] The lifecycle rules below (start twice, stop twice, restart, daemon thread, error on a bad interval) are not in the requirements; they are listed for confirmation at the gate.

Acceptance criteria:
- AC2.2.1: Given a limiter that was never asked to start background cleanup, when I construct it, then no background thread is running (the process thread count is unchanged).
- AC2.2.2: Given a fake clock advanced past two windows with three idle keys, and background cleanup started with an interval of 0.01 seconds, when I wait up to 5 seconds on a signal set from a spy around `cleanup()`, then the signal is set and the tracked key count is 0.
- AC2.2.3: (Tomas) Given background cleanup is running, when I stop it, then within 5 seconds the thread is no longer alive, and the thread is a daemon so it can never block interpreter exit.
- AC2.2.4: Given background cleanup was never started or is already stopped, when I stop it, then nothing happens and no error is raised.
- AC2.2.5: Given background cleanup is already running, when I start it again, then no second thread is created; given it was stopped, when I start it again, then it runs again.
- AC2.2.6: Given an interval of 0 or less, when I start background cleanup, then it raises a `ValueError`. [assumption] FR5.4 says "configurable interval" without naming this error; to be confirmed at the gate.

INVEST: independent of US1.4's on-demand `cleanup()`; the test uses a short real interval, as the requirements allow. Size: S to M.

## Priority Summary

| Priority | Stories |
|----------|---------|
| Must Have | US1.1, US1.2, US1.3, US1.4, US1.6, US1.7 |
| Should Have | US1.5, US2.1, US2.2 |
| Could Have | none |
| Won't Have | per-key limits, token bucket, async API, distributed state (see requirements Out of Scope) |

## Requirement Coverage

| Requirement | Stories |
|-------------|---------|
| FR1 (configuration) | US1.6, US1.7 |
| FR2 (sliding-window counting) | US1.1, US1.3 |
| FR3 (check operation) | US1.1, US1.2, US1.3 |
| FR4 (reset) | US1.5 |
| FR5 (time and eviction) | US1.4, US1.7, US2.1, US2.2 |
| NFR1 (constant time per check) | US1.1 |
| NFR2 (memory by active keys) | US1.4 |
| NFR3 (deterministic) | US1.7 |
| NFR4 (standard library only) | US1.6 |

The element-level mapping is in `traceability.json`.

## Dependencies

US1.2 and US1.3 share the window math, so build them together. Both use the interface in US1.1. US1.4 and US1.5 are independent of each other. US2.1 can be built on `check` and `reset` alone and is extended once US1.4's `cleanup()` exists. US2.2 depends on `cleanup()`. The Must Have set (US1.1 to US1.4, US1.6, US1.7) is a complete working limiter.

## Assumptions and Open Questions

- [assumption] Windows are aligned to multiples of `window_seconds` on the clock axis. Origin: quality review; every numeric example depends on it.
- [assumption] FR2.3 is read by window gap (carry the previous count only when the current window directly follows the window of last activity). Origin: developer review, which showed the literal wording ("more than one full window since last activity") gives a different answer for last activity at t=0.1 and a check at t=19.9. Open Question for the human and for Functional Design: confirm this reading of FR2.3, which clarifies an approved requirement.
- [assumption] `retry_after` is the smallest wait after which the next request is allowed (nudged just above the exact crossing so the guarantee holds in floating point). Origin: developer and quality reviews, since waiting the exact crossing time is still refused under the strict "below the limit" rule.
- [assumption] The limiter exposes a read-only way to see the tracked key count and a key's stored state; names are left to Code Generation. Origin: several criteria cannot be observed without it.
- [assumption] A refused request does not extend a key's last activity.
- [assumption] The supplied clock never goes backwards.
- [assumption] Background cleanup lifecycle rules and the `ValueError` messages in US1.6 and US2.2.

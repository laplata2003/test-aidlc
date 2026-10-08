**Collaborator:** aidlc-developer-agent

## Contribution

Scope: implementability, sizing, and consistency of the ACs with FR2 (formula) and FR3 (check semantics). Assumed constants as in stories.md: `limit = 3`, `window_seconds = 10`, windows half-open `[k*10, (k+1)*10)`.

### Arithmetic checked (OK)
- AC1.1.1: new key, effective count before = 0 < 3 so allowed; after recording = 1; `remaining = floor(3 - 1) = 2`. Correct, and consistent with FR3.2 (the new request counts toward `remaining`).
- AC1.1.2: 2 recorded, before = 2 < 3 so allowed; after = 3; `remaining = 0`. Correct.
- AC1.3.2: previous 3, f = 0.5: before = 0 + 3*(1-0.5) = 1.5 < 3 so allowed; after = 2.5; `remaining = floor(0.5) = 0`. Correct.
- AC1.3.3: f = 0.9 gives weight 1 - 0.9 = 0.1. Correct.
- AC2.1.1: frozen clock, previous = 0, 800 calls, counter reaches 3-style cap at 50 (effective 50 is "at or above"), so exactly 50 allowed. Correct.

### Findings that need wording changes

1. **AC1.2.3 (`retry_after`) is not satisfiable as written.** FR3.2/FR3.3 and AC1.2.4 make "allowed" strict (`effective < limit`). Any `retry_after` solved as "the time when effective == limit" lands exactly on the boundary, where the request is still refused. Example: 3 requests at t=0 (window 0), refused at t=4. The effective count stays 3 through the end of window 0, and at t=10.0 it is still `0 + 3*(1-0) = 3` (refused); it drops below 3 only for t > 10. So the true wait is `6.0 + epsilon`, never exactly 6.0. Also floating point makes an exact-equality solution unreliable. Suggested wording:
   - AC1.2.3: "Given 'a' is refused with `retry_after = r`, when the clock advances by `r`, then the next `check('a')` is allowed. (`retry_after` is the smallest wait, computed so that the effective count is strictly below `limit` at `now + r`; it is always greater than 0.0.)"
   - Carry to Functional Design: compute the exact crossing time, then nudge up (for example with `math.nextafter`) so the guarantee holds in floating point.
   - Add a non-trivial worked example so the test is not only the trivial "wait for rollover" case: limit 3, W 10. 3 requests at t=0. At t=15 (window 1, previous 3, f=0.5): request 1 before 1.5, allowed (after 2.5, remaining 0); request 2 before 2.5, allowed (after 3.5, remaining 0 clamped); request 3 before 3.5, refused. Refused case needs `cur + prev*(1-f) < 3` with cur = 2, prev = 3: `2 + 3(1-f) < 3` so f > 2/3, so `retry_after` is about `10*(2/3 - 1/2) = 1.667` s (plus epsilon), then allowed at t about 16.667. Note it also shows "remaining 0" does not mean the next call is refused (see item 6).

2. **AC1.2.4 boundary needs a concrete reachable case.** Suggested: "Given 3 requests at t=0, when I call `check` at exactly t=10.0 (window 1 start, previous 3, f=0), then effective = 3.0 equals the limit, so it is refused and `retry_after > 0.0`." This also pins the half-open window boundary and the "retry_after strictly greater than 0.0" rule when the computed wait is 0 (FR3.3). Add to US1.2.

3. **FR2.3 vs window-index rollover contradiction (real defect, carry to design, mention in US1.3).** FR2.3 says previous = 0 when "more than one full window has passed since the key's last activity". The canonical algorithm instead zeroes the previous count only when the window index jumped by 2 or more. Counter-example: activity at t=0.1 (window 0), check at t=19.9 (window 1). Time since activity = 19.8 > 10, so FR2.3 literally zeroes previous, but the algorithm still carries window 0's count at weight 1 - 0.99 = 0.01. The difference is small but affects deterministic tests (NFR3). Recommendation: AC1.3.4 should say "when the current window is two or more windows after the window of last activity" and the Open Question list should ask the architect to reconcile FR2.3 with this wording. Provide a pair of ACs: gap of exactly one window (previous carried) and gap of two windows (previous zero).

4. **AC1.1.5 is partly untestable.** "`check` takes no longer than on the first call" is a timing assertion and will be flaky; NFR1 is better verified structurally. Suggest: "Given 10,000 checks on one key over many windows, then the per-key state is a fixed-size record with exactly window start, current count, previous count, and the limiter's tracked key count is 1." Also "when I inspect the stored state" needs a stated inspection seam. NFR2 and AC1.4.2 both require a tracked key count, so stories should assume a public read-only accessor (for example `len(limiter)` or `tracked_keys()`), to be named in design.

5. **US1.1 is oversized and mixes concerns.** It holds happy path (AC1.1.1/1.1.2), key independence (AC1.1.3, FR3.4), configuration validation (AC1.1.4, FR1.1), and constant state (AC1.1.5, FR2.2/NFR1). Suggested sizing: US1.1 stays M (not S) with five ACs; or move AC1.1.4 to a small "Configure the limiter" story (S) and add the missing default-clock AC (FR1.2: "Given no clock, when constructed, then time comes from a monotonic system clock"), which no story covers today. Either way, FR1.2's default-clock case needs an AC somewhere.

6. **`remaining` semantics should be stated once, with a second example.** `remaining = max(0, floor(limit - effective_after_recording))`. Because effective counts are fractional, `remaining = 0` can occur on an allowed request, and the next request may still be allowed (item 1 example). Add an AC in US1.3 where floor is visible: limit 5, previous 3, f=0.5: before 1.5, after 2.5, `remaining = floor(2.5) = 2` (never over-promises). Add a one-line note in US1.1/US1.2 that `remaining` is computed after recording and `retry_after` only on refusals.

7. **AC1.4.1 is not observable as written.** After more than two windows idle, FR2.3 already makes the previous count zero, so "treated as the first request" is true even without eviction. The lazy eviction behavior is only visible via tracked-key count. Reword: "...then its old state is dropped (tracked key count excludes the stale entry before the call; the key is re-created by the call) and the result equals a first request." Also add the boundary: idle exactly two windows is retained, more than two is evicted (FR5.2/FR5.3 say "more than").

8. **Dependencies section is inaccurate.** US1.2's AC1.2.3 (waiting across a window rollover) needs the sliding computation from US1.3; US1.2 is not "depends only on US1.1". Suggest listing US1.2 -> US1.1 and US1.3 (shared window-rollover logic), or splitting build order as: window math and state (US1.1 + US1.3 core) before `retry_after` (US1.2). INVEST "Independent" claim for US1.2 should be softened to "testable on its own with a fake clock".

9. **US1.3 actor.** The smooth recovery benefits Priya (the end consumer, her pain point is double-limit at window edges); the clock seam is Tomas's. Consider splitting the actor: keep US1.3 as Priya for AC1.3.2 to 1.3.4, and note AC1.3.1/1.3.5 (injected clock, determinism) belong to Tomas. Not blocking.

10. **AC2.2.4 introduces behavior not in the requirements** (ValueError for non-positive interval). It is tagged `[assumption]`, but the inception rule says not to introduce requirements without documenting origin. Either keep it with an explicit "to be confirmed at the gate" note and a matching entry for requirements, or drop it; it is cheap to implement (one check, S).

11. **US2.1 / US2.2 testability.**
    - AC2.1.2 "the state is consistent" is vague. Reword to assertable: "no exception is raised, every result has `0 <= remaining <= limit`, and `allowed` calls on a key never exceed `limit` between resets" (with a frozen clock and no reset on that key), plus the tracked key count is a non-negative integer.
    - AC2.2.2 should avoid sleeping against wall time: use a fake clock advanced in the test, a short real interval (0.01 to 0.05 s) for the timer, and wait on a `threading.Event` or a bounded poll with a timeout (FR T3 allows a short real interval). Say so in the AC so the test does not hang or flake.
    - AC2.2.3 should name the guarantee: after `stop()` returns, the thread has been joined (not alive); background thread is a daemon so it never blocks interpreter exit. Optionally specify `start()` twice and `stop()` when not started are no-ops (unspecified in requirements; flag as assumption or leave to design).

### Sizing summary (relative, for a Python library with pytest)
| Story | Size | Notes |
|-------|------|-------|
| US1.1 | M | Window/state data structure plus validation and independence; split config validation out if smaller slices are wanted |
| US1.2 | M | Hardest piece: `retry_after` across a window rollover; float-boundary care |
| US1.3 | M | Rollover and weighting logic; shares code with US1.2 |
| US1.4 | S | Lazy eviction plus `cleanup()`; needs a key-count seam |
| US1.5 | XS | One `dict.pop` |
| US2.1 | S | One lock around the three operations |
| US2.2 | S to M | Thread lifecycle (start/stop/join); interval validation |

All seven are buildable as written once items 1, 3, 4, and 7 are resolved. The Must Have set remains a complete working limiter.

## Positions

- OBJECT: AC1.2.3 cannot hold under the strict "below limit" rule unless `retry_after` is defined as the smallest wait giving effective count strictly below `limit` (nudged above the exact crossing); reword as in Contribution item 1.
- OBJECT: FR2.3 ("more than one full window since last activity") conflicts with window-index rollover (activity at t=0.1, check at t=19.9); stories must state the window-gap rule and surface the FR2.3 contradiction.
- OBJECT: AC1.1.5 relies on a timing assertion and an unnamed inspection seam; replace with a structural check and a named tracked-key accessor.
- OBJECT: AC1.4.1 is not observable (FR2.3 already zeroes the previous count); assert via tracked-key count and add the exactly-two-windows boundary.
- OBJECT: The Dependencies section understates US1.2's reliance on US1.3's window math.
- AGREE: Breakdown by workflow with thread safety and background cleanup as own stories is buildable, and the priority split (Must Have US1.1 to US1.4) yields a complete working limiter.
- AGREE: The remaining/`effective + new request` arithmetic in AC1.1.1, AC1.1.2, AC1.3.2, AC1.3.3 and AC2.1.1 matches FR2.1 and FR3.2.

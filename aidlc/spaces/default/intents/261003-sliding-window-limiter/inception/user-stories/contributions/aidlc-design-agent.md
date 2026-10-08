**Collaborator:** aidlc-design-agent

## Contribution

Lens: this is a library with no UI, so the "interface" is the Python API surface. Findings cover naming, result shape, error experience, and whether each story is told by the persona who actually meets that part of the interface. No new requirements are introduced; items that would add behavior are marked [assumption] or flagged as questions.

### A. Naming and result shape

1. **Field naming is inconsistent at the source.** `requirements.md` Sources [Q3] says `retryAfter`; FR3.1 and every story say `retry_after`. Python-idiomatic snake_case is correct and matches org.md Code Style. Suggested wording for a note at the top of `stories.md`: "Interface names use Python snake_case: `check`, `reset`, `cleanup`, result fields `allowed`, `remaining`, `retry_after`, constructor arguments `limit`, `window_seconds`. (The Q3 answer wrote `retryAfter`; FR3.1 is authoritative.)"
2. **Result type is described only as "a small immutable object" (assumption).** Add one AC to US1.1 so Priya's experience is stated: "Given any `check` result, when I read `allowed`, `remaining`, and `retry_after`, then they are a bool, an int, and a float, and assigning to a field raises an error." Keeps the three field types visible (note `retry_after` is `0.0`, a float, even when allowed).
3. **Meaning of `remaining` should be stated from the caller's view.** Suggested wording in US1.1: "`remaining` is the number of further requests I could make right now after this one." AC1.1.2 already shows `remaining` is 0 on the last allowed call; the sentence prevents a reading where it counts before the request.
4. **`retry_after` is a float; HTTP `Retry-After` wants whole seconds.** Priya's goal says "tell the client how long to wait". Add to US1.2 a note (not a requirement): "`retry_after` is fractional seconds; rounding up for a header is the caller's job." Avoids a hidden surprise without expanding scope.
5. **Do not add** truthiness (`bool(result)`), exceptions-on-block, or context-manager sugar. Not in requirements; `if not result.allowed` is enough and the stories already read that way.

### B. Persona fidelity (who meets what)

6. **US1.3 is told by Tomas but delivers Priya's core pain point.** Priya's pain ("fixed-window limiters let double the limit through at a window edge") is addressed only by AC1.3.2 to AC1.3.4, yet the story belongs to Tomas, and no story names Priya's pain directly. Suggest splitting actors without adding stories: keep US1.3 as the sliding behavior story with actor **Priya** ("As Priya, I want the count to decay smoothly as the window slides, so that a burst at a window edge cannot double my limit") carrying AC1.3.2, AC1.3.3, AC1.3.4; move AC1.3.1 and AC1.3.5 (injected clock, determinism) into a Tomas-owned story. Smallest option: make US1.3 a two-actor story with a "Priya:" and a "Tomas:" AC group. Preferred option: move the clock ACs to a new Must Have story "US1.6: Control time in tests" for Tomas, because FR1.2, FR5.1, and NFR3 are otherwise only a bullet and Tomas has no story of his own in Group 1. (If the mob wants to hold the story count, use the two-actor option.)
7. **US2.2 is told by Tomas, but its benefit is Priya's.** The benefit text is "long-running services free idle keys", which is a production concern. Suggest: actor **Priya** for AC2.2.1 to AC2.2.2 and AC2.2.4 (start with an interval, nothing runs unless asked, bad interval rejected) and **Tomas** for AC2.2.3 (stops cleanly, does not hang the run). This also matches Tomas's stated pain point about unstoppable background threads.
8. **Tomas's persona overreach.** `personas.md` calls Tomas the one who "operates the limiter's cleanup". Operating cleanup in a running service is Priya's job; Tomas verifies it. Suggested wording: "Tomas ... writes and maintains the pytest suite and verifies the limiter's clock and cleanup controls."
9. **Priya's context sentence** ("runs a single process with several threads") is what justifies US2.1; keep it. Add to Tomas's context that he is the first reader of error messages and the `Result` fields when a test fails (see C).

### C. Error and edge experience

10. **ValueError messages are part of the developer experience.** FR1.1 only says `ValueError`. Suggested AC addition to US1.1 (marked [assumption]; the requirement is unchanged): "when construction raises a `ValueError`, then the message names the offending argument and the value received (for example `limit must be positive, got 0`)." The existing AC1.1.4 splits cleanly: one case for `limit`, one for `window_seconds`, so a failing test says which.
11. **AC1.1.4 and AC1.1.5 do not belong under "allow requests under the limit".** AC1.1.4 is configuration (FR1.1). AC1.1.5 tests internal state size (FR2.2/NFR1), which a caller cannot see through the public interface. Suggestions: move AC1.1.4 into a short "configure" AC group or into US1.3/US1.6 for Tomas; reword AC1.1.5 as observable behavior ("tracked key count after `cleanup()` is 0", already AC1.4.2) plus a note that state size is verified at the test layer. If the mob keeps it, label it "(verified at test level, not part of the public interface)". This also helps INVEST "Independent" and "Small" for US1.1.
12. **AC1.2.3 has a floating-point edge.** "When time advances by `r`, the next `check` is allowed" can fail by an epsilon with a weighted blend. Suggested wording: "when time advances by `r` seconds, then the next `check("a")` is allowed, and one microsecond earlier it was still refused." The second half gives Tomas the exact boundary test; the implementation must make `retry_after` a safe, not approximate, wait time.
13. **AC1.2.2 states an implementation fact ("were not counted").** Rephrase to what the caller observes: "then it is refused again, and `retry_after` is not larger than before." This is the observable form of FR3.3.
14. **Ambiguity in US2.2.** (a) "starts again while running": say what happens. Open question for the mob, not a new requirement: starting a second time while running is a no-op or a documented error, never two threads. (b) "stop" should be safe to call when never started and when already stopped; AC2.2.3 should add "and calling stop again does nothing". (c) FR5.1 says all time reads use the injected clock, so the interval wait is real time but key ages in the background cleanup come from the injected clock; AC2.2.2 should say so, or Tomas will wonder why a frozen clock never cleans anything.
15. **Verb and unit consistency for background cleanup.** Use `start` / `stop` and an interval in seconds (same unit as `window_seconds`) in the story text; leave exact names to Code Generation, as the requirements do.

### D. Acceptance-criteria clarity

16. US1.3 AC1.3.3: give the arithmetic so it is checkable. "previous window count 3, 90% of the current window elapsed, then effective count before the request is 0.3" (3 x 0.1).
17. US2.1 AC2.1.2: "state is consistent" is not testable as written. Suggested wording: "then no exception was raised, and a following `check` on a fresh key returns `remaining` equal to `limit - 1`" or "and the tracked key count equals the number of keys that were checked and not reset or cleaned".
18. Add to the "Assumed constants" line that `clock` is a fake clock in all examples, so readers know the examples assume time is controlled.
19. Accessibility/responsive design: not applicable (no UI). Stories should not gain UI-style criteria. Docstrings are the only "screen" this library has; a one-line story note that the public methods carry docstrings with the example values is optional and left to Code Generation.

## Positions

- AGREE: Breakdown by workflow with thread safety and background cleanup as their own stories matches Q1 = C and Q2 = A.
- AGREE: Two personas are enough; Priya primary and Tomas secondary fits the interface (one caller, one verifier).
- AGREE: Priority split (Must Have US1.1 to US1.4; Should Have US1.5, US2.1, US2.2) is sound, since the Must Have set is a working limiter.
- OBJECT: US1.3 and US2.2 are narrated by the wrong persona (item 6 and 7); persona-to-pain-point mapping is broken, and Priya's window-edge pain has no direct story.
- OBJECT: AC1.1.4 and AC1.1.5 sit under the wrong story (item 11), and AC1.1.5 tests internal state a caller cannot observe.
- OBJECT: AC1.2.3 and AC2.1.2 are not reliably testable as written (items 12 and 17).

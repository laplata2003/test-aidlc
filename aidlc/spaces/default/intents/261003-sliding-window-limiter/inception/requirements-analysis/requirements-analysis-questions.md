# Requirements Analysis — Clarifying Questions

Initial description: Create an in-memory rate-limiter with sliding-window logic and unit tests

The workspace is empty (greenfield), so the language and project layout are open. These questions fill only the gaps that block writing requirements.

## Question 1
Which language and test framework should the rate-limiter be written in? The workspace has no existing code, so this choice also sets how the unit tests are written and run.

A. TypeScript (Node.js) with Vitest
B. TypeScript (Node.js) with Jest
C. Python with pytest
D. Go with the standard `testing` package
X. Other (please specify)

[Answer]: C

## Question 2
Which sliding-window algorithm should it use? This decides accuracy versus memory use per client.

A. Sliding window log: store a timestamp per request, exact counts, memory grows with the limit
B. Sliding window counter: weighted blend of the current and previous fixed windows, approximate counts, constant memory
X. Other (please specify)

[Answer]: B

## Question 3
What should the public interface look like, and what should a check return? This sets what callers and the unit tests assert on.

A. A single `allow(key)` call that returns true or false
B. A `check(key)` call that returns a result with `allowed`, `remaining` requests, and `retryAfter` time
C. Same as B, plus a `reset(key)` call to clear one client's history
X. Other (please specify)

[Answer]: C

## Question 4
How should it handle time and old data? Unit tests for a sliding window need to control the clock, and unbounded in-memory state can leak.

A. Accept an injectable clock for tests, and evict idle keys' stored data lazily on access
B. Accept an injectable clock for tests, and also run a periodic background cleanup of idle keys
C. Use the system clock directly, with no cleanup of idle keys
X. Other (please specify)

[Answer]: B. Injectable clock for deterministic tests; lazy eviction on access plus periodic background cleanup of idle keys, with the cleanup callable on demand so it can be tested with the injected clock.

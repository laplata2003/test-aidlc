# Personas

## P1: Priya, the application developer (primary)

- **Role:** Backend developer who embeds the limiter in a service to protect an endpoint or job from overuse by a single client.
- **Goals:** Decide in one call whether a request may proceed; tell the client how long to wait when it may not; never worry about the limiter leaking memory.
- **Pain points:** Fixed-window limiters let double the limit through at a window edge; limiters that hide how many requests remain make good error messages impossible.
- **Context:** Works in Python, runs a single process with several threads, wants no external service or dependency.

## P2: Tomas, the test author and maintainer (secondary)

- **Role:** Engineer who writes and maintains the pytest suite and verifies the limiter's clock and cleanup controls.
- **Goals:** Run every time-dependent test without sleeping, reproduce window-edge cases exactly, and trigger cleanup on demand.
- **Pain points:** Tests that depend on the real clock are slow and flaky; background threads that cannot be stopped hang the test run.
- **Context:** Reads the same interface as Priya, plus the clock and cleanup controls. He is the first reader of error messages and result fields when a test fails.

## Priority and Relationship

P1 is the primary persona: her stories carry the core behavior. P2 depends on the same interface and adds the controls that make the behavior verifiable. Neither persona is a separate system; both call the same limiter.

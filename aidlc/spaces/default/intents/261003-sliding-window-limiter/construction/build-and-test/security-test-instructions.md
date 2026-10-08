# Security Test Instructions: Sliding-Window Rate Limiter

Scope: a review of `src/sliding_window_limiter/limiter.py` by the security engineer, plus the checks to run. The requirements contain no security requirement, so nothing here is a pass/fail target; it records what was looked at and what remains open.

## Attack Surface

The library has no network, file, subprocess, or database access and no authentication, secrets, or user-supplied code paths. Its imports are `dataclasses`, `logging`, `math`, `threading`, `time`, and `typing`. The only inputs are the constructor arguments (`limit`, `window_seconds`, `clock`), the `key` passed to `check`/`reset`, and the `interval` passed to `start_background_cleanup`.

## STRIDE Notes

| Threat | Finding |
|--------|---------|
| Spoofing, Repudiation, Elevation of privilege | Not applicable: no identities, audit trail, or privileges inside the library. The caller decides what a "key" means. |
| Tampering | State is private to the instance and guarded by one lock. `KeyState` and `CheckResult` are frozen. A caller who replaces the `clock` can move time arbitrarily; that is by design for tests. |
| Information disclosure | Log output on a failed background pass uses `logger.exception` and includes no key or request data. Constructor `ValueError` messages echo the bad `limit`/`window_seconds`/`interval` value only. |
| Denial of service | See the open items below. |

## Open Items (residual risks, not defects)

1. **Memory growth from many distinct keys.** Each active key costs a small fixed record, and idle keys are removed only after more than two windows, by `cleanup()` or lazily when the same key is checked again. An attacker who controls the key (for example a client-supplied header) could create many keys faster than they expire. The requirements set no cap on tracked keys, so none was added. Mitigation for users: derive keys from a trusted value (an authenticated id or the peer address), and run background cleanup.
2. **A blocking clock blocks every caller.** The clock is read while holding the state lock. A custom clock that blocks stalls all threads. The default clock (`time.monotonic`) does not block.
3. **`assert` in `check`.** One internal assertion states an invariant (a refused key always has stored state). Python run with `-O` strips assertions; behavior is unchanged because the invariant holds.

## Checks to Run

No security scanner is installed in this environment, so none was run. When available:

- Static analysis: `python3 -m pip install bandit` then `bandit -r src` (expect no findings beyond the `assert` note above, which is low severity).
- Dependency scan: `python3 -m pip install pip-audit` then `pip-audit` (runtime dependencies are empty; the scan covers pytest in the test environment only).
- Key-flood check (manual): create a limiter with a fake clock, call `check` with 100,000 distinct keys, advance the clock past two windows, call `cleanup()`, and confirm `len(limiter) == 0`.

# Build and Test Summary: Sliding-Window Rate Limiter

## Overall Status

Build: success. Unit tests: 51 of 51 passed, repeated 9 times with the same result. Every measurable target is `Met`. No loop-back was needed.

## Prerequisites

Python 3.10 or later and pytest 7 or later. A virtual environment is recommended (see `build-instructions.md`). The verified run used the system Python 3.14.7 with pytest installed into the user site-packages.

## Test Type Inventory

| Type | Generated | Why |
|------|-----------|-----|
| Unit | Yes (51 cases in `tests/test_limiter.py`) | Minimal strategy; created in Code Generation |
| Integration | No | Minimal strategy; the library has no external boundary |
| Performance | No | Minimal strategy; no performance requirement (NFR1 is a structural claim, checked in a unit test) |
| Security | Review notes only (`security-test-instructions.md`) | No security requirement; the notes record residual risks |
| Contract, E2E, accessibility | No | Not applicable to an in-process library |

## Coverage Expectations

No line-coverage floor applies to the express scope and none was measured. Every one of the 25 requirement IDs and 43 acceptance criteria is mapped to a test (`cross-unit-traceability.md`).

## Target Verification Matrix

| Target ID | Source | Expected | Actual | Evidence | Owning Stage | Verdict |
|-----------|--------|----------|--------|----------|--------------|---------|
| BT-NFR1 | `requirements.md` NFR1 | `check` does constant work however many past requests a key has | Per-key state is a fixed record after 10,000 requests; no timing measurement was taken | `test_state_stays_fixed_size_after_many_requests` passed | build-and-test | Met |
| BT-NFR2 | `requirements.md` NFR2 | Memory follows active keys; after `cleanup()` more than two windows past all activity, tracked key count is 0 | Count is 0 after cleanup; active keys are kept | `test_cleanup_removes_all_idle_keys`, `test_cleanup_keeps_active_keys` passed | build-and-test | Met |
| BT-NFR3 | `requirements.md` NFR3 | Same keys and clock values give the same results | Two fresh limiters gave equal result lists | `test_same_sequence_gives_equal_results` passed | build-and-test | Met |
| BT-NFR4 | `requirements.md` NFR4 | Standard library only at runtime | Source imports are all standard library; `dependencies = []` | `test_package_imports_are_stdlib_only` passed; `pyproject.toml` | build-and-test | Met |
| BT-TC1 | Testing Contract (scope floor) | Existing suite stays green | No earlier suite existed; the new suite is green | 51 passed | build-and-test | Met |
| BT-TC2 | Testing Contract (Minimal strategy) | One verifiable test per requirement; a happy-path unit test per component | Every requirement and criterion has a test; the single component has happy-path tests | `cross-unit-traceability.md`, `test-results.md` | build-and-test | Met |

There were no stage-level or design-stage quality targets (no `nfr-requirements` or `nfr-design` artifacts exist in the express plan).

## Readiness Assessment

- Build-ready: yes.
- Test-ready: yes. One command, `python3 -m pytest tests/test_limiter.py`.
- Deployment-ready: not assessed. This is a library with no deployment target. Publishing it, or wiring it into a service, is outside this plan.

## Known Limitations and Outstanding Items

- AC1.4.6 in `stories.md` cannot happen as written; the test uses an adjusted scenario (see `test-results.md`). The story text is unchanged.
- The approved plan and earlier messages said 49 acceptance criteria; the right number is 43.
- Eviction inside `check` cannot be told apart from no eviction by any test, because it changes no result. It stays because FR5.2 asks for it.
- Security residual risks (unbounded distinct keys, a blocking clock under the lock) are listed in `security-test-instructions.md`. No scanner was run: none is installed.
- Black is not installed, so formatting is hand-written and unchecked.
- The system Python was changed by the developer (pytest installed with `--break-system-packages`); see `code-summary.md`.
- `.gitignore` has no entries for `.pytest_cache`, `__pycache__`, or `*.egg-info`.

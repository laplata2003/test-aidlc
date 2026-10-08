"""Unit tests for the sliding-window limiter, grouped by story."""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import sys
import threading
import time

import pytest

from sliding_window_limiter import CheckResult, KeyState, SlidingWindowLimiter

LIMIT = 3
WINDOW = 10


def make(clock, limit=LIMIT, window=WINDOW):
    return SlidingWindowLimiter(limit, window, clock=clock)


def burst(limiter, key, n):
    return [limiter.check(key) for _ in range(n)]


# --------------------------------------------------------------- US1.6 / US1.7


@pytest.mark.parametrize("bad", [0, -1])
def test_limit_must_be_positive(bad):
    with pytest.raises(ValueError, match=rf"limit must be positive, got {bad}"):
        SlidingWindowLimiter(bad, WINDOW)


@pytest.mark.parametrize("bad", [0, -5, float("nan")])
def test_window_must_be_positive(bad):
    with pytest.raises(ValueError, match="window_seconds must be positive"):
        SlidingWindowLimiter(LIMIT, bad)


def test_limit_non_number_is_value_error():
    with pytest.raises(ValueError, match="limit"):
        SlidingWindowLimiter("3", WINDOW)  # type: ignore[arg-type]


def test_default_clock_reads_time_monotonic_at_call_time(monkeypatch):
    now = [0.0]
    limiter = SlidingWindowLimiter(LIMIT, WINDOW)  # built before the patch
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    burst(limiter, "a", 3)
    assert limiter.check("a").allowed is False
    now[0] = 30.0
    assert limiter.check("a").allowed is True


def test_injected_clock_is_used(clock):
    limiter = make(clock)
    clock.set(123.0)
    limiter.check("a")
    assert limiter.key_state("a").last_activity == 123.0


def test_no_real_time_used_with_fake_clock(monkeypatch, clock):
    def boom(*_a, **_k):
        raise AssertionError("real time used")

    limiter = make(clock)
    monkeypatch.setattr(time, "monotonic", boom)
    monkeypatch.setattr(time, "time", boom)
    monkeypatch.setattr(time, "sleep", boom)
    limiter.check("a")
    limiter.reset("a")
    clock.advance(25)
    limiter.check("b")
    limiter.cleanup()
    clock.advance(25)
    assert limiter.check("b").remaining == 2
    clock.advance(25)
    limiter.cleanup()
    assert len(limiter) == 0


def test_same_sequence_gives_equal_results(clock):
    from conftest import FakeClock

    seq = [("a", 0), ("a", 1), ("b", 2), ("a", 9), ("a", 10), ("a", 15), ("a", 33)]

    def run():
        c = FakeClock()
        limiter = make(c)
        out = []
        for key, t in seq:
            c.set(t)
            out.append(limiter.check(key))
        return out

    assert run() == run()


def test_package_imports_are_stdlib_only():
    src = pathlib.Path(__file__).resolve().parent.parent / "src"
    roots = set()
    for path in src.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                roots.add(node.module.split(".")[0])
    assert roots
    assert roots <= set(sys.stdlib_module_names)


# ----------------------------------------------------------------------- US1.1


def test_first_request_allowed(clock):
    r = make(clock).check("a")
    assert (r.allowed, r.remaining, r.retry_after) == (True, 2, 0.0)


def test_last_allowed_request_has_zero_remaining(clock):
    results = burst(make(clock), "a", 3)
    assert [r.remaining for r in results] == [2, 1, 0]
    assert all(r.allowed for r in results)


def test_keys_are_independent(clock):
    limiter = make(clock)
    burst(limiter, "a", 3)
    assert limiter.check("a").allowed is False
    r = limiter.check("b")
    assert r.allowed is True and r.remaining == 2


def test_result_types_and_immutability(clock):
    r = make(clock).check("a")
    assert isinstance(r, CheckResult)
    assert type(r.allowed) is bool
    assert type(r.remaining) is int
    assert type(r.retry_after) is float
    for field in ("allowed", "remaining", "retry_after"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(r, field, 0)


def test_state_stays_fixed_size_after_many_requests(clock):
    limiter = make(clock, limit=1000)
    for i in range(10_000):
        clock.set(i * 0.05)
        limiter.check("a")
    assert len(limiter) == 1
    state = limiter.key_state("a")
    assert isinstance(state, KeyState)
    assert [f.name for f in dataclasses.fields(state)] == [
        "window_start",
        "current",
        "previous",
        "last_activity",
    ]
    assert limiter.key_state("missing") is None


# ----------------------------------------------------------------------- US1.2


def test_refused_at_limit(clock):
    limiter = make(clock)
    burst(limiter, "a", 3)
    r = limiter.check("a")
    assert (r.allowed, r.remaining) == (False, 0)
    assert r.retry_after > 0.0


def test_repeated_refusal_is_stable_and_free(clock):
    limiter = make(clock)
    burst(limiter, "a", 3)
    first = limiter.check("a")
    assert limiter.check("a") == first
    assert limiter.key_state("a").current == 3


def test_retry_after_is_the_smallest_sufficient_wait(clock):
    limiter = make(clock)
    burst(limiter, "a", 3)
    clock.set(4)
    r = limiter.check("a")
    assert r.retry_after == pytest.approx(6.0, abs=1e-6)
    clock.set(4 + r.retry_after - 0.001)
    assert limiter.check("a").allowed is False
    clock.set(4 + r.retry_after)
    assert limiter.check("a").allowed is True


def test_refused_exactly_at_window_boundary(clock):
    limiter = make(clock)
    burst(limiter, "a", 3)
    clock.set(10.0)
    r = limiter.check("a")
    assert r.allowed is False and r.retry_after > 0.0
    clock.set(10.0 + r.retry_after)
    assert limiter.check("a").allowed is True


def test_worked_example_at_t15(clock):
    limiter = make(clock)
    burst(limiter, "a", 3)
    clock.set(15)
    first, second, third = burst(limiter, "a", 3)
    assert (first.allowed, first.remaining) == (True, 0)
    assert (second.allowed, second.remaining) == (True, 0)
    assert third.allowed is False
    assert third.retry_after == pytest.approx(1.667, abs=1e-3)
    clock.set(16.7)
    assert limiter.check("a").allowed is True


# ----------------------------------------------------------------------- US1.3


def seeded(clock, t, count=3):
    """A limiter with `count` requests in window 0, clock moved to `t`."""
    limiter = make(clock)
    for _ in range(count):
        limiter.check("a")
    clock.set(t)
    return limiter


@pytest.mark.parametrize(
    "prev, t, remaining",
    [
        (3, 17.5, 1),  # effective before 0.75, after 1.75
        (3, 15, 0),  # before 1.5, after 2.5
        (2, 15, 1),  # after 2.0
        (1, 12.5, 1),  # before 0.75, after 1.75
        (3, 11, 0),  # before 2.7, after 3.7 -> floored at 0
    ],
)
def test_previous_window_fades_out(clock, prev, t, remaining):
    limiter = seeded(clock, t, prev)
    r = limiter.check("a")
    assert r.allowed is True
    assert r.remaining == remaining


def test_boundary_then_half_window(clock):
    limiter = make(clock)
    clock.set(9.99)
    burst(limiter, "a", 3)
    clock.set(10.0)
    assert limiter.check("a").allowed is False
    clock.set(15)
    assert limiter.check("a").allowed is True


def test_gap_of_one_window_carries_previous_count(clock):
    limiter = make(clock)
    clock.set(5)
    burst(limiter, "a", 3)
    clock.set(15)
    assert limiter.check("a").remaining == 0  # 3 * 0.5 + 1 = 2.5
    assert limiter.key_state("a").previous == 3


def test_gap_of_two_windows_forgets_previous_count(clock):
    limiter = make(clock)
    clock.set(5)
    burst(limiter, "a", 3)
    clock.set(25)
    assert limiter.check("a").remaining == 2
    assert limiter.key_state("a").previous == 0


def test_late_check_in_next_window_uses_small_weight(clock):
    limiter = make(clock)
    clock.set(0.1)
    burst(limiter, "a", 3)
    clock.set(19.9)
    r = limiter.check("a")
    assert r.allowed is True
    assert r.remaining == 1  # 3 * 0.01 = 0.03 before; 1.03 after
    assert limiter._effective(1, 0, 3, 19.9) == pytest.approx(0.03)


# -------------------------------------------------------------------- US1.4/1.5


def test_stale_key_is_replaced_lazily(clock):
    limiter = make(clock)
    burst(limiter, "a", 3)
    clock.set(20.001)
    r = limiter.check("a")
    assert (r.allowed, r.remaining) == (True, 2)
    state = limiter.key_state("a")
    assert (state.current, state.previous) == (1, 0)


def test_cleanup_removes_all_idle_keys(clock):
    limiter = make(clock)
    for k in "abc":
        limiter.check(k)
    clock.set(20.001)
    limiter.cleanup()
    assert len(limiter) == 0


def test_cleanup_keeps_active_keys(clock):
    limiter = make(clock)
    limiter.check("old")
    clock.set(15)
    burst(limiter, "new", 2)
    clock.set(25)
    limiter.cleanup()
    assert limiter.key_state("old") is None
    assert limiter.key_state("new").current == 2


def test_cleanup_boundary_is_strictly_more_than_two_windows(clock):
    limiter = make(clock)
    limiter.check("a")
    clock.set(20)
    limiter.cleanup()
    assert limiter.key_state("a") is not None
    clock.set(20.001)
    limiter.cleanup()
    assert limiter.key_state("a") is None


def test_cleanup_on_empty_limiter(clock):
    limiter = make(clock)
    limiter.cleanup()
    assert len(limiter) == 0


def test_refused_check_does_not_extend_life(clock):
    # AC1.4.6 as written (refusal at t=18 after activity at t=0) cannot occur:
    # the count has faded to 0.6 by then. Same intent, with a refusal that can.
    limiter = make(clock)
    clock.set(9)
    burst(limiter, "a", 3)
    clock.set(10)
    assert limiter.check("a").allowed is False
    clock.set(29.001)
    limiter.cleanup()
    assert limiter.key_state("a") is None


def test_reset_known_key_restores_first_request_behavior(clock):
    limiter = make(clock)
    burst(limiter, "a", 4)
    count = len(limiter)
    limiter.reset("a")
    assert len(limiter) == count - 1
    r = limiter.check("a")
    assert (r.allowed, r.remaining) == (True, 2)


def test_reset_does_not_touch_other_keys(clock):
    limiter = make(clock)
    burst(limiter, "a", 3)
    burst(limiter, "b", 2)
    limiter.reset("a")
    assert limiter.key_state("b").current == 2


def test_reset_unknown_key_is_a_noop(clock):
    limiter = make(clock)
    limiter.reset("z")
    assert len(limiter) == 0


# --------------------------------------------------------------------- US2.1


def run_threads(targets, timeout=10):
    errors = []

    def wrap(fn):
        def inner():
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        return inner

    threads = [threading.Thread(target=wrap(t), daemon=True) for t in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=timeout)
    assert not any(t.is_alive() for t in threads)
    assert errors == []


def test_concurrent_checks_allow_exactly_the_limit(clock):
    limiter = make(clock, limit=50)
    barrier = threading.Barrier(8)
    allowed = []

    def worker():
        barrier.wait(timeout=10)
        n = sum(limiter.check("a").allowed for _ in range(100))
        allowed.append(n)

    run_threads([worker] * 8)
    assert sum(allowed) == 50


def test_concurrent_check_reset_cleanup_stay_consistent(clock):
    limiter = make(clock, limit=5)
    keys = [f"k{i}" for i in range(4)]
    barrier = threading.Barrier(6)
    results = []

    def checker(key):
        def run():
            barrier.wait(timeout=10)
            for _ in range(200):
                results.append(limiter.check(key))
                state = limiter.key_state(key)
                if state is not None:
                    assert state.current >= 0 and state.previous >= 0

        return run

    def resetter():
        barrier.wait(timeout=10)
        for _ in range(200):
            limiter.reset("k0")

    def cleaner():
        barrier.wait(timeout=10)
        for _ in range(200):
            limiter.cleanup()

    run_threads([checker(k) for k in keys] + [resetter, cleaner])
    assert all(0 <= r.remaining <= 5 for r in results)
    assert 0 <= len(limiter) <= len(keys)


def test_concurrent_cleanup_never_removes_active_keys(clock):
    limiter = make(clock, limit=1000)
    keys = [f"k{i}" for i in range(5)]
    for k in keys:
        limiter.check(k)
    barrier = threading.Barrier(4)

    def checker():
        barrier.wait(timeout=10)
        for _ in range(100):
            for k in keys:
                limiter.check(k)

    def cleaner():
        barrier.wait(timeout=10)
        for _ in range(300):
            limiter.cleanup()

    run_threads([checker, checker, cleaner, cleaner])
    assert len(limiter) == len(keys)


# --------------------------------------------------------------------- US2.2


def test_background_cleanup_not_started_by_default(clock):
    before = threading.active_count()
    limiter = make(clock)
    limiter.check("a")
    assert threading.active_count() == before


def test_background_cleanup_runs_and_cleans(clock):
    limiter = make(clock)
    for k in "abc":
        limiter.check(k)
    clock.set(25)
    ran = threading.Event()
    original = limiter.cleanup

    def spy():
        original()
        ran.set()

    limiter.cleanup = spy  # type: ignore[method-assign]
    limiter.start_background_cleanup(0.01)
    try:
        assert ran.wait(timeout=5)
        assert len(limiter) == 0
    finally:
        limiter.stop_background_cleanup()


def test_background_cleanup_stops_cleanly_and_is_daemon(clock):
    limiter = make(clock)
    limiter.start_background_cleanup(0.01)
    thread = limiter._bg_thread
    assert thread is not None and thread.daemon is True
    limiter.stop_background_cleanup()
    # stop() must have joined the thread already: no extra join before checking.
    assert not thread.is_alive()


def test_stop_without_start_and_double_stop_are_noops(clock):
    limiter = make(clock)
    limiter.stop_background_cleanup()
    limiter.start_background_cleanup(0.01)
    limiter.stop_background_cleanup()
    limiter.stop_background_cleanup()


def test_double_start_keeps_one_thread_and_restart_works(clock):
    limiter = make(clock)
    limiter.start_background_cleanup(0.01)
    first = limiter._bg_thread
    limiter.start_background_cleanup(0.01)
    assert limiter._bg_thread is first
    limiter.stop_background_cleanup()
    limiter.start_background_cleanup(0.01)
    try:
        assert limiter._bg_thread is not first
        assert limiter._bg_thread.is_alive()
    finally:
        limiter.stop_background_cleanup()


@pytest.mark.parametrize("bad", [0, -1, float("nan")])
def test_bad_interval_is_rejected(clock, bad):
    limiter = make(clock)
    with pytest.raises(ValueError, match="interval"):
        limiter.start_background_cleanup(bad)
    assert limiter._bg_thread is None


def test_background_loop_survives_cleanup_errors(clock, caplog):
    limiter = make(clock)
    calls = threading.Event()
    count = [0]

    def flaky():
        count[0] += 1
        if count[0] >= 3:
            calls.set()
        raise RuntimeError("boom")

    limiter.cleanup = flaky  # type: ignore[method-assign]
    with caplog.at_level("ERROR"):
        limiter.start_background_cleanup(0.01)
        try:
            assert calls.wait(timeout=5)
        finally:
            limiter.stop_background_cleanup()
    assert "background cleanup failed" in caplog.text

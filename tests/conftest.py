"""Shared pytest fixtures: a controllable clock for deterministic time tests."""

from __future__ import annotations

import pytest


class FakeClock:
    """A zero-argument callable returning the current fake time in seconds."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        """Move time forward by ``seconds``."""
        self.now += seconds

    def set(self, t: float) -> None:
        """Jump to the absolute time ``t``."""
        self.now = float(t)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()

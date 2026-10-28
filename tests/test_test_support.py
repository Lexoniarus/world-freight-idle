"""Counter-tests for deterministic support boundaries."""

import pytest

from tests.support.manual_clock import ManualClock


def test_manual_clock_advances_without_accepting_invalid_intervals():
    source = [100.0]
    clock = ManualClock(lambda: source[0])

    assert clock() == 100
    assert clock.advance(25.5) == 125.5
    source[0] = 101
    assert clock() == 126.5
    for invalid in (0, -1, float("inf"), 86401):
        with pytest.raises(ValueError, match="out of range"):
            clock.advance(invalid)

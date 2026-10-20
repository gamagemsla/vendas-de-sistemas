"""Unit tests for SystemClock."""

from __future__ import annotations

from datetime import UTC

from vendas.infrastructure.clock import SystemClock


def test_system_clock_returns_aware_utc_datetime() -> None:
    clock = SystemClock()
    now = clock.now()

    # Must be datetime instance
    assert isinstance(now, __import__("datetime").datetime)

    # Must be timezone aware
    assert now.tzinfo is not None

    # Must be UTC (offset zero)
    assert now.utcoffset() is not None
    assert now.utcoffset().total_seconds() == 0

    # Equivalent to timezone.utc
    assert now.tzinfo == UTC or now.tzinfo.utcoffset(now) == UTC.utcoffset(now)

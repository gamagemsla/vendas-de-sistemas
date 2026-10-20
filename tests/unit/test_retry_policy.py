"""Unit tests for retry_policy (pure domain)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from vendas.domain.policies.retry_policy import calculate_backoff_delay, compute_next_retry_at


def test_calculate_backoff_delay_progression_no_jitter() -> None:
    # retry 1 -> 60s
    assert calculate_backoff_delay(1, jitter=False) == timedelta(seconds=60)
    # retry 2 -> 120s
    assert calculate_backoff_delay(2, jitter=False) == timedelta(seconds=120)
    # retry 3 -> 240s
    assert calculate_backoff_delay(3, jitter=False) == timedelta(seconds=240)
    # retry 4 -> 480s
    assert calculate_backoff_delay(4, jitter=False) == timedelta(seconds=480)
    # high retry -> capped at max_delay_seconds (3600)
    assert calculate_backoff_delay(10, jitter=False) == timedelta(seconds=3600)


def test_calculate_backoff_delay_jitter_adds_up_to_10_percent() -> None:
    # With jitter, delay should be between base and base*1.1
    for retry in range(1, 6):
        delay = calculate_backoff_delay(retry, jitter=True)
        base = calculate_backoff_delay(retry, jitter=False)
        assert delay >= base
        assert delay <= base * 1.10 + timedelta(seconds=1)  # small tolerance


def test_compute_next_retry_at_returns_future_datetime() -> None:
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    next_at = compute_next_retry_at(now, retry_count=1, jitter=False)
    assert next_at == now + timedelta(seconds=60)

    next_at2 = compute_next_retry_at(now, retry_count=2, jitter=False)
    assert next_at2 == now + timedelta(seconds=120)


def test_compute_next_retry_at_with_jitter_is_future() -> None:
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    next_at = compute_next_retry_at(now, retry_count=1, jitter=True)
    assert next_at > now
    # max with jitter 10% => 66 seconds
    assert next_at <= now + timedelta(seconds=66)


def test_invalid_retry_count_raises() -> None:
    with pytest.raises(ValueError):
        calculate_backoff_delay(0, jitter=False)
    with pytest.raises(ValueError):
        calculate_backoff_delay(-1, jitter=False)

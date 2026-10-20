"""Retry / Backoff policy (pure domain, no I/O)."""

from __future__ import annotations

import random
from datetime import datetime, timedelta


def calculate_backoff_delay(
    retry_count: int,
    base_delay_seconds: int = 60,
    max_delay_seconds: int = 3600,
    jitter: bool = True,
) -> timedelta:
    """
    Calculate exponential backoff delay (base 2).

    For retry_count >= 1:
        delay = min(base_delay_seconds * (2 ** (retry_count - 1)), max_delay_seconds)

    If jitter is True, add uniform random variation in [0, 10%] of the delay.
    """
    if retry_count < 1:
        raise ValueError("retry_count must be >= 1")

    delay = base_delay_seconds * (2 ** (retry_count - 1))
    delay = min(delay, max_delay_seconds)

    if jitter:
        # add up to 10% jitter
        jitter_amount = random.uniform(0, delay * 0.10)
        delay += jitter_amount

    return timedelta(seconds=delay)


def compute_next_retry_at(
    now: datetime,
    retry_count: int,
    base_delay_seconds: int = 60,
    max_delay_seconds: int = 3600,
    jitter: bool = True,
) -> datetime:
    """
    Return the datetime for the next retry attempt.

    now: timezone-aware datetime (UTC) from Clock port.
    """
    delay = calculate_backoff_delay(
        retry_count=retry_count,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        jitter=jitter,
    )
    return now + delay

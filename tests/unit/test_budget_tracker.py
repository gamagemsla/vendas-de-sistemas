"""Unit tests for FileBudgetTracker."""

from __future__ import annotations

import pytest

from tests.fakes.fakes import FakeClock
from vendas.domain.errors import BudgetExceededError
from vendas.domain.ports import BudgetTracker
from vendas.infrastructure.providers.budget_tracker import FileBudgetTracker


def test_budget_tracker_allows_consumption_within_limit(tmp_path) -> None:
    clock = FakeClock()
    tracker: BudgetTracker = FileBudgetTracker(
        provider_name="test",
        daily_limit=5,
        store_path=str(tmp_path / "budget.json"),
        clock=clock,
    )

    # Consume 3 units
    tracker.check_and_consume(1)
    tracker.check_and_consume(2)
    assert tracker.remaining() == 2


def test_budget_tracker_raises_when_exceeds_limit(tmp_path) -> None:
    clock = FakeClock()
    tracker: BudgetTracker = FileBudgetTracker(
        provider_name="test",
        daily_limit=3,
        store_path=str(tmp_path / "budget.json"),
        clock=clock,
    )

    tracker.check_and_consume(3)
    with pytest.raises(BudgetExceededError):
        tracker.check_and_consume(1)


def test_budget_tracker_resets_on_new_day(tmp_path) -> None:
    clock = FakeClock()
    tracker: BudgetTracker = FileBudgetTracker(
        provider_name="test",
        daily_limit=2,
        store_path=str(tmp_path / "budget.json"),
        clock=clock,
    )

    # Consume full budget on day 1
    tracker.check_and_consume(2)
    assert tracker.remaining() == 0

    # Advance clock to next day
    clock.advance_days(1)

    # Budget should reset
    assert tracker.remaining() == 2
    tracker.check_and_consume(1)
    assert tracker.remaining() == 1

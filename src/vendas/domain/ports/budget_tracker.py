"""Budget Tracker port for daily provider cost control."""

from __future__ import annotations

from typing import Protocol


class BudgetTracker(Protocol):
    """Port para controle de orçamento diário por provedor."""

    def check_and_consume(self, amount: int = 1) -> None:
        """Verifica e consome `amount` unidades do orçamento diário.

        Levanta BudgetExceededError se o consumo exceder o limite.
        """
        ...

    def remaining(self) -> int:
        """Retorna unidades restantes no dia corrente."""
        ...

from __future__ import annotations

from vendas.domain.ports import BudgetTracker
from vendas.domain.ports.budget import BudgetQueryPort


class SqlAlchemyBudgetQuery(BudgetQueryPort):
    """Implementação que agrega os trackers de orçamento dos provedores."""

    def __init__(
        self,
        apify_tracker: BudgetTracker,
        firecrawl_tracker: BudgetTracker,
        gemini_tracker: BudgetTracker,
    ) -> None:
        self._trackers = {
            "apify": apify_tracker,
            "firecrawl": firecrawl_tracker,
            "gemini": gemini_tracker,
        }

    def get_daily_costs(self) -> dict[str, int]:
        return {name: tracker.used_today() for name, tracker in self._trackers.items()}

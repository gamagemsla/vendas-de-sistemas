from __future__ import annotations

from vendas.domain.ports.budget import BudgetQueryPort


class GetDailyCostsQuery:
    def __init__(self, query_port: BudgetQueryPort) -> None:
        self._query_port = query_port

    def execute(self) -> dict[str, int]:
        return self._query_port.get_daily_costs()

from typing import Any

from vendas.domain.ports.dashboard import DashboardQueryPort


class GetOverviewKPIsQuery:
    def __init__(self, query_port: DashboardQueryPort) -> None:
        self._query_port = query_port

    def execute(self) -> dict[str, Any]:
        return self._query_port.get_overview_kpis()

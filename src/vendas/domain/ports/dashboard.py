from typing import Any, Protocol


class DashboardQueryPort(Protocol):
    def get_overview_kpis(self) -> dict[str, Any]: ...

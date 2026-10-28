from typing import Protocol


class BudgetQueryPort(Protocol):
    def get_daily_costs(self) -> dict[str, int]: ...

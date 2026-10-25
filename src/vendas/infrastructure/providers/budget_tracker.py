"""File-based budget tracker implementation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from vendas.domain.errors import BudgetExceededError
from vendas.domain.ports import BudgetTracker, Clock


class FileBudgetTracker(BudgetTracker):
    """Armazena contadores diários em arquivo JSON com escrita atômica."""

    def __init__(
        self,
        provider_name: str,
        daily_limit: int,
        store_path: str,
        clock: Clock,
    ) -> None:
        self._provider_name = provider_name
        self._daily_limit = daily_limit
        self._store_path = Path(store_path)
        self._clock = clock
        # Ensure directory exists
        self._store_path.parent.mkdir(parents=True, exist_ok=True)

    def _current_day_key(self) -> str:
        # Use clock to get current date in UTC (or configured tz)
        now = self._clock.now()
        return now.date().isoformat()

    def _load_budget(self) -> dict[str, int]:
        if not self._store_path.exists():
            return {}
        try:
            with self._store_path.open("r", encoding="utf-8") as f:
                data: Any = json.load(f)
                if isinstance(data, dict):
                    return {k: int(v) for k, v in data.items()}
                return {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_budget(self, data: dict[str, int]) -> None:
        tmp_path = self._store_path.with_suffix(self._store_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, self._store_path)

    def check_and_consume(self, amount: int = 1) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")
        day_key = self._current_day_key()
        budget = self._load_budget()
        used = budget.get(day_key, 0)
        if used + amount > self._daily_limit:
            raise BudgetExceededError(
                f"Orçamento diário de {self._daily_limit} execuções excedido para {self._provider_name} em {day_key}"
            )
        budget[day_key] = used + amount
        self._save_budget(budget)

    def remaining(self) -> int:
        day_key = self._current_day_key()
        budget = self._load_budget()
        used = budget.get(day_key, 0)
        return max(self._daily_limit - used, 0)

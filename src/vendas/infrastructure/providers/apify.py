import json
import os
import time
from collections.abc import Iterable
from datetime import date
from typing import Any

import httpx

from vendas.domain.errors import (
    BudgetExceededError,
    ProviderRateLimited,
    ProviderUnavailable,
)


class ApifyLeadSource:
    """Adaptador de infraestrutura para buscar leads no Apify (ex: Google Maps Scraper)."""

    def __init__(
        self,
        api_key: str,
        actor_id: str,
        client: httpx.Client | None = None,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        daily_budget: int = 100,
        budget_store_path: str = ".apify_budget.json",
    ) -> None:
        self._api_key = api_key
        self._actor_id = actor_id
        self._client = client or httpx.Client(timeout=timeout)
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._daily_budget = daily_budget
        self._budget_store_path = budget_store_path

    def _load_budget(self) -> dict[str, int]:
        if not os.path.exists(self._budget_store_path):
            return {}
        try:
            with open(self._budget_store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # json.load returns Any; ensure correct type
                if isinstance(data, dict):
                    return {k: int(v) for k, v in data.items()}
                return {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_budget(self, data: dict[str, int]) -> None:
        tmp_path = self._budget_store_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, self._budget_store_path)

    def _check_and_increment_budget(self) -> None:
        today = date.today().isoformat()
        budget = self._load_budget()
        used = budget.get(today, 0)
        if used >= self._daily_budget:
            raise BudgetExceededError(
                f"Orçamento diário de {self._daily_budget} execuções excedido para {today}"
            )
        budget[today] = used + 1
        self._save_budget(budget)

    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = self._client.request(method, url, **kwargs)
                if response.status_code == 429:
                    raise ProviderRateLimited("Rate limited by Apify (429)")
                if 500 <= response.status_code < 600:
                    raise ProviderUnavailable(f"Apify server error {response.status_code}")
                response.raise_for_status()
                return response
            except (httpx.RequestError, ProviderUnavailable, ProviderRateLimited) as exc:
                attempt += 1
                if attempt > self._max_retries:
                    if isinstance(exc, ProviderRateLimited):
                        raise
                    if isinstance(exc, ProviderUnavailable):
                        raise
                    raise ProviderUnavailable(
                        f"Network error after {self._max_retries} retries: {exc}"
                    ) from exc
                sleep_time = self._backoff_factor * (2 ** (attempt - 1))
                time.sleep(sleep_time)

    def search(self, query: dict[str, Any]) -> Iterable[dict[str, Any]]:
        self._check_and_increment_budget()

        run_url = f"https://api.apify.com/v2/acts/{self._actor_id}/runs"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        # Dispara a execução do ator no Apify
        run_response = self._request_with_retry("POST", run_url, json=query, headers=headers)
        run_data = run_response.json().get("data", {})
        dataset_id = run_data.get("defaultDatasetId")

        if not dataset_id:
            return []

        # Paginação do dataset
        items: list[dict[str, Any]] = []
        offset = 0
        limit = 1000
        while True:
            items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            params = {"offset": offset, "limit": limit, "clean": "true"}
            items_response = self._request_with_retry(
                "GET", items_url, headers=headers, params=params
            )
            page = items_response.json()
            if not isinstance(page, list) or not page:
                break
            items.extend(page)
            offset += limit

        return items

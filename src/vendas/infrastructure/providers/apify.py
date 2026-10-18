from collections.abc import Iterable
from typing import Any

import httpx


class ApifyLeadSource:
    """Adaptador de infraestrutura para buscar leads no Apify (ex: Google Maps Scraper)."""

    def __init__(self, api_key: str, actor_id: str, client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._actor_id = actor_id
        self._client = client or httpx.Client(timeout=30.0)

    def search(self, query_params: dict[str, Any]) -> Iterable[dict[str, Any]]:
        url = f"https://api.apify.com/v2/acts/{self._actor_id}/runs"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            # Dispara a execução do ator no Apify
            response = self._client.post(url, json=query_params, headers=headers)
            response.raise_for_status()
            run_data = response.json().get("data", {})
            dataset_id = run_data.get("defaultDatasetId")

            if not dataset_id:
                return []

            # Busca os itens do dataset gerado
            items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            items_response = self._client.get(items_url, headers=headers)
            items_response.raise_for_status()

            items = items_response.json()
            return items if isinstance(items, list) else []

        except httpx.HTTPError as e:
            # Erros de rede/provedor devem ser tratados ou mapeados para exceções de domínio
            raise RuntimeError(f"Erro ao comunicar com o provedor Apify: {e}") from e

from typing import Any

import httpx


class FirecrawlLeadEnricher:
    """Adaptador de infraestrutura para extração e enriquecimento de sites via Firecrawl."""

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=30.0)

    def enrich(self, website_url: str) -> dict[str, Any]:
        """Realiza o scraping e extração estruturada do site do lead."""
        api_url = "https://api.firecrawl.dev/v1/scrape"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": website_url,
            "formats": ["markdown"],
        }

        try:
            response = self._client.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            result = data.get("data", {})
            return dict(result) if isinstance(result, dict) else {}
        except httpx.HTTPError:
            # Degradação graciosa: se o Firecrawl falhar, retornamos dict vazio
            # para não perder o lead que já foi ingerido com sucesso.
            return {}

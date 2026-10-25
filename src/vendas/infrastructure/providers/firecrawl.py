from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from vendas.domain.errors import (
    BudgetExceededError,
    ProviderError,
    ProviderRateLimited,
    ProviderUnavailable,
)
from vendas.domain.policies.retry_policy import calculate_backoff_delay
from vendas.domain.ports import EnrichedLeadData, LeadEnricher
from vendas.domain.value_objects import Cnpj

logger = structlog.get_logger(__name__)


class FirecrawlLeadEnricher(LeadEnricher):
    """Adaptador de infraestrutura para extração e enriquecimento de sites via Firecrawl."""

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        max_retries: int = 3,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=30.0)
        self._max_retries = max_retries
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._circuit_breaker_timeout = circuit_breaker_timeout
        self._consecutive_failures = 0
        self._circuit_open_at: float | None = None

    @property
    def enricher_name(self) -> str:
        return "firecrawl"

    def _circuit_breaker_check(self) -> None:
        if self._circuit_open_at is not None:
            if time.monotonic() - self._circuit_open_at >= self._circuit_breaker_timeout:
                # half-open: allow a request
                self._circuit_open_at = None
                self._consecutive_failures = 0
                logger.info("firecrawl_circuit_breaker_half_open")
            else:
                raise ProviderUnavailable("Firecrawl circuit breaker open")

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_at = None

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_breaker_threshold:
            self._circuit_open_at = time.monotonic()
            logger.warning(
                "firecrawl_circuit_breaker_opened",
                failures=self._consecutive_failures,
            )

    def _map_http_error(self, exc: httpx.HTTPError) -> ProviderError:
        if isinstance(exc, httpx.TimeoutException):
            return ProviderUnavailable("Firecrawl timeout")
        response = getattr(exc, "response", None)
        if response is not None:
            status = response.status_code
            if status == 429:
                return ProviderRateLimited()
            if 500 <= status < 600:
                return ProviderUnavailable(f"Firecrawl server error {status}")
            if status == 402:
                return BudgetExceededError()
        return ProviderError(f"Firecrawl HTTP error: {exc}")

    def enrich(self, website_url: str) -> dict[str, Any] | None:
        """Realiza o scraping e extração estruturada do site do lead."""
        self._circuit_breaker_check()

        api_url = "https://api.firecrawl.dev/v1/scrape"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": website_url,
            "formats": ["markdown"],
        }

        attempt = 0
        while True:
            try:
                response = self._client.post(api_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                result = data.get("data", {})
                enrichment = dict(result) if isinstance(result, dict) else {}
                self._record_success()
                return enrichment
            except httpx.HTTPError as exc:
                provider_error = self._map_http_error(exc)
                self._record_failure()
                # Determine if retryable
                retryable = isinstance(provider_error, (ProviderUnavailable, ProviderRateLimited))
                if retryable and attempt < self._max_retries:
                    attempt += 1
                    delay = calculate_backoff_delay(retry_count=attempt)
                    logger.warning(
                        "firecrawl_retry",
                        attempt=attempt,
                        delay_seconds=delay.total_seconds(),
                        error=str(provider_error),
                    )
                    time.sleep(delay.total_seconds())
                    continue
                # Non-retryable or max retries reached
                logger.error("firecrawl_enrich_failed", error=str(provider_error))
                raise provider_error

    # --- Async protocol stubs -------------------------------------------------
    async def enrich_by_domain(self, domain: str) -> EnrichedLeadData | None:
        raise NotImplementedError("enrich_by_domain not implemented for Firecrawl")

    async def enrich_by_cnpj(self, cnpj: Cnpj) -> EnrichedLeadData | None:
        raise NotImplementedError("enrich_by_cnpj not implemented for Firecrawl")

    async def enrich_by_linkedin(self, linkedin_url: str) -> EnrichedLeadData | None:
        raise NotImplementedError("enrich_by_linkedin not implemented for Firecrawl")

    async def health_check(self) -> bool:
        # Simple health check: try a lightweight request to base URL
        try:
            resp = self._client.get("https://api.firecrawl.dev/v1/health", timeout=5.0)
            return resp.is_success
        except httpx.HTTPError:
            return False

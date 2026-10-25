"""Contract tests for FirecrawlLeadEnricher using httpx.MockTransport."""

from __future__ import annotations

import httpx
import pytest

from vendas.domain.errors import ProviderRateLimited, ProviderUnavailable
from vendas.infrastructure.providers.firecrawl import FirecrawlLeadEnricher


def _make_enricher(transport: httpx.BaseTransport, max_retries: int = 0) -> FirecrawlLeadEnricher:
    client = httpx.Client(transport=transport, timeout=5.0)
    return FirecrawlLeadEnricher(api_key="test-key", client=client, max_retries=max_retries)


def test_enrich_success_returns_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/scrape"
        return httpx.Response(
            200,
            json={"data": {"markdown": "# Hello", "title": "Test"}},
        )

    transport = httpx.MockTransport(handler)
    enricher = _make_enricher(transport)

    result = enricher.enrich("https://example.com")
    assert isinstance(result, dict)
    assert result["markdown"] == "# Hello"


def test_enrich_rate_limit_429_raises_provider_rate_limited() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "1"})

    transport = httpx.MockTransport(handler)
    enricher = _make_enricher(transport, max_retries=0)

    with pytest.raises(ProviderRateLimited):
        enricher.enrich("https://example.com")


def test_enrich_server_error_500_raises_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    enricher = _make_enricher(transport, max_retries=0)

    with pytest.raises(ProviderUnavailable):
        enricher.enrich("https://example.com")


def test_enrich_timeout_raises_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    transport = httpx.MockTransport(handler)
    enricher = _make_enricher(transport)

    with pytest.raises(ProviderUnavailable):
        enricher.enrich("https://example.com")


def test_circuit_breaker_opens_after_threshold() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    enricher = FirecrawlLeadEnricher(
        api_key="test-key",
        client=httpx.Client(transport=transport, timeout=5.0),
        max_retries=0,
        circuit_breaker_threshold=2,
        circuit_breaker_timeout=60.0,
    )

    # First two calls should raise ProviderUnavailable and increment failures
    with pytest.raises(ProviderUnavailable):
        enricher.enrich("https://example.com")
    with pytest.raises(ProviderUnavailable):
        enricher.enrich("https://example.com")

    # Third call should raise ProviderUnavailable due to open circuit
    with pytest.raises(ProviderUnavailable) as exc:
        enricher.enrich("https://example.com")
    assert "circuit breaker open" in str(exc.value).lower()

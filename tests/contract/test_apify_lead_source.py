"""Testes de contrato para ApifyLeadSource usando httpx.MockTransport (sem rede)."""

import json
from pathlib import Path

import httpx
import pytest

from vendas.domain.errors import (
    BudgetExceededError,
    ProviderRateLimited,
    ProviderUnavailable,
)
from vendas.infrastructure.providers.apify import ApifyLeadSource

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "apify"


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "apify"


def _load_fixture(name: str) -> dict | list:
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


class MockTransport(httpx.BaseTransport):
    """Transport que responde com fixtures pré-definidos baseados na URL.
    Suporta múltiplas respostas sequenciais para a mesma chave (path)."""

    def __init__(self, responses: dict[str, list[tuple[int, dict | list]]]) -> None:
        # each key maps to a list of (status, body) to be consumed in order
        self._responses = {k: list(v) for k, v in responses.items()}
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = f"{request.method} {request.url.path}"
        if self._responses.get(key):
            status, body = self._responses[key].pop(0)
            return httpx.Response(status_code=status, json=body)
        # default 404
        return httpx.Response(status_code=404, json={"error": "not found"})


def test_search_returns_paginated_leads():
    """Deve buscar leads paginando até esgotar dataset."""
    run_fixture = _load_fixture("run_success.json")
    page1 = _load_fixture("dataset_page1.json")
    page2 = _load_fixture("dataset_page2.json")
    page3 = _load_fixture("dataset_empty.json")

    responses = {
        "POST /v2/acts/test-actor/runs": [(200, run_fixture)],
        "GET /v2/datasets/dataset_456/items": [(200, page1), (200, page2), (200, page3)],
    }

    transport = MockTransport(responses)
    client = httpx.Client(transport=transport, timeout=5.0)

    source = ApifyLeadSource(
        api_key="test-key",
        actor_id="test-actor",
        client=client,
        daily_budget=10,
        budget_store_path=str(FIXTURES_DIR / "budget_test.json"),
    )

    leads = list(source.search({"search": "restaurantes"}))

    assert len(leads) == 3
    assert leads[0]["name"] == "Empresa Alpha"
    assert leads[1]["name"] == "Empresa Beta"
    assert leads[2]["name"] == "Empresa Gamma"

    # Verifica que fez 4 requests (1 run + 3 pages)
    assert len(transport.requests) == 4


def test_search_empty_dataset_returns_empty():
    run_fixture = _load_fixture("run_success.json")
    empty = _load_fixture("dataset_empty.json")

    responses = {
        "POST /v2/acts/test-actor/runs": [(200, run_fixture)],
        "GET /v2/datasets/dataset_456/items": [(200, empty)],
    }

    transport = MockTransport(responses)
    client = httpx.Client(transport=transport, timeout=5.0)

    source = ApifyLeadSource(
        api_key="test-key",
        actor_id="test-actor",
        client=client,
        daily_budget=10,
        budget_store_path=str(FIXTURES_DIR / "budget_test2.json"),
    )

    leads = list(source.search({"search": "vazio"}))
    assert leads == []


def test_search_rate_limited_raises_provider_rate_limited():
    run_fixture = _load_fixture("run_success.json")
    rate_limit_body = _load_fixture("http_429.json")

    responses = {
        "POST /v2/acts/test-actor/runs": [(200, run_fixture)],
        "GET /v2/datasets/dataset_456/items": [(429, rate_limit_body), (429, rate_limit_body)],
    }

    transport = MockTransport(responses)
    client = httpx.Client(transport=transport, timeout=5.0)

    source = ApifyLeadSource(
        api_key="test-key",
        actor_id="test-actor",
        client=client,
        max_retries=1,
        backoff_factor=0.01,
        daily_budget=10,
        budget_store_path=str(FIXTURES_DIR / "budget_test3.json"),
    )

    with pytest.raises(ProviderRateLimited):
        list(source.search({"search": "rate"}))


def test_search_server_error_raises_provider_unavailable():
    run_fixture = _load_fixture("run_success.json")
    error_body = _load_fixture("http_500.json")

    responses = {
        "POST /v2/acts/test-actor/runs": [(200, run_fixture)],
        "GET /v2/datasets/dataset_456/items": [(500, error_body), (500, error_body)],
    }

    transport = MockTransport(responses)
    client = httpx.Client(transport=transport, timeout=5.0)

    source = ApifyLeadSource(
        api_key="test-key",
        actor_id="test-actor",
        client=client,
        max_retries=1,
        backoff_factor=0.01,
        daily_budget=10,
        budget_store_path=str(FIXTURES_DIR / "budget_test4.json"),
    )

    with pytest.raises(ProviderUnavailable):
        list(source.search({"search": "error"}))


def test_budget_exceeded_raises_budget_exceeded_error(tmp_path):
    from datetime import date

    budget_file = tmp_path / "budget.json"
    today = date.today().isoformat()
    # Preenche budget com limite atingido para hoje
    budget_file.write_text(json.dumps({today: 5}), encoding="utf-8")

    run_fixture = _load_fixture("run_success.json")
    responses = {
        "POST /v2/acts/test-actor/runs": (200, run_fixture),
    }

    transport = MockTransport(responses)
    client = httpx.Client(transport=transport, timeout=5.0)

    source = ApifyLeadSource(
        api_key="test-key",
        actor_id="test-actor",
        client=client,
        daily_budget=5,
        budget_store_path=str(budget_file),
    )

    with pytest.raises(BudgetExceededError):
        list(source.search({"search": "budget"}))

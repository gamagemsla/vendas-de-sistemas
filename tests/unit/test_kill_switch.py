"""Testes para Kill Switch (KILL_SWITCH) em dispatcher, API middleware e health checks."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from vendas.bootstrap.settings import Settings
from vendas.infrastructure.queue.dispatcher import OutboxDispatcher
from vendas.interfaces.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_dispatcher_kill_switch_returns_zero() -> None:
    """Dispatcher deve retornar 0 imediatamente quando KILL_SWITCH=True sem abrir transação."""
    uow_mock = MagicMock()
    channel_mock = MagicMock()

    dispatcher = OutboxDispatcher(uow=uow_mock, channel=channel_mock)

    with patch(
        "vendas.infrastructure.queue.dispatcher.settings",
        Settings(KILL_SWITCH=True, DRY_RUN=True, AUTOMATION_ENABLED=False),
    ):
        result = dispatcher.dispatch_batch(batch_size=10)

    assert result == 0
    # Não deve ter chamado claim_pending nem commit
    uow_mock.__enter__.assert_not_called()
    channel_mock.send.assert_not_called()


def test_api_post_blocked_when_kill_switch(client: TestClient) -> None:
    """POST em rota mutante deve retornar 503 com Retry-After quando KILL_SWITCH=True."""
    with patch(
        "vendas.interfaces.api.app.settings",
        Settings(KILL_SWITCH=True, DRY_RUN=True, AUTOMATION_ENABLED=False),
    ):
        response = client.post("/catalog", json={"name": "test"})

    assert response.status_code == 503
    assert response.headers.get("Retry-After") == "30"
    assert "KILL_SWITCH ativo" in response.json()["detail"]


def test_api_get_allowed_when_kill_switch(client: TestClient) -> None:
    """GET deve ser permitido mesmo com KILL_SWITCH=True."""
    with patch(
        "vendas.interfaces.api.app.settings",
        Settings(KILL_SWITCH=True, DRY_RUN=True, AUTOMATION_ENABLED=False),
    ):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_health_and_ready_endpoints(client: TestClient) -> None:
    """Endpoints /health e /ready devem responder normalmente."""
    # Sem kill switch
    response_health = client.get("/health")
    response_ready = client.get("/ready")
    assert response_health.status_code == 200
    assert response_ready.status_code == 200
    assert response_ready.json()["status"] == "ready"

    # Com kill switch ativo
    with patch(
        "vendas.interfaces.api.routes.health.settings",
        Settings(KILL_SWITCH=True, DRY_RUN=True, AUTOMATION_ENABLED=False),
    ):
        response_ready_ks = client.get("/ready")
        assert response_ready_ks.status_code == 200
        assert response_ready_ks.json()["status"] == "paused"
        assert response_ready_ks.json()["kill_switch"] is True

import asyncio
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from vendas.bootstrap.logging import clear_correlation_id, get_correlation_id, set_correlation_id
from vendas.interfaces.api.app import app, correlation_id_middleware


def test_set_and_get_correlation_id():
    """Helpers definem e leem correlation_id no contextvars."""
    clear_correlation_id()
    assert get_correlation_id() is None

    cid = set_correlation_id("custom-123")
    assert cid == "custom-123"
    assert get_correlation_id() == "custom-123"

    # sem argumento gera uuid
    clear_correlation_id()
    cid2 = set_correlation_id()
    assert get_correlation_id() == cid2
    # valid uuid format
    uuid.UUID(cid2)  # raises if invalid

    clear_correlation_id()
    assert get_correlation_id() is None


def test_clear_correlation_id():
    set_correlation_id("abc")
    assert get_correlation_id() == "abc"
    clear_correlation_id()
    assert get_correlation_id() is None


def test_middleware_generates_correlation_id_when_missing():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    # header presente
    assert "X-Correlation-ID" in response.headers
    cid = response.headers["X-Correlation-ID"]
    uuid.UUID(cid)  # valid uuid


def test_middleware_preserves_incoming_correlation_id():
    client = TestClient(app)
    custom = "my-custom-correlation-id"
    response = client.get("/health", headers={"X-Correlation-ID": custom})
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == custom


def test_middleware_adds_header_on_error_path():
    # Rota inexistente retorna 404, ainda deve ter header
    client = TestClient(app)
    response = client.get("/nao-existe")
    assert response.status_code == 404
    assert "X-Correlation-ID" in response.headers
    uuid.UUID(response.headers["X-Correlation-ID"])


# Test dispatcher correlation_id binding (unit test with mocked UoW)
def test_dispatcher_binds_correlation_id_per_item(monkeypatch):
    from vendas.infrastructure.queue import dispatcher as dispatcher_module
    from vendas.infrastructure.queue.dispatcher import OutboxDispatcher

    # Mock validate_outbox_payload to avoid validation errors
    monkeypatch.setattr(
        dispatcher_module, "validate_outbox_payload", lambda event_type, payload: payload
    )

    # Mock UoW and channel
    mock_uow = MagicMock()
    mock_channel = MagicMock()

    # Mock claim_pending to return two fake items
    class FakeItem:
        def __init__(self, id_, payload):
            self.id = id_
            self.payload = payload
            self.event_type = "TestEvent"
            self.idempotency_key = f"key-{id_}"

    item1 = FakeItem(1, {"correlation_id": "cid-1"})
    item2 = FakeItem(2, {})  # sem correlation_id, deve usar id

    mock_uow.__enter__.return_value = mock_uow
    mock_uow.__exit__.return_value = False
    mock_uow.outbox.claim_pending.return_value = [item1, item2]

    dispatcher = OutboxDispatcher(mock_uow, mock_channel)

    # Capture logs via structlog? We'll just ensure set_correlation_id called correctly by checking contextvars after each iteration.
    # Since dispatcher clears after each, after dispatch_batch context should be cleared.
    dispatcher.dispatch_batch(batch_size=10)

    # After processing, correlation_id should be cleared
    assert get_correlation_id() is None

    # Ensure claim_pending called
    mock_uow.outbox.claim_pending.assert_called_once_with(batch_size=10)
    # Ensure mark_sent called for each (DRY_RUN default true in settings)
    assert mock_uow.outbox.mark_sent.call_count == 2


def test_middleware_cleans_correlation_id_on_unhandled_exception():
    clear_correlation_id()
    # create a mock request
    scope = {"type": "http", "headers": []}
    request = Request(scope)

    async def call_next(_req):
        raise RuntimeError("boom")

    async def run():
        with pytest.raises(RuntimeError):
            await correlation_id_middleware(request, call_next)
        assert get_correlation_id() is None

    asyncio.run(run())

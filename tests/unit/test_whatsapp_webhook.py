import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from vendas.bootstrap.settings import settings
from vendas.domain.ports import ChannelStatePort, Clock, JobQueue, UnitOfWork
from vendas.interfaces.api.app import create_app
from vendas.interfaces.api.deps import get_channel_state_port, get_clock, get_job_queue, get_uow


@pytest.fixture
def client():
    app = create_app(auth_port=None)
    return TestClient(app)


@pytest.fixture
def mock_uow():
    uow = MagicMock(spec=UnitOfWork)
    uow.inbound_events = MagicMock()
    uow.inbound_events.exists.return_value = False
    uow.inbound_events.add = MagicMock()
    uow.leads = MagicMock()
    uow.leads.find_by_dedupe_key.return_value = None
    uow.conversations = MagicMock()
    uow.conversations.get_by_lead_id.return_value = None
    uow.conversations.add = MagicMock()
    uow.conversations.save = MagicMock()
    uow.outbox = MagicMock()
    uow.outbox.exists_by_provider_message_id.return_value = False
    uow.commit = MagicMock()
    uow.__enter__ = MagicMock(return_value=uow)
    uow.__exit__ = MagicMock(return_value=False)
    return uow


@pytest.fixture
def mock_job_queue():
    return AsyncMock(spec=JobQueue)


@pytest.fixture
def mock_clock():
    clock = MagicMock(spec=Clock)
    clock.now.return_value = "2024-01-01T00:00:00+00:00"
    return clock


@pytest.fixture
def mock_channel_state_port():
    port = MagicMock(spec=ChannelStatePort)
    port.is_connected.return_value = True
    port.set_connection_state = MagicMock()
    port.set_qr_pending = MagicMock()
    return port


def _sign(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _override_deps(client, uow, job_queue, clock, channel_state_port):
    client.app.dependency_overrides[get_uow] = lambda: uow
    client.app.dependency_overrides[get_job_queue] = lambda: job_queue
    client.app.dependency_overrides[get_clock] = lambda: clock
    client.app.dependency_overrides[get_channel_state_port] = lambda: channel_state_port


def test_webhook_valid_signature_enqueues_job(
    client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port
):
    settings.WEBHOOK_SECRET = "testsecret"
    _override_deps(client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port)

    payload = {
        "event": "MESSAGES-upsert",
        "instance": "test",
        "data": {
            "key": {"id": "msg-123", "remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False},
            "message": {"conversation": "Olá"},
        },
    }
    body = json.dumps(payload).encode()
    headers = {"X-Hub-Signature-256": _sign(body, "testsecret"), "Content-Type": "application/json"}

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message_id"] == "msg-123"
    mock_uow.inbound_events.add.assert_called_once()
    mock_uow.commit.assert_called_once()
    mock_job_queue.enqueue.assert_awaited_once()


def test_webhook_invalid_signature_returns_error(
    client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port
):
    settings.WEBHOOK_SECRET = "testsecret"
    _override_deps(client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port)

    payload = {
        "event": "MESSAGES-upsert",
        "data": {
            "key": {"id": "msg-1", "remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False},
            "message": {"conversation": "Oi"},
        },
    }
    body = json.dumps(payload).encode()
    headers = {"X-Hub-Signature-256": "sha256=invalido", "Content-Type": "application/json"}

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert response.json()["detail"] == "Invalid signature"


def test_webhook_duplicate_message_ignored(
    client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port
):
    settings.WEBHOOK_SECRET = "testsecret"
    mock_uow.inbound_events.exists.return_value = True
    _override_deps(client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port)

    payload = {
        "event": "MESSAGES-upsert",
        "instance": "test",
        "data": {
            "key": {"id": "msg-123", "remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False},
            "message": {"conversation": "Olá"},
        },
    }
    body = json.dumps(payload).encode()
    headers = {"X-Hub-Signature-256": _sign(body, "testsecret"), "Content-Type": "application/json"}

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["deduped"] is True
    mock_uow.inbound_events.add.assert_not_called()
    mock_job_queue.enqueue.assert_not_awaited()


def test_webhook_group_message_ignored(
    client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port
):
    settings.WEBHOOK_SECRET = "testsecret"
    _override_deps(client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port)

    payload = {
        "event": "MESSAGES-upsert",
        "instance": "test",
        "data": {
            "key": {"id": "msg-group", "remoteJid": "5511999999999-123456@g.us", "fromMe": False},
            "message": {"conversation": "Mensagem de grupo"},
        },
    }
    json.dumps(payload).encode()


def test_webhook_connection_update_close_sets_disconnected(
    client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port
):
    settings.WEBHOOK_SECRET = "testsecret"
    _override_deps(client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port)

    payload = {
        "event": "CONNECTION_UPDATE",
        "instance": "test",
        "data": {"state": "close"},
    }
    body = json.dumps(payload).encode()
    headers = {"X-Hub-Signature-256": _sign(body, "testsecret"), "Content-Type": "application/json"}

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_webhook_connection_update_open_sets_connected(
    client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port
):
    settings.WEBHOOK_SECRET = "testsecret"
    _override_deps(client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port)

    payload = {
        "event": "CONNECTION_UPDATE",
        "instance": "test",
        "data": {"state": "open"},
    }
    body = json.dumps(payload).encode()
    headers = {"X-Hub-Signature-256": _sign(body, "testsecret"), "Content-Type": "application/json"}

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_webhook_qrcode_updated_sets_qr_pending(
    client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port
):
    settings.WEBHOOK_SECRET = "testsecret"
    _override_deps(client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port)

    payload = {
        "event": "QRCODE_UPDATED",
        "instance": "test",
        "data": {"qrcode": "qr-code-data"},
    }
    body = json.dumps(payload).encode()
    headers = {"X-Hub-Signature-256": _sign(body, "testsecret"), "Content-Type": "application/json"}

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_webhook_from_me_takeover_detected(
    client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port
):
    settings.WEBHOOK_SECRET = "testsecret"
    # Configura mocks para simular lead existente e conversa
    mock_lead = MagicMock()
    mock_lead.id = "lead-123"
    mock_uow.leads.find_by_dedupe_key.return_value = mock_lead
    mock_conversation = MagicMock()
    mock_conversation.id = "conv-123"
    mock_uow.conversations.get_by_lead_id.return_value = None  # não existe, será criada
    mock_uow.conversations.add = MagicMock()
    mock_uow.conversations.save = MagicMock()
    mock_uow.commit = MagicMock()
    # outbox não tem o message_id (não é echo do bot)
    mock_uow.outbox = MagicMock()
    mock_uow.outbox.exists_by_provider_message_id.return_value = False

    _override_deps(client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port)

    payload = {
        "event": "MESSAGES-upsert",
        "instance": "test",
        "data": {
            "key": {
                "id": "msg-takeover",
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": True,
            },
            "message": {"conversation": "Mensagem do operador"},
        },
    }
    body = json.dumps(payload).encode()
    headers = {"X-Hub-Signature-256": _sign(body, "testsecret"), "Content-Type": "application/json"}

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event"] == "takeover_detected"
    # Verifica que conversa foi criada e salva
    mock_uow.conversations.add.assert_called_once()
    mock_uow.conversations.save.assert_called_once()
    mock_uow.commit.assert_called_once()


def test_webhook_from_me_echo_ignored(
    client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port
):
    settings.WEBHOOK_SECRET = "testsecret"
    # outbox tem o message_id (é echo do bot)
    mock_uow.outbox = MagicMock()
    mock_uow.outbox.exists_by_provider_message_id.return_value = True

    _override_deps(client, mock_uow, mock_job_queue, mock_clock, mock_channel_state_port)

    payload = {
        "event": "MESSAGES-upsert",
        "instance": "test",
        "data": {
            "key": {"id": "msg-echo", "remoteJid": "5511999999999@s.whatsapp.net", "fromMe": True},
            "message": {"conversation": "Echo do bot"},
        },
    }
    body = json.dumps(payload).encode()
    headers = {"X-Hub-Signature-256": _sign(body, "testsecret"), "Content-Type": "application/json"}

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "acknowledged"
    assert data["type"] == "outbound_echo"
    # Não deve criar lead nem conversa
    mock_uow.leads.find_by_dedupe_key.assert_not_called()
    mock_uow.conversations.add.assert_not_called()
    mock_uow.conversations.save.assert_not_called()
    mock_uow.commit.assert_not_called()

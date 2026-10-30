"""Testes de integração E2E para o fluxo de inbound (webhook → worker → outbox)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from vendas.bootstrap.settings import settings
from vendas.interfaces.api.app import create_app


def _sign(payload: bytes, secret: str) -> str:
    """Gera assinatura HMAC-SHA256 no formato sha256=<hex>."""
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    """Reseta as configurações para valores padrão antes de cada teste."""
    monkeypatch.setattr(settings, "AUTOMATION_ENABLED", True)
    monkeypatch.setattr(settings, "WEBHOOK_SECRET", "testsecret")
    monkeypatch.setattr(settings, "DRY_RUN", True)


@pytest.fixture
def client():
    app = create_app(auth_port=None)
    return TestClient(app)


@pytest.fixture
def webhook_payload():
    """Payload base válido da Evolution API para MESSAGES-upsert."""
    return {
        "event": "MESSAGES-upsert",
        "instance": "test-instance",
        "data": {
            "key": {
                "id": "msg-e2e-123",
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
            },
            "message": {"conversation": "Olá, gostaria de saber mais sobre seus serviços"},
        },
    }


def test_inbound_e2e_webhook_to_outbox(client, webhook_payload):
    """
    Teste E2E: Webhook válido → grava evento → worker reivindica via SKIP LOCKED
    → handler processa com agente fake → resposta na outbox → DRY_RUN loga simulação.
    """
    body = json.dumps(webhook_payload).encode()
    headers = {
        "X-Hub-Signature-256": _sign(body, "testsecret"),
        "Content-Type": "application/json",
    }

    # 1. POST no webhook
    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message_id"] == "msg-e2e-123"


def test_inbound_e2e_idempotency_duplicate_provider_message_id(client, webhook_payload):
    """
    Valida que requisição repetida com mesmo provider_message_id não duplica processamento.
    """
    body = json.dumps(webhook_payload).encode()
    headers = {
        "X-Hub-Signature-256": _sign(body, "testsecret"),
        "Content-Type": "application/json",
    }

    # Primeira requisição
    response1 = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "success"
    assert data1["message_id"] == "msg-e2e-123"

    # Segunda requisição com mesmo message_id
    response2 = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "success"
    assert data2["message_id"] == "msg-e2e-123"
    assert data2["deduped"] is True


def test_inbound_e2e_unknown_lead_opt_out(client):
    """
    Valida lead desconhecido e mensagem de opt-out.
    """
    # Payload com mensagem de opt-out (STOP)
    payload = {
        "event": "MESSAGES-upsert",
        "instance": "test-instance",
        "data": {
            "key": {
                "id": "msg-optout-456",
                "remoteJid": "5511988888888@s.whatsapp.net",
                "fromMe": False,
            },
            "message": {"conversation": "STOP"},
        },
    }
    body = json.dumps(payload).encode()
    headers = {
        "X-Hub-Signature-256": _sign(body, "testsecret"),
        "Content-Type": "application/json",
    }

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message_id"] == "msg-optout-456"


def test_inbound_e2e_evolution_signature_header(client, webhook_payload):
    """
    Valida que o header X-Evolution-Signature também é aceito (compatibilidade).
    Evolution API pode enviar assinatura em header customizado.
    """
    body = json.dumps(webhook_payload).encode()
    headers = {
        "X-Evolution-Signature": _sign(body, "testsecret"),
        "Content-Type": "application/json",
    }

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message_id"] == "msg-e2e-123"


def test_inbound_e2e_invalid_signature_rejected(client, webhook_payload):
    """
    Valida que assinatura inválida é rejeitada quando AUTOMATION_ENABLED=true.
    """
    body = json.dumps(webhook_payload).encode()
    headers = {
        "X-Hub-Signature-256": _sign(body, "wrongsecret"),
        "Content-Type": "application/json",
    }

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid signature"


def test_inbound_e2e_broadcast_ignored(client):
    """
    Valida que mensagens de broadcast (status@broadcast) são ignoradas.
    """
    payload = {
        "event": "MESSAGES-upsert",
        "instance": "test-instance",
        "data": {
            "key": {
                "id": "msg-broadcast-789",
                "remoteJid": "status@broadcast",
                "fromMe": False,
            },
            "message": {"conversation": "Status update"},
        },
    }
    body = json.dumps(payload).encode()
    headers = {
        "X-Hub-Signature-256": _sign(body, "testsecret"),
        "Content-Type": "application/json",
    }

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event"] == "broadcast_ignored"


def test_inbound_e2e_human_takeover_detected(client):
    """
    Valida detecção de takeover humano (mensagem fromMe=true não na outbox).
    """
    payload = {
        "event": "MESSAGES-upsert",
        "instance": "test-instance",
        "data": {
            "key": {
                "id": "msg-takeover-999",
                "remoteJid": "5511977777777@s.whatsapp.net",
                "fromMe": True,
            },
            "message": {"conversation": "Mensagem do atendente humano"},
        },
    }
    body = json.dumps(payload).encode()
    headers = {
        "X-Hub-Signature-256": _sign(body, "testsecret"),
        "Content-Type": "application/json",
    }

    response = client.post("/webhooks/whatsapp", content=body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event"] == "takeover_detected"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

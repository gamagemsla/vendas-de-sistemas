"""Testes de contrato para EvolutionWhatsAppChannel (sem rede real)."""

import json

import httpx
import pytest

from vendas.domain.errors import ProviderError, ProviderRateLimited, ProviderUnavailable
from vendas.infrastructure.channels.evolution_whatsapp import EvolutionWhatsAppChannel


def _make_channel(transport: httpx.MockTransport) -> EvolutionWhatsAppChannel:
    client = httpx.Client(transport=transport, timeout=30.0)
    return EvolutionWhatsAppChannel(
        base_url="http://testserver",
        api_key="test-key",
        instance_name="default",
        client=client,
    )


def test_send_success_with_presence() -> None:
    """Envio bem-sucedido deve retornar JSON da API e incluir presença no payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/message/sendText/default"
        body = json.loads(request.content.decode())
        assert body["number"] == "5511999999999"
        assert body["textMessage"]["text"] == "Olá"
        assert body["options"]["presence"] == "composing"
        assert body["options"]["delay"] == 1200
        return httpx.Response(200, json={"id": "msg-123", "status": "sent"})

    transport = httpx.MockTransport(handler)
    channel = _make_channel(transport)

    result = channel.send({"phone": "5511999999999", "content": "Olá"})
    assert result == {"id": "msg-123", "status": "sent"}


def test_check_whatsapp_true() -> None:
    """Verificação de número existente retorna True."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/chat/whatsappNumbers/default"
        body = json.loads(request.content.decode())
        assert body == {"numbers": ["5511999999999"]}
        return httpx.Response(
            200,
            json={"numbers": [{"number": "5511999999999", "exists": True}]},
        )

    transport = httpx.MockTransport(handler)
    channel = _make_channel(transport)

    assert channel.check_whatsapp("5511999999999") is True


def test_check_whatsapp_false() -> None:
    """Verificação de número inexistente retorna False."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/chat/whatsappNumbers/default"
        return httpx.Response(
            200,
            json={"numbers": [{"number": "5511999999999", "exists": False}]},
        )

    transport = httpx.MockTransport(handler)
    channel = _make_channel(transport)

    assert channel.check_whatsapp("5511999999999") is False


def test_send_rate_limited_raises_provider_rate_limited() -> None:
    """HTTP 429 deve lançar ProviderRateLimited."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    transport = httpx.MockTransport(handler)
    channel = _make_channel(transport)

    with pytest.raises(ProviderRateLimited):
        channel.send({"phone": "5511999999999", "content": "teste"})


def test_send_server_error_raises_provider_unavailable() -> None:
    """HTTP 500 deve lançar ProviderUnavailable."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal"})

    transport = httpx.MockTransport(handler)
    channel = _make_channel(transport)

    with pytest.raises(ProviderUnavailable):
        channel.send({"phone": "5511999999999", "content": "teste"})


def test_send_timeout_raises_provider_unavailable() -> None:
    """Timeout de rede deve lançar ProviderUnavailable."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    transport = httpx.MockTransport(handler)
    channel = _make_channel(transport)

    with pytest.raises(ProviderUnavailable):
        channel.send({"phone": "5511999999999", "content": "teste"})


def test_send_client_error_raises_provider_error() -> None:
    """HTTP 400 (exceto 429) deve lançar ProviderError genérico."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad request"})

    transport = httpx.MockTransport(handler)
    channel = _make_channel(transport)

    with pytest.raises(ProviderError):
        channel.send({"phone": "5511999999999", "content": "teste"})


def test_check_whatsapp_unexpected_format_returns_false() -> None:
    """Formato de resposta inesperado deve retornar False sem lançar."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "format"})

    transport = httpx.MockTransport(handler)
    channel = _make_channel(transport)

    assert channel.check_whatsapp("5511999999999") is False

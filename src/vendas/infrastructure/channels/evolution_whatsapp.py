from typing import Any

import httpx

from vendas.domain.errors import ProviderError, ProviderRateLimited, ProviderUnavailable


class EvolutionWhatsAppChannel:
    """Adaptador de infraestrutura para envio de mensagens via Evolution API (WhatsApp)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        instance_name: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._instance_name = instance_name
        self._client = client or httpx.Client(timeout=30.0)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._api_key,
            "Content-Type": "application/json",
        }

    def _request(
        self, method: str, url: str, *, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, url, json=json, headers=self._headers())
            # Mapear status codes para exceções de domínio
            if response.status_code == 429:
                raise ProviderRateLimited("Rate limit excedido na Evolution API")
            if 500 <= response.status_code < 600:
                raise ProviderUnavailable(
                    f"Evolution API indisponível (HTTP {response.status_code})"
                )
            if 400 <= response.status_code < 500:
                raise ProviderError(
                    f"Erro da Evolution API (HTTP {response.status_code}): {response.text}"
                )
            response.raise_for_status()
            return dict(response.json())
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable("Timeout ao chamar Evolution API") from exc
        except httpx.ConnectError as exc:
            raise ProviderUnavailable("Erro de conexão com Evolution API") from exc
        except httpx.RequestError as exc:
            raise ProviderUnavailable(f"Erro de requisição para Evolution API: {exc}") from exc

    # ------------------------------------------------------------------
    # Port MessageChannel
    # ------------------------------------------------------------------
    def send(self, msg_payload: dict[str, Any]) -> dict[str, Any]:
        phone = msg_payload.get("phone")
        content = msg_payload.get("content")

        if not phone or not content:
            raise ValueError("Payload de envio inválido: telefone ou conteúdo ausentes.")

        url = f"{self._base_url}/message/sendText/{self._instance_name}"
        body = {
            "number": phone,
            "textMessage": {
                "text": content,
            },
            "options": {
                "delay": 1200,  # Atraso simulando digitação humana (ms)
                "presence": "composing",
            },
        }

        return self._request("POST", url, json=body)

    # ------------------------------------------------------------------
    # Verificação de número WhatsApp (F4-02)
    # ------------------------------------------------------------------
    def check_whatsapp(self, phone: str) -> bool:
        """Consulta a Evolution API para confirmar se o número possui WhatsApp ativo."""
        url = f"{self._base_url}/chat/whatsappNumbers/{self._instance_name}"
        payload = {"numbers": [phone]}
        result = self._request("POST", url, json=payload)
        # A Evolution retorna uma lista de objetos com campo "exists" (bool)
        try:
            numbers_info = result.get("numbers") or result.get("data") or []
            for info in numbers_info:
                if info.get("number") == phone and info.get("exists") is True:
                    return True
            return False
        except (AttributeError, KeyError, TypeError):
            # Em caso de formato inesperado, considerar como não existente
            return False

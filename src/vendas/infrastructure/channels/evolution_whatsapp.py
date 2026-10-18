from typing import Any

import httpx


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

    def send(self, msg_payload: dict[str, Any]) -> dict[str, Any]:
        phone = msg_payload.get("phone")
        content = msg_payload.get("content")

        if not phone or not content:
            raise ValueError("Payload de envio inválido: telefone ou conteúdo ausentes.")

        url = f"{self._base_url}/message/sendText/{self._instance_name}"
        headers = {
            "apikey": self._api_key,
            "Content-Type": "application/json",
        }
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

        try:
            response = self._client.post(url, json=body, headers=headers)
            response.raise_for_status()
            return dict(response.json())
        except httpx.HTTPError as e:
            raise RuntimeError(f"Falha ao enviar mensagem via Evolution API: {e}") from e

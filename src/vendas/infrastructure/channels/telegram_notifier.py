import httpx
import structlog

logger = structlog.get_logger()


class TelegramNotifier:
    """Adaptador de infraestrutura para envio de alertas em tempo real via Bot do Telegram."""

    def __init__(self, bot_token: str, chat_id: str, client: httpx.Client | None = None) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._client = client or httpx.Client(timeout=10.0)

    def send_alert(self, message: str) -> bool:
        """Envia uma mensagem de texto formatada (Markdown) para o chat/canal do Telegram."""
        if not self._bot_token or not self._chat_id:
            logger.warning("telegram_credenciais_ausentes_alerta_ignorado")
            return False

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }

        try:
            response = self._client.post(url, json=payload)
            response.raise_for_status()
            logger.info("alerta_telegram_enviado_com_sucesso")
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("falha_envio_alerta_telegram", error=str(e))
            return False

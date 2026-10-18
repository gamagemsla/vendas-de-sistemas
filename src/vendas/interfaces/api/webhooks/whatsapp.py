import structlog
from fastapi import APIRouter, Request, status

logger = structlog.get_logger()

router = APIRouter(prefix="/webhooks/whatsapp", tags=["Webhooks WhatsApp"])


@router.post("", status_code=status.HTTP_200_OK)
async def receive_whatsapp_webhook(request: Request) -> dict[str, str]:
    """Endpoint receptor para eventos da Evolution API (inbound messages, status, etc.)."""
    try:
        payload = await request.json()
    except (TypeError, ValueError):
        return {"status": "error", "detail": "Invalid JSON payload"}

    event_type = payload.get("event")
    instance = payload.get("instance")

    logger.info("webhook_whatsapp_recebido", event_type=event_type, instance=instance)

    # Ignora eventos que não sejam de mensagens upsert (como status de conexão brutos se necessário)
    if event_type != "MESSAGES-upsert":
        return {"status": "ignored", "reason": "event_type_not_handled"}

    data = payload.get("data", {})
    message_id = data.get("key", {}).get("id")
    remote_jid = data.get("key", {}).get("remoteJid")
    from_me = data.get("key", {}).get("fromMe", False)

    # Se a mensagem foi enviada por nós mesmos (fromMe), tratamos apenas como confirmação de envio
    if from_me:
        return {"status": "acknowledged", "type": "outbound_echo"}

    # Extrai o texto da mensagem (suportando conversation ou extendedTextMessage)
    message_content = (
        data.get("message", {}).get("conversation")
        or data.get("message", {}).get("extendedTextMessage", {}).get("text")
        or ""
    )

    logger.info(
        "mensagem_inbound_capturada",
        message_id=message_id,
        remote_jid=remote_jid,
        content_preview=message_content[:30],
    )

    # Aqui a arquitetura grava o evento em `inbound_events` com provider_message_id único (dedupe)
    # e enfileira o comando `handle_inbound` para processamento pelo worker.

    return {"status": "success", "message_id": message_id}

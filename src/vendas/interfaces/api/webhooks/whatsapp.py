import hashlib
import hmac
from typing import Any

import structlog
from fastapi import APIRouter, Header, Request, status
from sqlalchemy.exc import IntegrityError

from vendas.bootstrap.settings import settings
from vendas.domain.entities.conversation import Conversation
from vendas.domain.entities.inbound_event import InboundEvent
from vendas.domain.ports import ChannelStatePort, Clock, UnitOfWork
from vendas.interfaces.api.deps import channel_state_dep, clock_dep, uow_dep

logger = structlog.get_logger()

router = APIRouter(prefix="/webhooks/whatsapp", tags=["Webhooks WhatsApp"])


def _verify_signature(body: bytes, signature_header: str | None) -> bool:
    """Valida assinatura HMAC-SHA256 em tempo constante."""
    secret = settings.WEBHOOK_SECRET
    if not secret:
        # Sem secret configurado: em dev/testes aceita; em produção deve ser configurado.
        return True
    if not signature_header:
        return False
    # Espera formato "sha256=<hex>"
    try:
        algo, received = signature_header.split("=", 1)
    except ValueError:
        return False
    if algo.lower() != "sha256":
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


@router.post("", status_code=status.HTTP_200_OK)
async def receive_whatsapp_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_evolution_signature: str | None = Header(default=None, alias="X-Evolution-Signature"),
    uow: UnitOfWork = uow_dep,
    clock: Clock = clock_dep,
    channel_state_port: ChannelStatePort = channel_state_dep,
) -> dict[str, Any]:
    """Endpoint receptor para eventos da Evolution API (inbound messages, status, etc.)."""
    # Lê corpo bruto para validação de assinatura
    body = await request.body()
    signature = x_hub_signature_256 or x_evolution_signature
    if not _verify_signature(body, signature):
        logger.warning("webhook_assinatura_invalida")
        return {"status": "error", "detail": "Invalid signature"}

    try:
        payload = await request.json()
    except (TypeError, ValueError):
        return {"status": "error", "detail": "Invalid JSON payload"}

    event_type = payload.get("event")
    instance = payload.get("instance")

    logger.info("webhook_whatsapp_recebido", event_type=event_type, instance=instance)

    # --- Eventos de conexão da Evolution API ---
    if event_type == "CONNECTION_UPDATE":
        data = payload.get("data", {})
        state = data.get("state")  # "open", "close", "connecting"
        logger.info("connection_update_recebido", instance=instance, state=state)
        if state in ("close", "connecting"):
            channel_state_port.set_connection_state("whatsapp", False, reason=state)
            logger.warning("whatsapp_desconectado", instance=instance, state=state)
        elif state == "open":
            channel_state_port.set_connection_state("whatsapp", True)
            logger.info("whatsapp_conectado", instance=instance)
        return {"status": "success", "event": "connection_update"}

    if event_type == "QRCODE_UPDATED":
        data = payload.get("data", {})
        qrcode = data.get("qrcode") or data.get("qr_code")
        logger.warning("qr_code_atualizado", instance=instance, has_qrcode=bool(qrcode))
        channel_state_port.set_qr_pending("whatsapp", qrcode)
        return {"status": "success", "event": "qrcode_updated"}

    # --- Mensagens ---
    if event_type != "MESSAGES-upsert":
        return {"status": "ignored", "reason": "event_type_not_handled"}

    with uow:
        data = payload.get("data", {})
        message_id = data.get("key", {}).get("id")
        remote_jid = data.get("key", {}).get("remoteJid")
        from_me = data.get("key", {}).get("fromMe", False)

        # Filtra mensagens de grupos (remoteJid termina com @g.us)
        if remote_jid and remote_jid.endswith("@g.us"):
            logger.info("webhook_ignorado_grupo", remote_jid=remote_jid)
            return {"status": "ignored", "reason": "group_message"}

        # Normaliza telefone via Phone VO (suporta JID)
        from vendas.domain.value_objects.phone import Phone

        phone_vo = Phone(remote_jid) if remote_jid else None
        _ = str(phone_vo) if phone_vo else None

        # Se a mensagem foi enviada por nós mesmos (fromMe), verifica se é echo do bot
        if from_me:
            # Verifica se o message_id existe na outbox (nossa mensagem enviada)
            if (
                hasattr(uow, "outbox")
                and uow.outbox
                and uow.outbox.exists_by_provider_message_id(message_id)
            ):
                logger.info("echo_bot_detectado", message_id=message_id)
                return {"status": "acknowledged", "type": "outbound_echo"}
            # Caso contrário, é takeover humano
            logger.warning(
                "takeover_humano_detectado", message_id=message_id, remote_jid=remote_jid
            )
            if phone_vo:
                lead = uow.leads.find_by_dedupe_key(cnpj=None, phone=phone_vo)
                if lead:
                    # Busca ou cria conversa
                    conversation: Conversation | None = uow.conversations.get_by_lead_id(lead.id)
                    if conversation is None:
                        # Cria conversa se não existir
                        conversation = Conversation.create(
                            lead_id=lead.id,
                            channel="whatsapp",
                            contact_phone=remote_jid,
                            at=clock.now(),
                        )
                        uow.conversations.add(conversation)
                    # Marca takeover
                    conversation.trigger_takeover(at=clock.now())
                    uow.conversations.save(conversation)
                    uow.commit()
                    logger.info(
                        "conversa_marcada_takeover",
                        lead_id=str(lead.id),
                        conversation_id=str(conversation.id),
                    )
            return {"status": "success", "event": "takeover_detected"}

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

        # Deduplicação: verifica se já processamos este provider_message_id
        if not message_id:
            logger.warning("webhook_sem_message_id")
            return {"status": "error", "detail": "Missing message id"}

        if uow.inbound_events.exists_by_provider_id("evolution", message_id):
            logger.info("webhook_duplicado_ignorado", provider_message_id=message_id)
            return {"status": "success", "message_id": message_id, "deduped": True}

        # Grava evento de inbound para rastreabilidade e idempotência
        inbound_event = InboundEvent.create(
            provider_name="evolution",
            provider_event_id=message_id,
            event_type="message",
            payload=payload,
            at=clock.now(),
        )
        uow.inbound_events.add(inbound_event)
        try:
            uow.commit()
        except IntegrityError:
            # Constraint única (uq_inbound_events_provider_event) violada = duplicata
            logger.info("webhook_duplicado_constraint", provider_message_id=message_id)
            uow.rollback()
            return {"status": "success", "message_id": message_id, "deduped": True}

        return {"status": "success", "message_id": message_id}

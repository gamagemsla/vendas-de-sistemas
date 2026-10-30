from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

import structlog

from vendas.domain.entities.conversation import Conversation
from vendas.domain.entities.conversation import Message as ConversationMessage
from vendas.domain.entities.inbound_event import InboundEvent
from vendas.domain.entities.suppression_record import SuppressionReason
from vendas.domain.policies.opt_out_policy import OptOutPolicy
from vendas.domain.ports import AgentContext, Clock, ConversationAgent, ConversationLock, Message
from vendas.domain.ports.knowledge_base import KnowledgeBasePort
from vendas.domain.ports.uow import UnitOfWork
from vendas.domain.value_objects.phone import Phone, UnidentifiedContactError

logger = structlog.get_logger()


class HandleInboundCommand:
    """Caso de uso principal para processar mensagens recebidas (inbound) e acionar a IA ou Handoff."""

    def __init__(
        self,
        uow: UnitOfWork,
        agent: ConversationAgent,
        knowledge_base: KnowledgeBasePort,
        clock: Clock,
        conversation_lock_factory: Callable[[Any], ConversationLock],
    ) -> None:
        self._uow = uow
        self._agent = agent
        self._knowledge_base = knowledge_base
        self._clock = clock
        self._conversation_lock_factory = conversation_lock_factory

    def execute(
        self,
        sender_phone: str,
        message_text: str,
        provider_message_id: str,
        at: datetime | None = None,
    ) -> None:
        if at is None:
            at = self._clock.now()
        with self._uow as uow:
            # 1. Verifica duplicação de evento inbound
            if hasattr(uow, "inbound_events") and uow.inbound_events:
                if uow.inbound_events.exists_by_provider_id("evolution", provider_message_id):
                    logger.info(
                        "evento_inbound_duplicado_ignorado", provider_message_id=provider_message_id
                    )
                    return
                inbound_event = InboundEvent.create(
                    provider_name="evolution",
                    provider_event_id=provider_message_id,
                    event_type="message",
                    payload={"sender_phone": sender_phone, "message_text": message_text},
                    at=at,
                )
                uow.inbound_events.add(inbound_event)

            # 2. Normaliza telefone e trata @lid (contato não identificado)
            try:
                phone_vo = Phone(sender_phone)
            except UnidentifiedContactError as e:
                # Contato não identificado (@lid) - registra evento para handoff
                logger.warning(
                    "contato_nao_identificado_lid",
                    lid=e.lid,
                    message_text=message_text[:100],
                )
                # Se a mensagem contiver solicitação de opt-out, registra supressão usando o LID
                if (
                    OptOutPolicy.detects_opt_out(message_text)
                    and hasattr(uow, "suppression")
                    and uow.suppression
                ):
                    uow.suppression.add_suppression(
                        phone_e164=e.lid,
                        reason=SuppressionReason.OPT_OUT,
                        source="whatsapp_opt_out_lid",
                        notes=f"Opt-out detectado via mensagem de contato não identificado: {message_text[:100]}",
                    )
                    uow.commit()
                return

            # 3. Localiza o lead pelo telefone normalizado (Single-Tenant)
            lead = uow.leads.find_by_dedupe_key(cnpj=None, phone=phone_vo)
            if not lead:
                logger.warning("lead_nao_encontrado_para_inbound", phone=sender_phone)
                return

            # Acquire conversation lock for this lead (serializes concurrent inbound)
            lock = self._conversation_lock_factory(uow.session)
            with lock.acquire(lead.id):
                # 4. REGRA DE OURO: Opt-out verificado ANTES de qualquer chamada de IA
                if OptOutPolicy.detects_opt_out(message_text) or lead.status == "OPTED_OUT":
                    lead.mark_as_opted_out(at=at)
                    uow.leads.save(lead)
                    if hasattr(uow, "suppression") and uow.suppression:
                        phone_e164 = str(phone_vo)
                        uow.suppression.add_suppression(
                            phone_e164=phone_e164,
                            reason=SuppressionReason.OPT_OUT,
                            source="whatsapp_opt_out",
                            notes=f"Opt-out detectado via mensagem: {message_text[:100]}",
                        )
                    uow.commit()
                    logger.info("opt_out_processado_imediatamente", lead_id=lead.id)
                    return

                # 5. Busca ou cria a conversa para este lead
                conversation = uow.conversations.get_by_lead_id(lead.id)
                if not conversation:
                    conversation = Conversation.create(
                        lead_id=lead.id,
                        channel="whatsapp",
                        contact_phone=str(phone_vo),
                        at=at,
                    )
                    uow.conversations.add(conversation)

                # 6. Persiste a mensagem recebida na conversa ANTES de acionar a IA
                inbound_msg = ConversationMessage.create_inbound(
                    conversation_id=conversation.id,
                    content=message_text,
                    message_type="text",
                    external_id=provider_message_id,
                    at=at,
                )
                conversation.add_message(inbound_msg, at=at)
                uow.conversations.save(conversation)

                # 7. Verifica se a conversa está sob takeover humano (IA pausada)
                if conversation.is_under_human_takeover():
                    logger.info("conversa_em_takeover_humano_ia_ignorada", lead_id=lead.id)
                    uow.commit()
                    return

                # 8. Monta o contexto para o Agente de IA
                # Carrega histórico real da conversa (incluindo a mensagem atual)
                history: Sequence[Message] = conversation.messages

                # Busca base de conhecimento (preview) para injetar no contexto
                kb_preview = self._knowledge_base.preview(message_text, at=at)

                # Converte a mensagem de domínio para o port Message
                current_message = Message(
                    id=inbound_msg.id,
                    conversation_id=inbound_msg.conversation_id,
                    direction=inbound_msg.direction,
                    content=inbound_msg.content,
                    message_type=inbound_msg.message_type,
                    template_name=inbound_msg.template_name,
                    status=inbound_msg.status,
                    external_id=inbound_msg.external_id,
                    error_message=inbound_msg.error_message,
                    created_at=inbound_msg.created_at,
                    sent_at=inbound_msg.sent_at,
                )

                context = AgentContext(
                    lead=lead,
                    conversation_history=history,
                    current_step=conversation.current_step,
                    cadence_step_template=None,
                    lead_enriched_data=None,
                    knowledge_base=kb_preview,
                    current_message=current_message,
                )

                # 9. Executa a decisão estruturada com o Agente
                decision = self._agent.decide(context)

                # 10. Validação de Guardrails e Handoff / Outbox
                if decision.action == "handoff" or decision.confidence < 0.7:
                    logger.info(
                        "handoff_acionado_por_guardrail",
                        reason=decision.handoff_reason,
                        confidence=decision.confidence,
                    )
                    conversation.trigger_handoff(
                        reason=decision.handoff_reason or "baixa_confianca",
                        at=at,
                    )
                    uow.conversations.save(conversation)
                else:
                    outbound_payload = {
                        "phone": sender_phone,
                        "content": decision.response_text or "",
                    }
                    uow.outbox.add(
                        event_type="SEND_AI_RESPONSE",
                        payload=outbound_payload,
                        idempotency_key=f"inbound-{provider_message_id}-reply",
                    )

                uow.commit()

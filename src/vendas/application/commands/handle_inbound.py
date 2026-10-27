from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

import structlog

from vendas.domain.entities.suppression_record import SuppressionReason
from vendas.domain.policies.opt_out_policy import OptOutPolicy
from vendas.domain.ports import AgentContext, Clock, ConversationAgent, ConversationLock, Message
from vendas.domain.ports.knowledge_base import KnowledgeBasePort
from vendas.domain.ports.uow import UnitOfWork
from vendas.domain.value_objects.phone import Phone

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
            # 1. Validação de Idempotência do Inbound
            if hasattr(uow, "inbound_events") and uow.inbound_events:
                if uow.inbound_events.exists(provider_message_id):
                    logger.info(
                        "inbound_duplicado_ignorado", provider_message_id=provider_message_id
                    )
                    return
                uow.inbound_events.record(provider_message_id, sender_phone, message_text)

            # 2. Localiza o lead pelo telefone normalizado (Single-Tenant)
            phone_vo = Phone(sender_phone)
            lead = uow.leads.find_by_dedupe_key(cnpj=None, phone=phone_vo)
            if not lead:
                logger.warning("lead_nao_encontrado_para_inbound", phone=sender_phone)
                return

            # Acquire conversation lock for this lead (serializes concurrent inbound)
            lock = self._conversation_lock_factory(uow.session)
            with lock.acquire(lead.id):
                # 3. REGRA DE OURO: Opt-out verificado ANTES de qualquer chamada de IA
                if OptOutPolicy.detects_opt_out(message_text) or lead.status == "OPTED_OUT":
                    lead.mark_as_opted_out(at=at)
                    uow.leads.save(lead)
                    # Registra na lista de supressão permanente via helper
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

                # 4. Verifica se a conversa está sob takeover humano (IA pausada)
                conversation = (
                    uow.conversations.get_by_lead_id(lead.id)
                    if hasattr(uow.conversations, "get_by_lead_id")
                    else None
                )
                if conversation and conversation.is_under_human_takeover():
                    logger.info("conversa_em_takeover_humano_ia_ignorada", lead_id=lead.id)
                    conversation.add_message(
                        sender="lead", text=message_text, timestamp=self._clock.now()
                    )
                    uow.conversations.save(conversation)
                    uow.commit()
                    return

                # 5. Monta o contexto para o Agente de IA
                # Histórico vazio por simplicidade; pode ser preenchido futuramente
                history: Sequence[Message] = ()

                # Busca base de conhecimento (preview) para injetar no contexto
                kb_preview = self._knowledge_base.preview(message_text, at=at)

                context = AgentContext(
                    lead=lead,
                    conversation_history=history,
                    current_step=0,
                    cadence_step_template=None,
                    lead_enriched_data=None,
                    knowledge_base=kb_preview,
                )

                # 6. Executa a decisão estruturada com o Agente
                decision = self._agent.decide(context)

                # 7. Validação de Guardrails e Handoff / Outbox
                if decision.action == "handoff" or decision.confidence < 0.7:
                    logger.info(
                        "handoff_acionado_por_guardrail",
                        reason=decision.handoff_reason,
                        confidence=decision.confidence,
                    )
                    if conversation:
                        conversation.trigger_handoff(
                            reason=decision.handoff_reason or "baixa_confianca"
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

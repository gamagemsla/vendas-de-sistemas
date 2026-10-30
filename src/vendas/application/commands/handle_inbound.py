from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

import structlog

from vendas.domain.entities.cadence_enrollment import EnrollmentStatus
from vendas.domain.entities.conversation import Conversation
from vendas.domain.entities.conversation import Message as ConversationMessage
from vendas.domain.entities.inbound_event import InboundEvent
from vendas.domain.entities.suppression_record import SuppressionReason
from vendas.domain.policies.opt_out_policy import OptOutPolicy
from vendas.domain.policies.price_policy import PriceValidationPolicy
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

                # 10. Validação de preço
                price_policy = PriceValidationPolicy()
                final_action = decision.action
                handoff_reason = decision.handoff_reason

                if final_action in ("reply", "qualify", "disqualify") and decision.response_text:
                    validation = price_policy.validate(decision.response_text, kb_preview)
                    if not validation.is_valid:
                        logger.warning(
                            "price_validation_failed_forcing_handoff",
                            mismatches=[str(m) for m in validation.mismatches],
                        )
                        final_action = "handoff"
                        handoff_reason = "price_mismatch"

                # 11. Tratamento das ações
                if final_action == "handoff":
                    logger.info(
                        "handoff_executado", reason=handoff_reason, original_action=decision.action
                    )
                    conversation.trigger_handoff(reason=handoff_reason or "handoff", at=at)
                    uow.conversations.save(conversation)
                    lead.handoff(assigned_to=None, notes=handoff_reason, at=at)
                    uow.leads.save(lead)
                    enrollment = uow.enrollments.get_by_lead(lead.id)
                    if enrollment and enrollment.status == EnrollmentStatus.ACTIVE:
                        enrollment.cancel(reason="handoff", at=at)
                        uow.enrollments.save(enrollment)
                    uow.outbox.add(
                        event_type="HANDOFF_NOTIFICATION",
                        payload={
                            "lead_id": str(lead.id),
                            "conversation_id": str(conversation.id),
                            "reason": handoff_reason,
                        },
                        idempotency_key=f"handoff-{conversation.id}-{at.isoformat()}",
                    )
                elif final_action == "reply":
                    if decision.response_text and decision.response_text.strip():
                        uow.outbox.add(
                            event_type="SEND_AI_RESPONSE",
                            payload={"phone": sender_phone, "content": decision.response_text},
                            idempotency_key=f"inbound-{provider_message_id}-reply",
                        )
                elif final_action == "qualify":
                    if decision.qualification_score is not None:
                        lead.start_qualification(at=at)
                        lead.qualification_score = decision.qualification_score
                        if decision.qualification_notes:
                            lead.qualification_notes = decision.qualification_notes
                        uow.leads.save(lead)
                    if decision.response_text and decision.response_text.strip():
                        uow.outbox.add(
                            event_type="SEND_AI_RESPONSE",
                            payload={"phone": sender_phone, "content": decision.response_text},
                            idempotency_key=f"inbound-{provider_message_id}-qualify",
                        )
                elif final_action == "disqualify":
                    reason = decision.disqualification_reason or "desqualificado_pela_ia"
                    lead.disqualify(reason=reason, at=at)
                    uow.leads.save(lead)
                    if decision.response_text and decision.response_text.strip():
                        uow.outbox.add(
                            event_type="SEND_AI_RESPONSE",
                            payload={"phone": sender_phone, "content": decision.response_text},
                            idempotency_key=f"inbound-{provider_message_id}-disqualify",
                        )
                elif final_action == "opt_out":
                    lead.opt_out(reason=decision.opt_out_intent or "opt_out_via_ia", at=at)
                    uow.leads.save(lead)
                    if hasattr(uow, "suppression") and uow.suppression:
                        uow.suppression.add_suppression(
                            phone_e164=sender_phone,
                            reason=SuppressionReason.OPT_OUT,
                            source="whatsapp_opt_out_ia",
                            notes=f"Opt-out detectado pela IA: {decision.opt_out_intent}",
                        )
                    if decision.response_text and decision.response_text.strip():
                        uow.outbox.add(
                            event_type="SEND_AI_RESPONSE",
                            payload={"phone": sender_phone, "content": decision.response_text},
                            idempotency_key=f"inbound-{provider_message_id}-optout",
                        )
                elif final_action == "wait":
                    logger.debug("wait_action_ia_aguardando", lead_id=lead.id)
                else:
                    logger.warning("acao_desconhecida_da_ia", action=final_action)

                uow.commit()

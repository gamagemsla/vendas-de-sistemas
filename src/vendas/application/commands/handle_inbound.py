from typing import Any

import structlog

from vendas.domain.policies.opt_out_policy import OptOutPolicy
from vendas.domain.ports import UnitOfWork
from vendas.domain.value_objects.phone import Phone

logger = structlog.get_logger()


class HandleInboundCommand:
    """Caso de uso principal para processar mensagens recebidas (inbound) e acionar a IA ou Handoff."""

    def __init__(self, uow: UnitOfWork, agent: Any, clock: Any) -> None:
        self._uow = uow
        self._agent = agent
        self._clock = clock

    def execute(
        self,
        sender_phone: str,
        message_text: str,
        provider_message_id: str,
    ) -> None:
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
            lead = uow.leads.find_by_dedupe_key(cnpj=None, phone=Phone(sender_phone))
            if not lead:
                logger.warning("lead_nao_encontrado_para_inbound", phone=sender_phone)
                return

            # 3. REGRA DE OURO: Opt-out verificado ANTES de qualquer chamada de IA
            if OptOutPolicy.detects_opt_out(message_text) or lead.status == "OPTED_OUT":
                lead.mark_as_opted_out()
                uow.leads.save(lead)
                # Registra na lista de supressão permanente
                if hasattr(uow, "suppression"):
                    uow.suppression.add(identifier=sender_phone, reason="Opt-out via WhatsApp")
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
            system_prompt = (
                "Você é um assistente de prospecção B2B altamente qualificado. "
                "Responda apenas com base nas regras comerciais e dados fornecidos. "
                "Nunca prometa descontos ou prazos sem aprovação humana."
            )
            context_data = (
                f"Lead: {lead.name}\nStatus: {lead.status}\nÚltima mensagem do lead: {message_text}"
            )

            # 6. Executa a decisão estruturada com o Agente Gemini
            decision = self._agent.decide(
                system_prompt=system_prompt,
                conversation_context=context_data,
            )

            # 7. Validação de Guardrails e Handoff / Outbox
            if decision.needs_handoff or decision.confidence < 0.7:
                logger.info(
                    "handoff_acionado_por_guardrail",
                    reason=decision.reason,
                    confidence=decision.confidence,
                )
                if conversation:
                    conversation.trigger_handoff(reason=decision.reason)
                    uow.conversations.save(conversation)
            else:
                outbound_payload = {
                    "phone": sender_phone,
                    "content": decision.reply,
                }
                uow.outbox.add(
                    event_type="SEND_AI_RESPONSE",
                    payload=outbound_payload,
                    idempotency_key=f"inbound-{provider_message_id}-reply",
                )

            uow.commit()

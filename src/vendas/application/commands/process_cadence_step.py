from typing import Any

import structlog

from vendas.domain.policies.send_window_policy import SendWindowPolicy
from vendas.domain.ports import UnitOfWork

logger = structlog.get_logger()


class ProcessCadenceStepCommand:
    """Processa etapas de cadências vencidas de forma atômica (Outbox + Avanço de Passo)."""

    def __init__(self, uow: UnitOfWork, clock: Any, send_window_policy: SendWindowPolicy) -> None:
        self._uow = uow
        self._clock = clock
        self._send_window_policy = send_window_policy

    def execute(self, batch_size: int = 10) -> int:
        processed_count = 0
        now = self._clock.now()

        with self._uow as uow:
            if not hasattr(uow, "enrollments") or not uow.enrollments:
                return 0

            # Busca enrollments vencidos com SKIP LOCKED para múltiplos workers concorrentes
            due_enrollments = uow.enrollments.claim_due(now=now, batch_size=batch_size)
            if not due_enrollments:
                return 0

            for enrollment in due_enrollments:
                lead = uow.leads.get(enrollment.lead_id)

                # Se o lead não existe, deu opt-out ou foi suprimido, cancela a cadência dele
                if not lead or lead.status == "OPTED_OUT":
                    enrollment.cancel("lead_nao_encontrado_ou_opted_out", at=now)
                    uow.enrollments.save(enrollment)
                    continue

                # Valida política de horário comercial e fuso do lead
                if lead.phone is None:
                    continue
                phone_ddd = lead.phone.ddd
                if not self._send_window_policy.is_allowed(phone_ddd, now):
                    # Fora da janela: o worker ignora por ora e ele será pego depois
                    continue

                # BLOQUEIO MANDATÓRIO: Verifica lista de supressão antes de enfileirar
                phone_e164 = str(lead.phone)
                if (
                    hasattr(uow, "suppression")
                    and uow.suppression
                    and uow.suppression.is_suppressed(phone_e164)
                ):
                    enrollment.cancel("telefone_na_lista_supressao", at=now)
                    uow.enrollments.save(enrollment)
                    logger.info(
                        "envio_bloqueado_supressao",
                        lead_id=lead.id,
                        phone=phone_e164,
                        enrollment_id=enrollment.id,
                        step=enrollment.current_step,
                    )
                    continue

                # Prepara o payload da mensagem baseada no passo atual
                message_payload = {
                    "lead_id": lead.id,
                    "phone": phone_e164,
                    "step": enrollment.current_step,
                    "content": f"Olá {lead.name}, passando para dar continuidade ao nosso contato.",
                }

                # TRANSAÇÃO ATÔMICA: Grava na Outbox + Avança o passo da cadência
                uow.outbox.add(
                    event_type="SEND_CADENCE_MESSAGE",
                    payload=message_payload,
                    idempotency_key=f"cadence-{lead.id}-step-{enrollment.current_step}",
                )

                # Avança a cadência para o próximo intervalo/passo
                next_step = enrollment.current_step + 1
                enrollment.advance_step(next_step=next_step, next_run_at=now, at=now)
                uow.enrollments.save(enrollment)
                processed_count += 1

            uow.commit()

        return processed_count

from __future__ import annotations

from datetime import datetime, timedelta

import structlog

from vendas.domain.policies.cadence_policy import CadencePolicy
from vendas.domain.policies.daily_cap_policy import DailyCapPolicy
from vendas.domain.policies.min_interval_policy import MinIntervalPolicy
from vendas.domain.policies.send_window_policy import SendWindowPolicy
from vendas.domain.ports import ChannelStatePort, Clock, LegalBasisPort, UnitOfWork

logger = structlog.get_logger()


class ProcessCadenceStepCommand:
    """Processa etapas de cadências vencidas aplicando pipeline de 6 checagens antes de gravar na Outbox."""

    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        send_window_policy: SendWindowPolicy,
        cadence_policy: CadencePolicy,
        legal_basis_port: LegalBasisPort,
        channel_state_port: ChannelStatePort,
        daily_cap_policy: DailyCapPolicy,
        min_interval_policy: MinIntervalPolicy,
        unsubscribe_base_url: str = "http://localhost:8000/unsubscribe",
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._send_window_policy = send_window_policy
        self._cadence_policy = cadence_policy
        self._legal_basis_port = legal_basis_port
        self._channel_state_port = channel_state_port
        self._daily_cap_policy = daily_cap_policy
        self._min_interval_policy = min_interval_policy

    def _next_business_day_08(self, dt: datetime) -> datetime:
        """Retorna o próximo dia útil (seg-sex) às 08:00 no mesmo fuso de dt."""
        next_day = dt + timedelta(days=1)
        next_day = next_day.replace(hour=8, minute=0, second=0, microsecond=0)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day

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

                if lead.phone is None:
                    continue
                phone_e164 = str(lead.phone)
                phone_ddd = lead.phone.ddd

                # 1) Supressão
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

                # 2) Base legal
                if not self._legal_basis_port.has_legal_basis(str(lead.id), lead.phone):
                    enrollment.cancel("sem_base_legal", at=now)
                    uow.enrollments.save(enrollment)
                    continue

                # 3) Janela de envio
                if not self._send_window_policy.is_allowed(phone_ddd, now):
                    # Fora da janela: pula ciclo, mantém next_run_at inalterado
                    continue

                # 4) Teto diário
                daily_cap_result = self._daily_cap_policy.check(
                    channel="whatsapp", reference_time=now
                )
                if not daily_cap_result.allowed:
                    # Reagenda para próximo dia útil 08:00
                    next_run_at = self._next_business_day_08(now)
                    enrollment.next_run_at = next_run_at
                    enrollment.updated_at = now
                    uow.enrollments.save(enrollment)
                    continue

                # 5) Intervalo mínimo
                min_interval_result = self._min_interval_policy.check(
                    lead_id=str(lead.id), channel="whatsapp", reference_time=now
                )
                if not min_interval_result.allowed:
                    next_run_at = min_interval_result.next_allowed_at or now
                    enrollment.next_run_at = next_run_at
                    enrollment.updated_at = now
                    uow.enrollments.save(enrollment)
                    continue

                # 6) Estado do canal
                if not self._channel_state_port.is_connected("whatsapp"):
                    next_run_at = now + timedelta(minutes=5)
                    enrollment.next_run_at = next_run_at
                    enrollment.updated_at = now
                    uow.enrollments.save(enrollment)
                    continue

                # Prepara o payload da mensagem baseada no passo atual
                current_step = enrollment.current_step
                next_step_def = self._cadence_policy.get_next_step(current_step)
                template_name = next_step_def.template_name if next_step_def else "unknown"

                message_payload = {
                    "lead_id": lead.id,
                    "phone": phone_e164,
                    "step": current_step,
                    "template_name": template_name,
                    "content": f"Olá {lead.name}, passando para dar continuidade ao nosso contato.",
                }

                # TRANSAÇÃO ATÔMICA: Grava na Outbox + Avança o passo da cadência
                uow.outbox.add(
                    event_type="SEND_CADENCE_MESSAGE",
                    payload=message_payload,
                    idempotency_key=f"cadence-{lead.id}-step-{enrollment.current_step}",
                )

                # Avança a cadência para o próximo intervalo/passo usando a policy para calcular o delay
                next_step = current_step + 1
                delay = self._cadence_policy.get_delay_until_next(current_step)
                next_run_at = now + delay if delay else now
                enrollment.advance_step(next_step=next_step, next_run_at=next_run_at, at=now)
                uow.enrollments.save(enrollment)
                processed_count += 1

            uow.commit()

        return processed_count

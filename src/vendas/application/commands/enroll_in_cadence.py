from datetime import timedelta

from vendas.domain.entities.cadence_enrollment import CadenceEnrollment, EnrollmentStatus
from vendas.domain.policies.cadence_policy import CadencePolicy
from vendas.domain.policies.eligibility_policy import EligibilityPolicy
from vendas.domain.ports import Clock, UnitOfWork


class EnrollInCadenceCommand:
    """Caso de uso responsável por inscrever um lead elegível em uma cadência comercial."""

    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        eligibility_policy: EligibilityPolicy,
        cadence_policy: CadencePolicy,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._eligibility_policy = eligibility_policy
        self._cadence_policy = cadence_policy

    def execute(self, lead_id: str, cadence_name: str = "default_b2b") -> bool:
        with self._uow as uow:
            lead = uow.leads.get(lead_id)
            if not lead:
                return False

            now = self._clock.now()

            # Prevenção de duplicidade: verifica se já existe matrícula ativa/pausada na mesma cadência
            existing = uow.enrollments.get_by_lead(lead.id)
            if (
                existing
                and existing.cadence_name == cadence_name
                and existing.status in (EnrollmentStatus.ACTIVE, EnrollmentStatus.PAUSED)
            ):
                return False

            # Validações de segurança antes da inscrição (política completa)
            if lead.phone is not None:
                result = self._eligibility_policy.check(
                    lead_id=lead.id,
                    phone=lead.phone,
                    email=str(lead.email) if lead.email else None,
                    status=lead.status.value if lead.status else None,
                    company_size=lead.company_size,
                    industry=lead.industry,
                    qualification_score=lead.qualification_score,
                )
                if not result.is_eligible:
                    reasons_str = ", ".join([r.value for r in result.reasons])
                    lead.disqualify(reason=reasons_str, at=now)
                    uow.leads.save(lead)
                    uow.commit()
                    return False
            else:
                lead.disqualify(reason="invalid_phone", at=now)
                uow.leads.save(lead)
                uow.commit()
                return False

            # Transiciona o estado do lead na máquina de estados (criada na F1-02)
            try:
                lead.start_cadence(at=now)
            except ValueError:
                # Transição de estado não permitida a partir do estado atual
                return False

            # Salva o lead atualizado
            uow.leads.save(lead)

            # Calcula agendamento do primeiro passo usando a CadencePolicy
            first_step = self._cadence_policy.get_step_by_number(1)
            delay = first_step.delay if first_step else timedelta(0)
            next_run_at = now + delay

            # Cria a matrícula via factory de domínio
            enrollment = CadenceEnrollment.create(
                lead_id=lead.id,
                cadence_name=cadence_name,
                next_run_at=next_run_at,
                at=now,
            )

            # Persiste a matrícula
            uow.enrollments.add(enrollment)

            uow.commit()
            return True

from typing import Any

from vendas.domain.policies.eligibility_policy import EligibilityPolicy
from vendas.domain.ports import UnitOfWork


class EnrollInCadenceCommand:
    """Caso de uso responsável por inscrever um lead elegível em uma cadência comercial."""

    def __init__(
        self,
        uow: UnitOfWork,
        clock: Any,
        eligibility_policy: EligibilityPolicy,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._eligibility_policy = eligibility_policy

    def execute(self, lead_id: str, cadence_name: str = "default_b2b") -> bool:
        with self._uow as uow:
            lead = uow.leads.get(lead_id)
            if not lead:
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
                    lead.disqualify(reason=reasons_str)
                    uow.leads.save(lead)
                    uow.commit()
                    return False
            else:
                lead.disqualify(reason="invalid_phone")
                uow.leads.save(lead)
                uow.commit()
                return False

            # Transiciona o estado do lead na máquina de estados (criada na F1-02)
            try:
                lead.start_cadence()
            except Exception:  # noqa: BLE001
                # Se a transição de estado não for permitida a partir do estado atual
                return False

            # Salva o lead atualizado
            uow.leads.save(lead)

            # Inscreve na cadência e agenda o próximo passo imediato (ou conforme regra)
            if hasattr(uow, "enrollments") and uow.enrollments:
                uow.enrollments.create_enrollment(
                    lead_id=lead.id,
                    cadence_name=cadence_name,
                    step=1,
                    next_run_at=self._clock.now(),
                    status="ACTIVE",
                )

            uow.commit()
            return True

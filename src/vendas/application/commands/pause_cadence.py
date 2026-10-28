from vendas.domain.entities.cadence_enrollment import EnrollmentStatus
from vendas.domain.ports import Clock, UnitOfWork


class PauseCadenceCommand:
    """Caso de uso para pausar a cadência de um lead com motivo."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, lead_id: str, reason: str) -> bool:
        with self._uow as uow:
            enrollment = uow.enrollments.get_by_lead(lead_id)
            if not enrollment:
                return False
            if enrollment.status != EnrollmentStatus.ACTIVE:
                # Só permite pausar se estiver ativa
                return False
            now = self._clock.now()
            enrollment.pause(reason=reason, at=now)
            uow.enrollments.save(enrollment)
            uow.commit()
            return True

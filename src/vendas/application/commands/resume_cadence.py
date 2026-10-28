from vendas.domain.entities.cadence_enrollment import EnrollmentStatus
from vendas.domain.ports import Clock, UnitOfWork


class ResumeCadenceCommand:
    """Caso de uso para retomar a cadência pausada de um lead."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, lead_id: str) -> bool:
        with self._uow as uow:
            enrollment = uow.enrollments.get_by_lead(lead_id)
            if not enrollment:
                return False
            if enrollment.status != EnrollmentStatus.PAUSED:
                # Só permite retomar se estiver pausada
                return False
            now = self._clock.now()
            enrollment.resume(at=now)
            uow.enrollments.save(enrollment)
            uow.commit()
            return True

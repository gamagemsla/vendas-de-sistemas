"""Entidade CadenceEnrollment - Agregado para gerenciar inscrição em cadências de prospecção."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from vendas.domain.events import DomainEvent


class EnrollmentStatus(str, Enum):
    """Estados da inscrição em cadência."""

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class CadenceEnrollment:
    """Inscrição de um lead em uma cadência de prospecção.

    Attributes:
        id: Identificador único da inscrição.
        lead_id: ID do lead vinculado.
        cadence_name: Nome da cadência (ex: "cold_outreach_v1").
        current_step: Passo atual da cadência (começa em 0).
        status: Estado da inscrição (ACTIVE, PAUSED, COMPLETED, CANCELLED).
        next_run_at: Próximo agendamento de execução (para cadências baseadas em tempo).
        last_step_at: Timestamp da última execução de passo.
        completed_at: Timestamp de conclusão (se status == COMPLETED).
        cancelled_at: Timestamp de cancelamento (se status == CANCELLED).
        cancel_reason: Motivo do cancelamento.
        created_at: Timestamp de criação.
        updated_at: Timestamp da última atualização.
        events: Lista de eventos de domínio não publicados.
    """

    id: UUID
    lead_id: UUID
    cadence_name: str
    created_at: datetime
    updated_at: datetime
    current_step: int = 0
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE
    next_run_at: datetime | None = None
    last_step_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        lead_id: UUID,
        cadence_name: str,
        next_run_at: datetime | None = None,
        at: datetime | None = None,
    ) -> CadenceEnrollment:
        """Factory para criar nova inscrição em cadência."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para criar CadenceEnrollment")
        return cls(
            id=uuid4(),
            lead_id=lead_id,
            cadence_name=cadence_name,
            current_step=0,
            status=EnrollmentStatus.ACTIVE,
            next_run_at=next_run_at,
            created_at=at,
            updated_at=at,
        )

    def advance_step(
        self, next_step: int, next_run_at: datetime | None = None, at: datetime | None = None
    ) -> None:
        """Avança para próximo passo da cadência."""
        if self.status != EnrollmentStatus.ACTIVE:
            raise ValueError(f"Não é possível avançar passo em status {self.status.value}")
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para advance_step")

        self.current_step = next_step
        self.last_step_at = at
        self.next_run_at = next_run_at
        self.updated_at = at

    def pause(self, reason: str | None = None, at: datetime | None = None) -> None:
        """Pausa a cadência."""
        if self.status == EnrollmentStatus.PAUSED:
            return
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para pause")
        self.status = EnrollmentStatus.PAUSED
        self.updated_at = at
        # reason could be stored in a new field if needed; currently not persisted

    def resume(self, at: datetime | None = None) -> None:
        """Retoma cadência pausada."""
        if self.status != EnrollmentStatus.PAUSED:
            raise ValueError(f"Só é possível retomar de PAUSED, atual: {self.status.value}")
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para resume")
        self.status = EnrollmentStatus.ACTIVE
        self.updated_at = at

    def complete(self, at: datetime | None = None) -> None:
        """Marca cadência como concluída."""
        if self.status not in (EnrollmentStatus.ACTIVE, EnrollmentStatus.PAUSED):
            raise ValueError(
                f"Só é possível completar de ACTIVE/PAUSED, atual: {self.status.value}"
            )
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para complete")
        self.status = EnrollmentStatus.COMPLETED
        self.completed_at = at
        self.updated_at = at

    def cancel(self, reason: str, at: datetime | None = None) -> None:
        """Cancela a inscrição em cadência."""
        if self.status == EnrollmentStatus.CANCELLED:
            return
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para cancel")
        self.status = EnrollmentStatus.CANCELLED
        self.cancelled_at = at
        self.cancel_reason = reason.strip() if reason and reason.strip() else None
        self.updated_at = at

    def is_due(self, at: datetime) -> bool:
        """Verifica se o passo próximo está vencido."""
        if self.status != EnrollmentStatus.ACTIVE or self.next_run_at is None:
            return False
        return at >= self.next_run_at

    def clear_events(self) -> list[DomainEvent]:
        """Remove e retorna eventos pendentes."""
        events = self.events.copy()
        self.events.clear()
        return events

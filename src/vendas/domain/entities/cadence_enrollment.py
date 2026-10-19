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
    current_step: int = 0
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE
    next_run_at: datetime | None = None
    last_step_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls, lead_id: UUID, cadence_name: str, next_run_at: datetime | None = None
    ) -> CadenceEnrollment:
        """Factory para criar nova inscrição em cadência."""
        return cls(
            id=uuid4(),
            lead_id=lead_id,
            cadence_name=cadence_name,
            current_step=0,
            status=EnrollmentStatus.ACTIVE,
            next_run_at=next_run_at,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def advance_step(self, next_step: int, next_run_at: datetime | None = None) -> None:
        """Avança para próximo passo da cadência."""
        if self.status != EnrollmentStatus.ACTIVE:
            raise ValueError(f"Não é possível avançar passo em status {self.status.value}")

        self.current_step = next_step
        self.last_step_at = datetime.utcnow()
        self.next_run_at = next_run_at
        self.updated_at = datetime.utcnow()

    def pause(self) -> None:
        """Pausa a cadência."""
        if self.status == EnrollmentStatus.PAUSED:
            return
        self.status = EnrollmentStatus.PAUSED
        self.updated_at = datetime.utcnow()

    def resume(self) -> None:
        """Retoma cadência pausada."""
        if self.status != EnrollmentStatus.PAUSED:
            raise ValueError(f"Só é possível retomar de PAUSED, atual: {self.status.value}")
        self.status = EnrollmentStatus.ACTIVE
        self.updated_at = datetime.utcnow()

    def complete(self) -> None:
        """Marca cadência como concluída."""
        if self.status not in (EnrollmentStatus.ACTIVE, EnrollmentStatus.PAUSED):
            raise ValueError(
                f"Só é possível completar de ACTIVE/PAUSED, atual: {self.status.value}"
            )
        self.status = EnrollmentStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def cancel(self, reason: str) -> None:
        """Cancela a inscrição em cadência."""
        if self.status == EnrollmentStatus.CANCELLED:
            return
        self.status = EnrollmentStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.cancel_reason = reason.strip() if reason and reason.strip() else None
        self.updated_at = datetime.utcnow()

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

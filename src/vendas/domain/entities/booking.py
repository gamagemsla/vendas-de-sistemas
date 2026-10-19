"""Entidade Booking - Agendamento de reunião com cliente qualificado."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class BookingStatus(str, Enum):
    """Estados de um agendamento."""

    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


@dataclass(slots=True)
class Booking:
    """Agendamento de reunião (após qualificação).

    Attributes:
        id: Identificador único do agendamento.
        lead_id: ID do lead qualificado.
        scheduled_at: Data/hora agendada.
        timezone: Timezone do agendamento (ex: "America/Sao_Paulo").
        duration_minutes: Duração prevista em minutos.
        title: Título/assunto da reunião.
        notes: Observações sobre a reunião.
        assigned_to: ID do vendedor responsável.
        status: Estado do agendamento.
        meeting_url: URL de videoconferência (se aplicável).
        completed_at: Timestamp de conclusão/realização.
        cancelled_at: Timestamp de cancelamento.
        cancellation_reason: Motivo do cancelamento.
        created_at: Timestamp de criação.
        updated_at: Timestamp da última atualização.
    """

    id: UUID
    lead_id: UUID
    scheduled_at: datetime
    timezone: str
    duration_minutes: int = 30
    title: str = ""
    notes: str | None = None
    assigned_to: UUID | None = None
    status: BookingStatus = BookingStatus.CONFIRMED
    meeting_url: str | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(
        cls,
        lead_id: UUID,
        scheduled_at: datetime,
        timezone: str,
        duration_minutes: int = 30,
        title: str = "",
        assigned_to: UUID | None = None,
    ) -> Booking:
        """Factory para criar novo agendamento."""
        return cls(
            id=uuid4(),
            lead_id=lead_id,
            scheduled_at=scheduled_at,
            timezone=timezone,
            duration_minutes=duration_minutes,
            title=title.strip() if title and title.strip() else "",
            assigned_to=assigned_to,
            status=BookingStatus.CONFIRMED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def reschedule(self, new_scheduled_at: datetime) -> None:
        """Reagenda para nova data/hora."""
        if self.status == BookingStatus.CANCELLED:
            raise ValueError("Não é possível reagendar agendamento cancelado")

        self.scheduled_at = new_scheduled_at
        self.status = BookingStatus.RESCHEDULED
        self.updated_at = datetime.utcnow()

    def complete(self) -> None:
        """Marca como realizada."""
        if self.status == BookingStatus.CANCELLED:
            raise ValueError("Não é possível completar agendamento cancelado")

        self.status = BookingStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def no_show(self) -> None:
        """Marca como não comparecido."""
        if self.status == BookingStatus.CANCELLED:
            raise ValueError("Não é possível marcar como no-show um agendamento cancelado")

        self.status = BookingStatus.NO_SHOW
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def cancel(self, reason: str) -> None:
        """Cancela o agendamento."""
        if self.status in (BookingStatus.COMPLETED, BookingStatus.NO_SHOW):
            raise ValueError(f"Não é possível cancelar agendamento em status {self.status.value}")

        self.status = BookingStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.cancellation_reason = reason.strip() if reason and reason.strip() else None
        self.updated_at = datetime.utcnow()

    def is_in_future(self, at: datetime | None = None) -> bool:
        """Verifica se o agendamento é no futuro."""
        now = at or datetime.utcnow()
        return self.scheduled_at > now

    def is_overdue(self, at: datetime | None = None) -> bool:
        """Verifica se o agendamento já passou."""
        now = at or datetime.utcnow()
        return self.scheduled_at < now

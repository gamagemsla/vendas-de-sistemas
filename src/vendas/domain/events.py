"""Eventos de Domínio - Eventos disparados nas mudanças de estado relevantes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Evento base de domínio."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: UUID | None = None
    aggregate_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LeadCreated(DomainEvent):
    """Evento disparado quando um Lead é criado."""

    aggregate_type: str = "Lead"
    name: str = ""
    phone: str = ""
    cnpj: str | None = None
    email: str | None = None
    status: str = "NEW"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "name": self.name,
                "phone": self.phone,
                "cnpj": self.cnpj,
                "email": self.email,
                "status": self.status,
            },
        )


@dataclass(frozen=True, slots=True)
class LeadStatusChanged(DomainEvent):
    """Evento disparado quando o status do Lead muda."""

    aggregate_type: str = "Lead"
    previous_status: str = ""
    new_status: str = ""
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "previous_status": self.previous_status,
                "new_status": self.new_status,
                "reason": self.reason,
            },
        )


@dataclass(frozen=True, slots=True)
class LeadEnriched(DomainEvent):
    """Evento disparado quando o Lead é enriquecido com dados externos."""

    aggregate_type: str = "Lead"
    cnpj: str | None = None
    email: str | None = None
    company_name: str | None = None
    company_size: str | None = None
    industry: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "cnpj": self.cnpj,
                "email": self.email,
                "company_name": self.company_name,
                "company_size": self.company_size,
                "industry": self.industry,
            },
        )


@dataclass(frozen=True, slots=True)
class LeadQualified(DomainEvent):
    """Evento disparado quando o Lead é qualificado."""

    aggregate_type: str = "Lead"
    qualification_score: int = 0
    qualification_notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "qualification_score": self.qualification_score,
                "qualification_notes": self.qualification_notes,
            },
        )


@dataclass(frozen=True, slots=True)
class LeadDisqualified(DomainEvent):
    """Evento disparado quando o Lead é desqualificado."""

    aggregate_type: str = "Lead"
    reason: str = ""
    disqualification_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "reason": self.reason,
                "disqualification_code": self.disqualification_code,
            },
        )


@dataclass(frozen=True, slots=True)
class LeadOptedOut(DomainEvent):
    """Evento disparado quando o Lead faz opt-out (terminal)."""

    aggregate_type: str = "Lead"
    reason: str | None = None
    channel: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "reason": self.reason,
                "channel": self.channel,
            },
        )


@dataclass(frozen=True, slots=True)
class LeadHandoff(DomainEvent):
    """Evento disparado quando o Lead é passado para vendas (handoff)."""

    aggregate_type: str = "Lead"
    assigned_to: UUID | None = None
    handoff_notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "assigned_to": str(self.assigned_to) if self.assigned_to else None,
                "handoff_notes": self.handoff_notes,
            },
        )


@dataclass(frozen=True, slots=True)
class LeadWon(DomainEvent):
    """Evento disparado quando o Lead fecha como ganho."""

    aggregate_type: str = "Lead"
    deal_value: int = 0  # em centavos
    closed_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "deal_value": self.deal_value,
                "closed_at": self.closed_at.isoformat(),
            },
        )


@dataclass(frozen=True, slots=True)
class LeadLost(DomainEvent):
    """Evento disparado quando o Lead fecha como perdido."""

    aggregate_type: str = "Lead"
    loss_reason: str = ""
    loss_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "loss_reason": self.loss_reason,
                "loss_code": self.loss_code,
            },
        )


@dataclass(frozen=True, slots=True)
class ConversationStarted(DomainEvent):
    """Evento disparado quando uma conversa é iniciada."""

    aggregate_type: str = "Conversation"
    channel: str = ""
    contact_phone: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "channel": self.channel,
                "contact_phone": self.contact_phone,
            },
        )


@dataclass(frozen=True, slots=True)
class MessageReceived(DomainEvent):
    """Evento disparado quando uma mensagem é recebida."""

    aggregate_type: str = "Conversation"
    message_id: UUID = field(default_factory=uuid4)
    direction: str = "inbound"  # inbound | outbound
    content: str = ""
    message_type: str = "text"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "message_id": str(self.message_id),
                "direction": self.direction,
                "content": self.content,
                "message_type": self.message_type,
            },
        )


@dataclass(frozen=True, slots=True)
class ConversationStateChanged(DomainEvent):
    """Evento disparado quando o estado da conversa muda."""

    aggregate_type: str = "Conversation"
    previous_state: str = ""
    new_state: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            {
                "previous_state": self.previous_state,
                "new_state": self.new_state,
            },
        )

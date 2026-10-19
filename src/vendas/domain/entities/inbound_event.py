"""Entidade InboundEvent - Evento de entrada recebido de canal externo (WhatsApp, etc)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(slots=True)
class InboundEvent:
    """Evento de entrada capturado de canal externo.

    Attributes:
        id: Identificador único do evento.
        provider_name: Nome do provedor (ex: "evolution", "whatsapp", "email").
        provider_event_id: ID único do evento no provedor (ex: provider_message_id).
        event_type: Tipo do evento (ex: "message", "status_update", "webhook").
        payload: Dados brutos do evento em dict.
        processed: Flag indicando se foi processado.
        processed_at: Timestamp de processamento.
        error_message: Erro durante processamento, se houver.
        created_at: Timestamp de recebimento.
    """

    id: UUID
    provider_name: str
    provider_event_id: str
    event_type: str
    payload: dict[str, Any]
    processed: bool = False
    processed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(
        cls,
        provider_name: str,
        provider_event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> InboundEvent:
        """Factory para criar novo evento de entrada."""
        return cls(
            id=uuid4(),
            provider_name=provider_name,
            provider_event_id=provider_event_id,
            event_type=event_type,
            payload=payload,
            processed=False,
            processed_at=None,
            error_message=None,
            created_at=datetime.utcnow(),
        )

    def mark_as_processed(self) -> None:
        """Marca evento como processado com sucesso."""
        self.processed = True
        self.processed_at = datetime.utcnow()
        self.error_message = None

    def mark_as_failed(self, error: str) -> None:
        """Marca evento como falhado durante processamento."""
        self.processed = True
        self.processed_at = datetime.utcnow()
        self.error_message = error.strip() if error and error.strip() else None

    def is_duplicate(self, other: InboundEvent) -> bool:
        """Verifica se é duplicata de outro evento (mesmo provider_event_id)."""
        return (
            self.provider_name == other.provider_name
            and self.provider_event_id == other.provider_event_id
        )

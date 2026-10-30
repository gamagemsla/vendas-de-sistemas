"""Entidade InboundEvent - Evento de entrada recebido de canal externo (WhatsApp, etc)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
        attempts: Número de tentativas de processamento.
        locked_until: Timestamp até quando o evento está bloqueado para processamento.
        created_at: Timestamp de recebimento.
    """

    id: UUID
    provider_name: str
    provider_event_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
    processed: bool = False
    processed_at: datetime | None = None
    error_message: str | None = None
    attempts: int = 0
    locked_until: datetime | None = None

    @classmethod
    def create(
        cls,
        provider_name: str,
        provider_event_id: str,
        event_type: str,
        payload: dict[str, Any],
        at: datetime | None = None,
    ) -> InboundEvent:
        """Factory para criar novo evento de entrada."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para create InboundEvent")
        return cls(
            id=uuid4(),
            provider_name=provider_name,
            provider_event_id=provider_event_id,
            event_type=event_type,
            payload=payload,
            processed=False,
            processed_at=None,
            error_message=None,
            attempts=0,
            locked_until=None,
            created_at=at,
        )

    def mark_as_processed(self, at: datetime | None = None) -> None:
        """Marca evento como processado com sucesso."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para mark_as_processed")
        self.processed = True
        self.processed_at = at
        self.error_message = None
        self.locked_until = None

    def mark_as_failed(self, error: str, at: datetime | None = None) -> None:
        """Marca evento como falhado durante processamento."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para mark_as_failed")
        self.processed = True
        self.processed_at = at
        self.error_message = error.strip() if error and error.strip() else None
        self.locked_until = None

    def claim(self, lease_seconds: int, at: datetime | None = None) -> None:
        """Reivindica o evento para processamento (incrementa attempts, define locked_until)."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para claim")
        self.attempts += 1
        self.locked_until = at + timedelta(seconds=lease_seconds)

    def release(self, at: datetime | None = None) -> None:
        """Libera o evento (remove lock, mantém attempts)."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para release")
        self.locked_until = None

    def is_duplicate(self, other: InboundEvent) -> bool:
        """Verifica se é duplicata de outro evento (mesmo provider_event_id)."""
        return (
            self.provider_name == other.provider_name
            and self.provider_event_id == other.provider_event_id
        )

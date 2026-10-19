"""Entidade OutboxMessage - Mensagem na outbox para envio assíncrono (Transactional Outbox pattern)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class OutboxStatus(str, Enum):
    """Estados de uma mensagem na outbox."""

    PENDING = "pending"  # Aguardando processamento
    PROCESSING = "processing"  # Sendo processada
    SENT = "sent"  # Enviada com sucesso
    FAILED = "failed"  # Falhou (não vai fazer retry)
    DEAD_LETTER = "dead_letter"  # Excedeu max_attempts


@dataclass(slots=True)
class OutboxMessage:
    """Mensagem na outbox para envio assíncrono.

    Pattern: Transactional Outbox — garante que a mensagem seja salva
    no banco ao mesmo tempo que a entidade de domínio, e depois é
    processada de forma assíncrona por um worker.

    Attributes:
        id: Identificador único da mensagem.
        aggregate_type: Tipo do agregado ("Lead", "Conversation", etc.).
        aggregate_id: ID do agregado.
        event_type: Tipo do evento de domínio.
        payload: Dados do evento em dict.
        channel: Canal de envio ("whatsapp", "email", None para eventos internos).
        destination: Destino (telefone, e-mail, etc.).
        template_name: Nome do template prê-aprovado (se aplicável).
        template_params: Parâmetros do template.
        priority: Prioridade (0=normal, 1=high, -1=low).
        attempts: Tentativas realizadas.
        max_attempts: Máximo de tentativas permitidas.
        status: Estado atual.
        last_error: Último erro (se houver).
        scheduled_at: Data/hora para processamento.
        created_at: Timestamp de criação.
        processed_at: Timestamp de processamento (se finalizado).
    """

    id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    payload: dict[str, Any]
    channel: str | None = None
    destination: str | None = None
    template_name: str | None = None
    template_params: dict[str, Any] | None = None
    priority: int = 0
    attempts: int = 0
    max_attempts: int = 3
    status: OutboxStatus = OutboxStatus.PENDING
    last_error: str | None = None
    scheduled_at: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        channel: str | None = None,
        destination: str | None = None,
        template_name: str | None = None,
        template_params: dict[str, Any] | None = None,
        priority: int = 0,
        max_attempts: int = 3,
        scheduled_at: datetime | None = None,
    ) -> OutboxMessage:
        """Factory para criar nova mensagem na outbox."""
        return cls(
            id=uuid4(),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            channel=channel,
            destination=destination,
            template_name=template_name,
            template_params=template_params,
            priority=priority,
            max_attempts=max_attempts,
            status=OutboxStatus.PENDING,
            scheduled_at=scheduled_at or datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

    def is_due(self, at: datetime | None = None) -> bool:
        """Verifica se está vencida para processamento."""
        now = at or datetime.utcnow()
        return self.status == OutboxStatus.PENDING and now >= self.scheduled_at

    def mark_processing(self) -> None:
        """Marca como sendo processada."""
        self.status = OutboxStatus.PROCESSING

    def mark_sent(self, external_id: str | None = None) -> None:
        """Marca como enviada com sucesso."""
        self.status = OutboxStatus.SENT
        self.attempts += 1
        self.processed_at = datetime.utcnow()
        self.last_error = None

    def mark_failed(self, error: str, will_retry: bool) -> None:
        """Marca como falhada."""
        self.attempts += 1
        self.last_error = error

        if self.attempts >= self.max_attempts:
            self.status = OutboxStatus.DEAD_LETTER
            self.processed_at = datetime.utcnow()
        elif will_retry:
            # Retorna para PENDING para retry
            self.status = OutboxStatus.PENDING
        else:
            # Falha permanente
            self.status = OutboxStatus.FAILED
            self.processed_at = datetime.utcnow()

    def can_retry(self) -> bool:
        """Verifica se pode fazer novo retry."""
        return self.status == OutboxStatus.PENDING and self.attempts < self.max_attempts

    def is_exhausted(self) -> bool:
        """Verifica se excedeu max_attempts."""
        return self.status == OutboxStatus.DEAD_LETTER

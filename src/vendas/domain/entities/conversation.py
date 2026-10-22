"""Entidade Conversation - Conversação com cliente via WhatsApp, Email, etc."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class ConversationState(str, Enum):
    """Estados de uma conversa."""

    OPEN = "OPEN"
    WAITING_REPLY = "WAITING_REPLY"
    CLOSED = "CLOSED"
    HANDOFF = "HANDOFF"


@dataclass(slots=True)
class Message:
    """Mensagem em uma conversa."""

    id: UUID
    conversation_id: UUID
    direction: str  # "inbound" | "outbound"
    content: str
    message_type: str  # "text" | "image" | "document" | "audio" | "video"
    created_at: datetime
    template_name: str | None = None
    status: str = "pending"  # "pending" | "sent" | "delivered" | "read" | "failed"
    external_id: str | None = None  # ID no provedor (Evolution, etc.)
    error_message: str | None = None
    sent_at: datetime | None = None

    @classmethod
    def create_inbound(
        cls,
        conversation_id: UUID,
        content: str,
        message_type: str = "text",
        external_id: str | None = None,
        at: datetime | None = None,
    ) -> Message:
        """Factory para criar mensagem de entrada (cliente → bot)."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para create_inbound")
        return cls(
            id=uuid4(),
            conversation_id=conversation_id,
            direction="inbound",
            content=content,
            message_type=message_type,
            external_id=external_id,
            status="delivered",
            created_at=at,
        )

    @classmethod
    def create_outbound(
        cls,
        conversation_id: UUID,
        content: str,
        message_type: str = "text",
        template_name: str | None = None,
        at: datetime | None = None,
    ) -> Message:
        """Factory para criar mensagem de saída (bot → cliente)."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para create_outbound")
        return cls(
            id=uuid4(),
            conversation_id=conversation_id,
            direction="outbound",
            content=content,
            message_type=message_type,
            template_name=template_name,
            status="pending",
            created_at=at,
        )

    def mark_sent(self, external_id: str | None = None, at: datetime | None = None) -> None:
        """Marca como enviada."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para mark_sent")
        self.status = "sent"
        self.external_id = external_id
        self.sent_at = at

    def mark_delivered(self) -> None:
        """Marca como entregue."""
        self.status = "delivered"

    def mark_read(self) -> None:
        """Marca como lida."""
        self.status = "read"

    def mark_failed(self, error: str) -> None:
        """Marca como falhada."""
        self.status = "failed"
        self.error_message = error


@dataclass(slots=True)
class Conversation:
    """Conversa com cliente via canal externo.

    Attributes:
        id: Identificador único da conversa.
        lead_id: ID do lead associado.
        channel: Canal da conversa ("whatsapp", "email", etc.).
        contact_phone: Telefone em E.164 (ex: "+5511999999999").
        contact_email: E-mail do contato (opcional).
        state: Estado da conversa (OPEN, WAITING_REPLY, CLOSED, HANDOFF).
        current_step: Passo atual da cadência (se aplicável).
        last_message_at: Timestamp da última mensagem.
        created_at: Timestamp de criação.
        updated_at: Timestamp da última atualização.
        messages: Histórico de mensagens (lazy-loaded).
    """

    id: UUID
    lead_id: UUID
    channel: str  # "whatsapp", "email", "sms"
    contact_phone: str  # E.164
    created_at: datetime
    updated_at: datetime
    contact_email: str | None = None
    state: ConversationState = ConversationState.OPEN
    current_step: int = 0
    last_message_at: datetime | None = None
    messages: list[Message] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        lead_id: UUID,
        channel: str,
        contact_phone: str,
        contact_email: str | None = None,
        at: datetime | None = None,
    ) -> Conversation:
        """Factory para criar nova conversa."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para create Conversation")
        return cls(
            id=uuid4(),
            lead_id=lead_id,
            channel=channel,
            contact_phone=contact_phone,
            contact_email=contact_email,
            state=ConversationState.OPEN,
            created_at=at,
            updated_at=at,
        )

    def add_message(self, message: Message, at: datetime | None = None) -> None:
        """Adiciona mensagem ao histórico."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para add_message")
        self.messages.append(message)
        self.last_message_at = message.created_at
        self.updated_at = at

    def is_under_human_takeover(self) -> bool:
        """Verifica se está sob takeover humano (estado HANDOFF)."""
        return self.state == ConversationState.HANDOFF

    def trigger_handoff(self, at: datetime | None = None) -> None:
        """Marca para handoff humano."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para trigger_handoff")
        self.state = ConversationState.HANDOFF
        self.updated_at = at

    def close(self, at: datetime | None = None) -> None:
        """Fecha a conversa."""
        if at is None:
            raise ValueError("Timestamp 'at' é obrigatório para close")
        self.state = ConversationState.CLOSED
        self.updated_at = at

    def get_messages_since(self, timestamp: datetime) -> list[Message]:
        """Busca mensagens desde um timestamp."""
        return [m for m in self.messages if m.created_at >= timestamp]

    def last_message(self) -> Message | None:
        """Retorna a última mensagem."""
        return self.messages[-1] if self.messages else None

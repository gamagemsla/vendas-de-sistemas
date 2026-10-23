"""SQLAlchemy 2.x ORM Models for all database tables.

This module contains the declarative ORM models that map to database tables.
All models inherit from the Base class and include created_at, updated_at.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vendas.infrastructure.persistence.base import Base


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    ENRICHED = "ENRICHED"
    ELIGIBLE = "ELIGIBLE"
    IN_CADENCE = "IN_CADENCE"
    REPLIED = "REPLIED"
    QUALIFYING = "QUALIFYING"
    QUALIFIED = "QUALIFIED"
    HANDOFF = "HANDOFF"
    WON = "WON"
    LOST = "LOST"
    DISQUALIFIED = "DISQUALIFIED"
    OPTED_OUT = "OPTED_OUT"


class ConversationState(str, enum.Enum):
    OPEN = "OPEN"
    WAITING_REPLY = "WAITING_REPLY"
    CLOSED = "CLOSED"
    HANDOFF = "HANDOFF"


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    LOCATION = "location"
    CONTACT = "contact"
    BUTTON = "button"
    LIST = "list"
    TEMPLATE = "template"


class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class CadenceStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OutboxStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SuppressionReason(str, enum.Enum):
    OPT_OUT = "opt_out"
    DNC = "dnc"
    BOUNCE = "bounce"
    COMPLAINT = "complaint"
    MANUAL = "manual"


class ConsentType(str, enum.Enum):
    EXPLICIT = "explicit"
    LEGITIMATE_INTEREST = "legitimate_interest"
    CONTRACTUAL = "contractual"
    LEGAL_OBLIGATION = "legal_obligation"


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    DEACTIVATE = "deactivate"
    RULES_UPDATE = "rules_update"
    TRANSITION = "transition"
    SEND = "send"
    RECEIVE = "receive"
    OPT_OUT = "opt_out"
    HANDOFF = "handoff"
    QUALIFY = "qualify"
    DISQUALIFY = "disqualify"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    contacts: Mapped[list[Contact]] = relationship(
        "Contact", back_populates="company", lazy="selectin"
    )
    leads: Mapped[list[Lead]] = relationship("Lead", back_populates="company", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("cnpj", name="uq_companies_cnpj"),
        Index("ix_companies_name", "name"),
    )

    def __repr__(self) -> str:
        return f"Company(id={self.id}, name='{self.name}', cnpj='{self.cnpj}')"


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    company: Mapped[Company | None] = relationship(
        "Company", back_populates="contacts", lazy="selectin"
    )
    leads: Mapped[list[Lead]] = relationship("Lead", back_populates="contact", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("phone_e164", name="uq_contacts_phone"),
        Index("ix_contacts_email", "email"),
        Index("ix_contacts_company", "company_id"),
    )

    def __repr__(self) -> str:
        return f"Contact(id={self.id}, name='{self.name}', phone='{self.phone_e164}')"


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discount_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"CatalogItem(id={self.id}, service_name='{self.service_name}', price_cents={self.price_cents})"


class CatalogService(Base):
    __tablename__ = "catalog_services"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discount_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_catalog_services_name", "name"),
        Index("ix_catalog_services_active", "active"),
    )

    def __repr__(self) -> str:
        return f"CatalogService(id={self.id}, name='{self.name}', active={self.active})"


class CatalogPrice(Base):
    __tablename__ = "catalog_prices"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_services.id"), nullable=False, index=True
    )
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_catalog_prices_service_window", "service_id", "valid_from", "valid_to"),
        Index("ix_catalog_prices_active", "active"),
    )

    def __repr__(self) -> str:
        return f"CatalogPrice(id={self.id}, service_id={self.service_id}, price_cents={self.price_cents})"


class FaqEntry(Base):
    __tablename__ = "faq_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_services.id"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(String(255), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_faq_entries_question", "question"),
        Index("ix_faq_entries_active", "active"),
    )

    def __repr__(self) -> str:
        return f"FaqEntry(id={self.id}, question='{self.question}', active={self.active})"


class KnowledgeChangeLog(Base):
    __tablename__ = "knowledge_change_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False, default="admin")
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_knowledge_change_logs_entity_actor", "entity_type", "entity_id", "actor_id"),
    )

    def __repr__(self) -> str:
        return f"KnowledgeChangeLog(id={self.id}, entity={self.entity_type}:{self.entity_id}, action={self.action})"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, native_enum=False), default=LeadStatus.NEW, nullable=False, index=True
    )
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qualification_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qualification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    handoff_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deal_value_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    loss_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    loss_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    company: Mapped[Company | None] = relationship(
        "Company", back_populates="leads", lazy="selectin"
    )
    contact: Mapped[Contact | None] = relationship(
        "Contact", back_populates="leads", lazy="selectin"
    )
    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="lead", lazy="selectin"
    )
    cadence_enrollments: Mapped[list[CadenceEnrollment]] = relationship(
        "CadenceEnrollment", back_populates="lead", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("phone_e164", name="uq_leads_phone"),
        UniqueConstraint("cnpj", name="uq_leads_cnpj"),
        Index("ix_leads_status_value", "status"),
        Index("ix_leads_email", "email"),
        Index("ix_leads_assigned_to_value", "assigned_to"),
        Index("ix_leads_source", "source"),
    )

    def __repr__(self) -> str:
        return f"Lead(id={self.id}, name='{self.name}', status={self.status.value})"


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    probability: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_close_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assigned_to: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lead: Mapped[Lead] = relationship("Lead", lazy="selectin")

    __table_args__ = (
        Index("ix_opportunities_stage_value", "stage"),
        Index("ix_opportunities_assigned_to_value", "assigned_to"),
    )

    def __repr__(self) -> str:
        return f"Opportunity(id={self.id}, name='{self.name}', stage='{self.stage}')"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(50), default="whatsapp", nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[ConversationState] = mapped_column(
        Enum(ConversationState, native_enum=False),
        default=ConversationState.OPEN,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lead: Mapped[Lead] = relationship("Lead", back_populates="conversations", lazy="selectin")
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="conversation", lazy="selectin", order_by="Message.created_at"
    )

    __table_args__ = (
        Index("ix_conversations_state_value", "state"),
        Index("ix_conversations_contact_phone", "contact_phone"),
        Index("ix_conversations_last_message_at", "last_message_at"),
    )

    def __repr__(self) -> str:
        return f"Conversation(id={self.id}, lead_id={self.lead_id}, state={self.state.value})"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, native_enum=False), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, native_enum=False), default=MessageType.TEXT, nullable=False
    )
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, native_enum=False),
        default=MessageStatus.PENDING,
        nullable=False,
        index=True,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    provider_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="messages", lazy="selectin"
    )
    events: Mapped[list[MessageEvent]] = relationship(
        "MessageEvent",
        back_populates="message",
        lazy="selectin",
        order_by="MessageEvent.created_at",
    )

    __table_args__ = (
        UniqueConstraint("provider_message_id", name="uq_messages_provider_message_id"),
        Index("ix_messages_status_value", "status"),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_messages_provider", "provider_name", "provider_message_id"),
    )

    def __repr__(self) -> str:
        return f"Message(id={self.id}, conversation_id={self.conversation_id}, direction={self.direction.value})"


class MessageEvent(Base):
    __tablename__ = "message_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    message: Mapped[Message] = relationship("Message", back_populates="events", lazy="selectin")

    __table_args__ = (
        Index("ix_message_events_message_created", "message_id", "created_at"),
        Index("ix_message_events_provider", "provider_name", "provider_event_id"),
        Index("ix_message_events_unprocessed", "processed", "created_at"),
    )

    def __repr__(self) -> str:
        return f"MessageEvent(id={self.id}, message_id={self.message_id}, event_type='{self.event_type}')"


class CadenceEnrollment(Base):
    __tablename__ = "cadence_enrollments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cadence_name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[CadenceStatus] = mapped_column(
        Enum(CadenceStatus, native_enum=False),
        default=CadenceStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lead: Mapped[Lead] = relationship("Lead", back_populates="cadence_enrollments", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("lead_id", "cadence_name", name="uq_cadence_enrollments_lead_cadence"),
        Index("ix_cadence_enrollments_status_value", "status"),
        Index("ix_cadence_enrollments_next_run", "next_run_at", "status"),
    )

    def __repr__(self) -> str:
        return f"CadenceEnrollment(id={self.id}, lead_id={self.lead_id}, cadence='{self.cadence_name}', step={self.current_step})"


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    template_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(OutboxStatus, native_enum=False),
        default=OutboxStatus.PENDING,
        nullable=False,
        index=True,
    )
    provider_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    provider_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_outbox_status_value", "status"),
        Index("ix_outbox_scheduled", "scheduled_at", "status"),
        Index("ix_outbox_provider", "provider_name", "provider_message_id"),
    )

    def __repr__(self) -> str:
        return f"Outbox(id={self.id}, channel={self.channel}, to={self.to_phone}, status={self.status.value})"


class InboundEvent(Base):
    __tablename__ = "inbound_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(default=False, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "provider_name", "provider_event_id", name="uq_inbound_events_provider_event"
        ),
        Index("ix_inbound_events_processed", "processed"),
        Index("ix_inbound_events_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"InboundEvent(id={self.id}, provider={self.provider_name}, event={self.event_type})"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.PENDING, nullable=False, index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_jobs_status_value", "status"),
        Index("ix_jobs_scheduled", "scheduled_at", "status"),
        Index("ix_jobs_type", "job_type"),
    )

    def __repr__(self) -> str:
        return f"Job(id={self.id}, type={self.job_type}, status={self.status.value})"


class SuppressionList(Base):
    __tablename__ = "suppression_list"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[SuppressionReason] = mapped_column(
        Enum(SuppressionReason, native_enum=False), nullable=False
    )
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("phone_e164", name="uq_suppression_phone"),
        Index("ix_suppression_reason", "reason"),
        Index("ix_suppression_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"SuppressionList(id={self.id}, phone={self.phone_e164}, reason={self.reason.value})"


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False)
    consent_type: Mapped[ConsentType] = mapped_column(
        Enum(ConsentType, native_enum=False), nullable=False
    )
    granted: Mapped[bool] = mapped_column(default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    proof: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("phone_e164", "consent_type", name="uq_consent_phone_type"),
        Index("ix_consent_granted", "granted"),
        Index("ix_consent_phone", "phone_e164"),
    )

    def __repr__(self) -> str:
        return f"ConsentRecord(id={self.id}, phone={self.phone_e164}, type={self.consent_type.value}, granted={self.granted})"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, native_enum=False), nullable=False
    )
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_actor", "actor_id"),
        Index("ix_audit_logs_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"AuditLog(id={self.id}, entity={self.entity_type}:{self.entity_id}, action={self.action.value})"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="confirmed", nullable=False)
    meeting_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lead: Mapped[Lead] = relationship("Lead", lazy="selectin")

    __table_args__ = (
        Index("ix_bookings_scheduled_status", "scheduled_at", "status"),
        Index("ix_bookings_lead_id", "lead_id"),
        Index("ix_bookings_assigned_to", "assigned_to"),
    )

    def __repr__(self) -> str:
        return f"Booking(id={self.id}, lead_id={self.lead_id}, scheduled_at={self.scheduled_at}, status={self.status})"


# --- Aliases de compatibilidade para Mypy e Repositórios ---
LeadModel = Lead
CompanyModel = Company
ContactModel = Contact
CatalogItemModel = CatalogItem
OpportunityModel = Opportunity
ConversationModel = Conversation
MessageModel = Message
MessageEventModel = MessageEvent
CadenceEnrollmentModel = CadenceEnrollment
OutboxModel = Outbox
InboundEventModel = InboundEvent
JobModel = Job
SuppressionListModel = SuppressionList
ConsentRecordModel = ConsentRecord
AuditLogModel = AuditLog
KnowledgeChangeLogModel = KnowledgeChangeLog
CatalogServiceModel = CatalogService
CatalogPriceModel = CatalogPrice
FaqEntryModel = FaqEntry
BookingModel = Booking

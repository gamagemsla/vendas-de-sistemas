"""Implementação SQLAlchemy do LeadDataSubjectPort para LGPD."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from vendas.domain.ports import Clock
from vendas.domain.ports.lead_data_subject import LeadDataExport, LeadDataSubjectPort
from vendas.infrastructure.clock import SystemClock
from vendas.infrastructure.persistence.orm_models import (
    AuditLog,
    Booking,
    CadenceEnrollment,
    ConsentRecord,
    Conversation,
    InboundEvent,
    Lead,
    Message,
    Outbox,
    SuppressionList,
)


class SQLAlchemyLeadDataSubjectAdapter(LeadDataSubjectPort):
    """Adapter SQLAlchemy para operações de direitos do titular (LGPD)."""

    def __init__(self, session: Session, clock: Clock | None = None) -> None:
        self._session = session
        self._clock = clock or SystemClock()

    async def export(self, lead_id: UUID) -> LeadDataExport:
        """Exporta todos os dados pessoais do lead."""
        lead = self._session.get(Lead, lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} não encontrado")

        phone = lead.phone_e164

        inbound_events = (
            self._session.execute(
                select(InboundEvent).where(InboundEvent.payload["phone"].astext == phone)
            )
            .scalars()
            .all()
        )

        outbox_messages = (
            self._session.execute(select(Outbox).where(Outbox.to_phone == phone)).scalars().all()
        )

        cadence_enrollments = (
            self._session.execute(
                select(CadenceEnrollment).where(CadenceEnrollment.lead_id == lead_id)
            )
            .scalars()
            .all()
        )

        conversations = (
            self._session.execute(select(Conversation).where(Conversation.lead_id == lead_id))
            .scalars()
            .all()
        )

        conversation_history: list[dict[str, object]] = []
        for conv in conversations:
            messages = (
                self._session.execute(select(Message).where(Message.conversation_id == conv.id))
                .scalars()
                .all()
            )
            for msg in messages:
                conversation_history.append(
                    {
                        "conversation_id": str(conv.id),
                        "message_id": str(msg.id),
                        "direction": msg.direction.value,
                        "type": msg.message_type.value,
                        "content": msg.content,
                        "status": msg.status.value,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    }
                )

        suppression_records = (
            self._session.execute(
                select(SuppressionList).where(SuppressionList.phone_e164 == phone)
            )
            .scalars()
            .all()
        )

        self._session.execute(
            select(ConsentRecord).where(ConsentRecord.phone_e164 == phone)
        ).scalars().all()

        self._session.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "lead", AuditLog.entity_id == str(lead_id)
            )
        ).scalars().all()

        self._session.execute(select(Booking).where(Booking.lead_id == lead_id)).scalars().all()

        return LeadDataExport(
            lead_id=lead.id,
            phone=lead.phone_e164,
            email=lead.email,
            name=lead.name,
            cnpj=lead.cnpj,
            status=lead.status.value,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            inbound_events=[
                {
                    "id": str(e.id),
                    "event_type": e.event_type,
                    "payload": e.payload,
                    "provider_event_id": e.provider_event_id,
                    "received_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in inbound_events
            ],
            outbox_messages=[
                {
                    "id": str(m.id),
                    "event_type": m.event_type,
                    "payload": m.payload,
                    "status": m.status.value,
                    "attempts": m.attempts,
                    "last_error": m.error_message,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "processed_at": m.sent_at.isoformat() if m.sent_at else None,
                }
                for m in outbox_messages
            ],
            cadence_enrollments=[
                {
                    "id": str(e.id),
                    "cadence_name": e.cadence_name,
                    "status": e.status.value,
                    "current_step": e.current_step,
                    "enrolled_at": e.created_at.isoformat() if e.created_at else None,
                    "paused_at": None,
                    "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                }
                for e in cadence_enrollments
            ],
            conversation_history=conversation_history,
            suppression_records=[
                {
                    "id": str(s.id),
                    "reason": s.reason.value,
                    "source": s.source,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in suppression_records
            ],
        )

    async def anonymize(self, lead_id: UUID) -> None:
        """Anonimiza dados pessoais do lead mantendo integridade referencial."""
        lead = self._session.get(Lead, lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} não encontrado")

        anon_suffix = str(lead_id)[:8]
        old_phone = lead.phone_e164

        lead.phone_e164 = f"+55119999{anon_suffix}"
        lead.email = f"anon-{anon_suffix}@example.com"
        lead.name = f"Lead Anonimizado {anon_suffix}"
        lead.cnpj = None
        lead.company_name = None
        lead.qualification_notes = None
        lead.handoff_notes = None
        lead.loss_reason = None
        lead.source_data = None
        lead.updated_at = self._clock.now()

        conversations = (
            self._session.execute(select(Conversation).where(Conversation.lead_id == lead_id))
            .scalars()
            .all()
        )

        for conv in conversations:
            messages = (
                self._session.execute(select(Message).where(Message.conversation_id == conv.id))
                .scalars()
                .all()
            )
            for msg in messages:
                if msg.content:
                    msg.content = f"[CONTEÚDO ANONIMIZADO {anon_suffix}]"

        outbox_messages = (
            self._session.execute(select(Outbox).where(Outbox.to_phone == old_phone))
            .scalars()
            .all()
        )
        for outbox_msg in outbox_messages:
            if outbox_msg.payload and isinstance(outbox_msg.payload, dict):
                pii_fields = ["phone", "email", "name", "cnpj", "document"]
                for field in pii_fields:
                    if field in outbox_msg.payload:
                        outbox_msg.payload[field] = f"[ANONIMIZADO {anon_suffix}]"

        inbound_events = (
            self._session.execute(
                select(InboundEvent).where(InboundEvent.payload["phone"].astext == old_phone)
            )
            .scalars()
            .all()
        )
        for event in inbound_events:
            if event.payload and isinstance(event.payload, dict):
                pii_fields = ["phone", "email", "name", "cnpj", "document", "remote_jid"]
                for field in pii_fields:
                    if field in event.payload:
                        event.payload[field] = f"[ANONIMIZADO {anon_suffix}]"

        consent_records = (
            self._session.execute(
                select(ConsentRecord).where(ConsentRecord.phone_e164 == old_phone)
            )
            .scalars()
            .all()
        )
        for consent in consent_records:
            consent.revoked_at = self._clock.now()

        self._session.flush()

    async def delete(self, lead_id: UUID) -> None:
        """Exclui permanentemente todos os dados do lead (cascata via FK)."""
        lead = self._session.get(Lead, lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} não encontrado")

        self._session.delete(lead)
        self._session.flush()

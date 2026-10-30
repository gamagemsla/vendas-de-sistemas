"""Mappers para conversão entre Domain Entities e ORM Models."""

from vendas.domain.entities.booking import Booking, BookingStatus
from vendas.domain.entities.cadence_enrollment import CadenceEnrollment, EnrollmentStatus
from vendas.domain.entities.inbound_event import InboundEvent
from vendas.domain.entities.lead import Lead, LeadStatus
from vendas.domain.entities.outbox_message import OutboxMessage, OutboxStatus
from vendas.domain.entities.suppression_record import SuppressionReason, SuppressionRecord
from vendas.domain.value_objects import Cnpj, Email, Phone
from vendas.infrastructure.persistence.orm_models import (
    BookingModel,
    CadenceEnrollmentModel,
    InboundEventModel,
    LeadModel,
    SuppressionListModel,
)
from vendas.infrastructure.persistence.orm_models import (
    Outbox as OutboxModel,
)


class LeadMapper:
    """Mapper para Lead (Domain ↔ ORM)."""

    @staticmethod
    def to_domain(model: LeadModel) -> Lead | None:
        """Converte ORM Model para Domain Entity."""
        if not model:
            return None

        return Lead(
            id=model.id,
            name=model.name,
            phone=Phone(model.phone_e164),
            cnpj=Cnpj(model.cnpj) if model.cnpj else None,
            email=Email(model.email) if model.email else None,
            status=LeadStatus(
                model.status.value if hasattr(model.status, "value") else model.status
            ),
            company_name=model.company_name,
            company_size=model.company_size,
            industry=model.industry,
            qualification_score=model.qualification_score or 0,
            qualification_notes=model.qualification_notes,
            assigned_to=model.assigned_to,
            handoff_notes=model.handoff_notes,
            deal_value=model.deal_value_cents or 0,
            loss_reason=model.loss_reason or "",
            loss_code=model.loss_code,
            disqualification_reason="",  # Não está no ORM
            disqualification_code=None,  # Não está no ORM
            opt_out_reason=None,  # Não está no ORM
            opt_out_channel=None,  # Não está no ORM
            created_at=model.created_at,
            updated_at=model.updated_at,
            events=[],
        )

    @staticmethod
    def to_orm(entity: Lead) -> LeadModel | None:
        """Converte Domain Entity para ORM Model."""
        if not entity:
            return None

        return LeadModel(
            id=entity.id,
            name=entity.name,
            phone_e164=str(entity.phone),
            cnpj=str(entity.cnpj) if entity.cnpj else None,
            email=str(entity.email) if entity.email else None,
            status=entity.status,
            company_name=entity.company_name,
            company_size=entity.company_size,
            industry=entity.industry,
            qualification_score=entity.qualification_score,
            qualification_notes=entity.qualification_notes,
            assigned_to=entity.assigned_to,
            handoff_notes=entity.handoff_notes,
            deal_value_cents=entity.deal_value,
            loss_reason=entity.loss_reason or None,
            loss_code=entity.loss_code,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class CadenceEnrollmentMapper:
    """Mapper para CadenceEnrollment (Domain ↔ ORM)."""

    @staticmethod
    def to_domain(model: CadenceEnrollmentModel) -> CadenceEnrollment | None:
        """Converte ORM Model para Domain Entity."""
        if not model:
            return None

        return CadenceEnrollment(
            id=model.id,
            lead_id=model.lead_id,
            cadence_name=model.cadence_name,
            current_step=model.current_step,
            status=EnrollmentStatus(
                model.status.value if hasattr(model.status, "value") else model.status
            ),
            next_run_at=model.next_run_at,
            last_step_at=model.last_step_at,
            completed_at=model.completed_at,
            cancelled_at=model.cancelled_at,
            cancel_reason=model.cancel_reason,
            created_at=model.created_at,
            updated_at=model.updated_at,
            events=[],
        )

    @staticmethod
    def to_orm(entity: CadenceEnrollment) -> CadenceEnrollmentModel | None:
        """Converte Domain Entity para ORM Model."""
        if not entity:
            return None

        return CadenceEnrollmentModel(
            id=entity.id,
            lead_id=entity.lead_id,
            cadence_name=entity.cadence_name,
            current_step=entity.current_step,
            status=entity.status,
            next_run_at=entity.next_run_at,
            last_step_at=entity.last_step_at,
            completed_at=entity.completed_at,
            cancelled_at=entity.cancelled_at,
            cancel_reason=entity.cancel_reason,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class InboundEventMapper:
    """Mapper para InboundEvent (Domain ↔ ORM)."""

    @staticmethod
    def to_domain(model: InboundEventModel) -> InboundEvent | None:
        """Converte ORM Model para Domain Entity."""
        if not model:
            return None

        return InboundEvent(
            id=model.id,
            provider_name=model.provider_name,
            provider_event_id=model.provider_event_id,
            event_type=model.event_type,
            payload=model.payload,
            processed=model.processed,
            processed_at=model.processed_at,
            error_message=model.error_message,
            attempts=model.attempts,
            locked_until=model.locked_until,
            created_at=model.created_at,
        )

    @staticmethod
    def to_orm(entity: InboundEvent) -> InboundEventModel | None:
        """Converte Domain Entity para ORM Model."""
        if not entity:
            return None

        return InboundEventModel(
            id=entity.id,
            provider_name=entity.provider_name,
            provider_event_id=entity.provider_event_id,
            event_type=entity.event_type,
            payload=entity.payload,
            processed=entity.processed,
            processed_at=entity.processed_at,
            error_message=entity.error_message,
            attempts=entity.attempts,
            locked_until=entity.locked_until,
            created_at=entity.created_at,
        )


class SuppressionRecordMapper:
    """Mapper para SuppressionRecord (Domain ↔ ORM)."""

    @staticmethod
    def to_domain(model: SuppressionListModel) -> SuppressionRecord | None:
        """Converte ORM Model para Domain Entity."""
        if not model:
            return None

        return SuppressionRecord(
            id=model.id,
            phone_e164=model.phone_e164,
            reason=SuppressionReason(
                model.reason.value if hasattr(model.reason, "value") else model.reason
            ),
            source=model.source,
            notes=model.notes,
            created_at=model.created_at,
            expires_at=model.expires_at,
        )

    @staticmethod
    def to_orm(entity: SuppressionRecord) -> SuppressionListModel | None:
        """Converte Domain Entity para ORM Model."""
        if not entity:
            return None

        return SuppressionListModel(
            id=entity.id,
            phone_e164=entity.phone_e164,
            reason=entity.reason,
            source=entity.source,
            notes=entity.notes,
            created_at=entity.created_at,
            expires_at=entity.expires_at,
        )


class BookingMapper:
    """Mapper para Booking (Domain ↔ ORM)."""

    @staticmethod
    def to_domain(model: BookingModel) -> Booking | None:
        """Converte ORM Model para Domain Entity."""
        if not model:
            return None

        return Booking(
            id=model.id,
            lead_id=model.lead_id,
            scheduled_at=model.scheduled_at,
            timezone=model.timezone,
            duration_minutes=model.duration_minutes,
            title=model.title,
            notes=model.notes,
            assigned_to=model.assigned_to,
            status=BookingStatus(
                model.status.value if hasattr(model.status, "value") else model.status
            ),
            meeting_url=model.meeting_url,
            completed_at=model.completed_at,
            cancelled_at=model.cancelled_at,
            cancellation_reason=model.cancellation_reason,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_orm(entity: Booking) -> BookingModel | None:
        """Converte Domain Entity para ORM Model."""
        if not entity:
            return None

        return BookingModel(
            id=entity.id,
            lead_id=entity.lead_id,
            scheduled_at=entity.scheduled_at,
            timezone=entity.timezone,
            duration_minutes=entity.duration_minutes,
            title=entity.title,
            notes=entity.notes,
            assigned_to=entity.assigned_to,
            status=entity.status,
            meeting_url=entity.meeting_url,
            completed_at=entity.completed_at,
            cancelled_at=entity.cancelled_at,
            cancellation_reason=entity.cancellation_reason,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class OutboxMapper:
    """Mapper para OutboxMessage (Domain ↔ ORM)."""

    @staticmethod
    def to_domain(model: OutboxModel) -> OutboxMessage | None:
        """Converte ORM Model para Domain Entity."""
        if not model:
            return None

        return OutboxMessage(
            id=model.id,
            event_type=model.event_type,
            payload=model.payload,
            idempotency_key=model.idempotency_key,
            channel=model.channel,
            destination=model.to_phone,
            template_name=model.template_name,
            template_params=model.template_params,
            attempts=model.attempts,
            max_attempts=model.max_attempts,
            status=OutboxStatus(
                model.status.value if hasattr(model.status, "value") else model.status
            ),
            last_error=model.error_message,
            scheduled_at=model.scheduled_at or model.created_at,
            created_at=model.created_at,
            processed_at=model.sent_at,
            provider_message_id=model.provider_message_id,
        )

    @staticmethod
    def to_orm(entity: OutboxMessage) -> OutboxModel | None:
        """Converte Domain Entity para ORM Model."""
        if not entity:
            return None

        return OutboxModel(
            id=entity.id,
            event_type=entity.event_type,
            payload=entity.payload,
            idempotency_key=entity.idempotency_key,
            channel=entity.channel,
            to_phone=entity.destination,
            template_name=entity.template_name,
            template_params=entity.template_params,
            status=entity.status,
            attempts=entity.attempts,
            max_attempts=entity.max_attempts,
            error_message=entity.last_error,
            scheduled_at=entity.scheduled_at,
            sent_at=entity.processed_at,
            provider_message_id=entity.provider_message_id,
            created_at=entity.created_at,
        )

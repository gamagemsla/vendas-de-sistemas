"""SQLAlchemy Repositories - Implementação completa (Parte 1 CORRIGIDA)."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from vendas.domain.entities.booking import Booking
from vendas.domain.entities.cadence_enrollment import CadenceEnrollment, EnrollmentStatus
from vendas.domain.entities.conversation import Conversation, Message
from vendas.domain.entities.inbound_event import InboundEvent
from vendas.domain.entities.lead import Lead, LeadStatus
from vendas.domain.entities.outbox_message import OutboxMessage
from vendas.domain.entities.suppression_record import SuppressionRecord
from vendas.domain.ports import ConversationFilter, LeadFilter
from vendas.domain.value_objects import Cnpj, Email, Phone
from vendas.infrastructure.persistence.mappers import (
    BookingMapper,
    CadenceEnrollmentMapper,
    InboundEventMapper,
    LeadMapper,
    OutboxMapper,
    SuppressionRecordMapper,
)
from vendas.infrastructure.persistence.orm_models import (
    BookingModel,
    CadenceEnrollmentModel,
    ConversationModel,
    InboundEventModel,
    LeadModel,
    MessageModel,
    OutboxModel,
    SuppressionListModel,
)


class SQLAlchemyLeadRepository:
    """Repositório de Leads com SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entity: Lead) -> None:
        """Adiciona novo lead."""
        model = LeadMapper.to_orm(entity)
        self._session.add(model)

    def get(self, entity_id: UUID | str) -> Lead | None:
        """Busca lead por ID."""
        model = self._session.query(LeadModel).filter_by(id=entity_id).first()
        return LeadMapper.to_domain(model) if model else None

    def save(self, entity: Lead) -> None:
        """Salva/atualiza lead existente."""
        model = LeadMapper.to_orm(entity)
        self._session.merge(model)

    def remove(self, entity: Lead) -> None:
        """Remove lead."""
        self._session.query(LeadModel).filter_by(id=entity.id).delete()

    def get_by_phone(self, phone: Phone) -> Lead | None:
        """Busca por telefone."""
        model = self._session.query(LeadModel).filter_by(phone_e164=str(phone)).first()
        return LeadMapper.to_domain(model) if model else None

    def get_by_email(self, email: Email) -> Lead | None:
        """Busca por e-mail."""
        model = self._session.query(LeadModel).filter_by(email=str(email)).first()
        return LeadMapper.to_domain(model) if model else None

    def get_by_cnpj(self, cnpj: Cnpj) -> Lead | None:
        """Busca por CNPJ."""
        model = self._session.query(LeadModel).filter_by(cnpj=str(cnpj)).first()
        return LeadMapper.to_domain(model) if model else None

    def find_by_dedupe_key(self, cnpj: Cnpj | None, phone: Phone | None) -> Lead | None:
        """Busca por chave de deduplicação (CNPJ ou telefone)."""
        if cnpj:
            model = self._session.query(LeadModel).filter_by(cnpj=str(cnpj)).first()
            if model:
                return LeadMapper.to_domain(model)
        if phone:
            model = self._session.query(LeadModel).filter_by(phone_e164=str(phone)).first()
            if model:
                return LeadMapper.to_domain(model)
        return None

    def list(self, filter: LeadFilter) -> Sequence[Lead]:
        """Lista leads com filtros e paginação."""
        query = self._session.query(LeadModel)

        if filter.status:
            query = query.filter_by(status=filter.status)
        if filter.statuses:
            query = query.filter(LeadModel.status.in_(filter.statuses))
        if filter.phone:
            query = query.filter_by(phone_e164=str(filter.phone))
        if filter.email:
            query = query.filter_by(email=str(filter.email))
        if filter.cnpj:
            query = query.filter_by(cnpj=str(filter.cnpj))
        if filter.assigned_to:
            query = query.filter_by(assigned_to=filter.assigned_to)
        if filter.created_after:
            query = query.filter(LeadModel.created_at >= filter.created_after)
        if filter.created_before:
            query = query.filter(LeadModel.created_at <= filter.created_before)

        limit = filter.limit
        offset = filter.offset

        models = query.order_by(LeadModel.created_at.desc()).limit(limit).offset(offset).all()
        return [lead for m in models if (lead := LeadMapper.to_domain(m)) is not None]

    def count(self, filter: LeadFilter) -> int:
        """Conta leads com filtros (sem paginação)."""
        query = self._session.query(func.count(LeadModel.id))

        if filter.status:
            query = query.filter_by(status=filter.status)
        if filter.statuses:
            query = query.filter(LeadModel.status.in_(filter.statuses))
        if filter.phone:
            query = query.filter_by(phone_e164=str(filter.phone))
        if filter.email:
            query = query.filter_by(email=str(filter.email))
        if filter.cnpj:
            query = query.filter_by(cnpj=str(filter.cnpj))
        if filter.assigned_to:
            query = query.filter_by(assigned_to=filter.assigned_to)
        if filter.created_after:
            query = query.filter(LeadModel.created_at >= filter.created_after)
        if filter.created_before:
            query = query.filter(LeadModel.created_at <= filter.created_before)

        return query.scalar() or 0

    def get_next_for_cadence(self, limit: int = 100) -> Sequence[Lead]:
        """Busca próximos leads elegíveis para cadência (status ELIGIBLE)."""
        models = (
            self._session.query(LeadModel)
            .filter_by(status=LeadStatus.ELIGIBLE)
            .order_by(LeadModel.created_at.asc())
            .limit(limit)
            .all()
        )
        return [lead for m in models if (lead := LeadMapper.to_domain(m)) is not None]

    def get_for_handoff(self, limit: int = 100) -> Sequence[Lead]:
        """Busca leads prontos para handoff (status QUALIFIED)."""
        models = (
            self._session.query(LeadModel)
            .filter_by(status=LeadStatus.QUALIFIED)
            .order_by(LeadModel.created_at.asc())
            .limit(limit)
            .all()
        )
        return [lead for m in models if (lead := LeadMapper.to_domain(m)) is not None]


class SQLAlchemyConversationRepository:
    """Repositório de Conversas com SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entity: Conversation) -> None:
        """Adiciona nova conversa."""
        model = ConversationModel(
            id=entity.id,
            lead_id=entity.lead_id,
            channel=entity.channel,
            contact_phone=entity.contact_phone,
            state=entity.state.value if hasattr(entity.state, "value") else entity.state,
            started_at=datetime.utcnow(),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
        self._session.add(model)

    def get(self, entity_id: UUID | str) -> Conversation | None:
        """Busca conversa por ID."""
        model = self._session.query(ConversationModel).filter_by(id=entity_id).first()
        return self._to_domain(model) if model else None

    def save(self, entity: Conversation) -> None:
        """Salva/atualiza conversa existente."""
        model = self._session.query(ConversationModel).filter_by(id=entity.id).first()
        if model:
            state_value = (
                entity.state.value if hasattr(entity.state, "value") else str(entity.state)
            )
            model.state = state_value  # type: ignore[assignment]
            model.updated_at = datetime.utcnow()

    def remove(self, entity: Conversation) -> None:
        """Remove conversa."""
        self._session.query(ConversationModel).filter_by(id=entity.id).delete()

    def get_by_lead(self, lead_id: UUID | str) -> Conversation | None:
        """Busca conversa ativa por lead."""
        model = (
            self._session.query(ConversationModel)
            .filter_by(lead_id=lead_id)
            .order_by(ConversationModel.created_at.desc())
            .first()
        )
        return self._to_domain(model) if model else None

    def get_by_lead_id(self, lead_id: UUID | str) -> Conversation | None:
        """Alias para get_by_lead."""
        return self.get_by_lead(lead_id)

    def get_by_contact(self, channel: str, contact_phone: str) -> Conversation | None:
        """Busca conversa por canal e contato."""
        model = (
            self._session.query(ConversationModel)
            .filter_by(channel=channel, contact_phone=contact_phone)
            .order_by(ConversationModel.created_at.desc())
            .first()
        )
        return self._to_domain(model) if model else None

    def list(self, filter: ConversationFilter) -> Sequence[Conversation]:
        """Lista conversas com filtros."""
        query = self._session.query(ConversationModel)

        if filter.lead_id:
            query = query.filter_by(lead_id=filter.lead_id)
        if filter.channel:
            query = query.filter_by(channel=filter.channel)
        if filter.state:
            query = query.filter_by(state=filter.state)
        if filter.contact_phone:
            query = query.filter_by(contact_phone=filter.contact_phone)

        limit = filter.limit
        offset = filter.offset

        models = (
            query.order_by(ConversationModel.created_at.desc()).limit(limit).offset(offset).all()
        )
        return [conv for m in models if (conv := self._to_domain(m)) is not None]

    def add_message(self, message: Message) -> None:
        """Adiciona mensagem à conversa."""
        model = MessageModel(
            id=message.id,
            conversation_id=message.conversation_id,
            direction=message.direction,
            content=message.content,
            message_type=message.message_type,
            status=message.status,
            provider_message_id=message.external_id,
            error_message=message.error_message,
            created_at=message.created_at,
        )
        self._session.add(model)
        # Atualiza last_message_at da conversa
        self._session.query(ConversationModel).filter_by(id=message.conversation_id).update(
            {"last_message_at": message.created_at}
        )

    def get_messages(
        self,
        conversation_id: UUID | str,
        limit: int = 100,
        before: datetime | None = None,
    ) -> Sequence[Message]:
        """Busca mensagens de uma conversa (mais recentes primeiro)."""
        query = self._session.query(MessageModel).filter_by(conversation_id=conversation_id)

        if before:
            query = query.filter(MessageModel.created_at < before)

        models = query.order_by(MessageModel.created_at.desc()).limit(limit).all()
        return [self._to_message(m) for m in models]

    def update_message_status(
        self,
        message_id: UUID | str,
        status: str,
        external_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Atualiza status de uma mensagem."""
        self._session.query(MessageModel).filter_by(id=message_id).update(
            {
                "status": status,
                "provider_message_id": external_id or MessageModel.provider_message_id,
                "error_message": error_message,
            }
        )

    @staticmethod
    def _to_domain(model: ConversationModel) -> Conversation | None:
        """Converte ORM para Domain."""
        if not model:
            return None
        from vendas.domain.entities.conversation import ConversationState

        return Conversation(
            id=model.id,
            lead_id=model.lead_id,
            channel=model.channel,
            contact_phone=model.contact_phone,
            contact_email=None,
            state=ConversationState(model.state),
            current_step=0,
            last_message_at=model.last_message_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_message(model: MessageModel) -> Message:
        """Converte ORM Message para Domain."""
        return Message(
            id=model.id,
            conversation_id=model.conversation_id,
            direction=model.direction,
            content=model.content,
            message_type=model.message_type,
            template_name=None,
            status=model.status,
            external_id=model.provider_message_id,
            error_message=model.error_message,
            created_at=model.created_at,
            sent_at=model.sent_at,
        )


class SQLAlchemyOutboxRepository:
    """Repositório de Outbox com SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, message: OutboxMessage | None = None, **kwargs: Any) -> None:
        """Adiciona mensagem à outbox."""
        if message:
            model = OutboxMapper.to_orm(message)
        else:
            event_type = kwargs.get("event_type")
            payload = kwargs.get("payload")
            idempotency_key = kwargs.get("idempotency_key")
            if not (event_type and payload and idempotency_key):
                raise TypeError("event_type, payload, idempotency_key are required")
            entity = OutboxMessage.create(
                event_type=event_type,
                payload=payload,
                idempotency_key=idempotency_key,
                channel=kwargs.get("channel"),
                destination=kwargs.get("destination"),
                template_name=kwargs.get("template_name"),
                template_params=kwargs.get("template_params"),
                max_attempts=kwargs.get("max_attempts", 3),
                scheduled_at=kwargs.get("scheduled_at"),
            )
            model = OutboxMapper.to_orm(entity)

        self._session.add(model)

    def add_message(self, **kwargs: Any) -> None:
        """Convenience method para add() com parâmetros nomeados."""
        self.add(message=None, **kwargs)

    def get(self, entity_id: UUID | str) -> OutboxMessage | None:
        """Busca mensagem por ID."""
        model = self._session.query(OutboxModel).filter_by(id=entity_id).first()
        return OutboxMapper.to_domain(model) if model else None

    def save(self, entity: OutboxMessage) -> None:
        """Salva/atualiza mensagem."""
        model = OutboxMapper.to_orm(entity)
        self._session.merge(model)

    def remove(self, entity: OutboxMessage) -> None:
        """Remove mensagem."""
        self._session.query(OutboxModel).filter_by(id=entity.id).delete()

    def get_pending(
        self, limit: int = 100, channels: list[str] | None = None
    ) -> list[OutboxMessage]:
        """Busca mensagens pendentes."""
        query = self._session.query(OutboxModel).filter_by(status="pending")

        if channels:
            query = query.filter(OutboxModel.channel.in_(channels))

        from sqlalchemy import case

        models = (
            query.order_by(
                case(
                    (OutboxModel.scheduled_at.isnot(None), OutboxModel.scheduled_at),
                    else_=OutboxModel.created_at,
                ).desc()
            )
            .limit(limit)
            .all()
        )
        return [dm for m in models if (dm := OutboxMapper.to_domain(m)) is not None]

    def mark_processing(self, message_id: UUID | str) -> bool:
        """Marca como processando."""
        result = (
            self._session.query(OutboxModel)
            .filter_by(id=message_id, status="pending")
            .update({"status": "processing"})
        )
        return result > 0

    def mark_sent(self, message_id: UUID | str, external_id: str | None = None) -> None:
        """Marca como enviada."""
        self._session.query(OutboxModel).filter_by(id=message_id).update(
            {
                "status": "sent",
                "provider_message_id": external_id,
                "sent_at": datetime.utcnow(),
            }
        )

    def mark_failed(
        self,
        message_id: UUID | str,
        error: str,
        will_retry: bool,
    ) -> None:
        """Marca como falhada."""
        self._session.query(OutboxModel).filter_by(id=message_id).update(
            {
                "retry_count": OutboxModel.retry_count + 1,
                "error_message": error,
                "status": "pending" if will_retry else "failed",
            }
        )

    def get_dead_letters(self, limit: int = 100) -> list[OutboxMessage]:
        """Busca mensagens em dead letter."""
        models = (
            self._session.query(OutboxModel)
            .filter(OutboxModel.retry_count >= OutboxModel.max_retries)
            .limit(limit)
            .all()
        )
        return [dm for m in models if (dm := OutboxMapper.to_domain(m)) is not None]

    def cleanup_old(self, older_than: datetime, statuses: list[str]) -> int:
        """Remove mensagens antigas."""
        result = (
            self._session.query(OutboxModel)
            .filter(
                and_(
                    OutboxModel.created_at < older_than,
                    OutboxModel.status.in_(statuses),
                )
            )
            .delete()
        )
        return result


class SQLAlchemyBookingRepository:
    """Repositório de Bookings com SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entity: Booking) -> None:
        model = BookingMapper.to_orm(entity)
        if model:
            self._session.add(model)

    def get(self, entity_id: UUID | str) -> Booking | None:
        model = self._session.query(BookingModel).filter_by(id=entity_id).first()
        return BookingMapper.to_domain(model) if model else None

    def save(self, entity: Booking) -> None:
        model = BookingMapper.to_orm(entity)
        if model:
            self._session.merge(model)

    def remove(self, entity: Booking) -> None:
        self._session.query(BookingModel).filter_by(id=entity.id).delete()

    def list_by_lead(self, lead_id: UUID | str) -> list[Booking]:
        models = self._session.query(BookingModel).filter_by(lead_id=lead_id).all()
        return [b for m in models if (b := BookingMapper.to_domain(m)) is not None]

    def list_upcoming(self, limit: int = 100) -> list[Booking]:
        from datetime import datetime

        now = datetime.now()
        models = (
            self._session.query(BookingModel)
            .filter(BookingModel.scheduled_at >= now)
            .order_by(BookingModel.scheduled_at.asc())
            .limit(limit)
            .all()
        )
        return [b for m in models if (b := BookingMapper.to_domain(m)) is not None]


class SQLAlchemyEnrollmentRepository:
    """Repositório de CadenceEnrollment com SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entity: CadenceEnrollment) -> None:
        model = CadenceEnrollmentMapper.to_orm(entity)
        if model:
            self._session.add(model)

    def get(self, entity_id: UUID | str) -> CadenceEnrollment | None:
        model = self._session.query(CadenceEnrollmentModel).filter_by(id=entity_id).first()
        return CadenceEnrollmentMapper.to_domain(model) if model else None

    def save(self, entity: CadenceEnrollment) -> None:
        model = CadenceEnrollmentMapper.to_orm(entity)
        if model:
            self._session.merge(model)

    def remove(self, entity: CadenceEnrollment) -> None:
        self._session.query(CadenceEnrollmentModel).filter_by(id=entity.id).delete()

    def get_by_lead(self, lead_id: UUID | str) -> CadenceEnrollment | None:
        model = self._session.query(CadenceEnrollmentModel).filter_by(lead_id=lead_id).first()
        return CadenceEnrollmentMapper.to_domain(model) if model else None

    def get_active(self, limit: int = 100) -> list[CadenceEnrollment]:
        models = (
            self._session.query(CadenceEnrollmentModel)
            .filter_by(status=EnrollmentStatus.ACTIVE)
            .order_by(CadenceEnrollmentModel.next_run_at.asc())
            .limit(limit)
            .all()
        )
        return [e for m in models if (e := CadenceEnrollmentMapper.to_domain(m)) is not None]


class SQLAlchemyInboundEventRepository:
    """Repositório de InboundEvent com SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entity: InboundEvent) -> None:
        model = InboundEventMapper.to_orm(entity)
        if model:
            self._session.add(model)

    def get(self, entity_id: UUID | str) -> InboundEvent | None:
        model = self._session.query(InboundEventModel).filter_by(id=entity_id).first()
        return InboundEventMapper.to_domain(model) if model else None

    def save(self, entity: InboundEvent) -> None:
        model = InboundEventMapper.to_orm(entity)
        if model:
            self._session.merge(model)

    def remove(self, entity: InboundEvent) -> None:
        self._session.query(InboundEventModel).filter_by(id=entity.id).delete()

    def get_unprocessed(self, limit: int = 100) -> list[InboundEvent]:
        models = (
            self._session.query(InboundEventModel)
            .filter_by(processed=False)
            .order_by(InboundEventModel.created_at.asc())
            .limit(limit)
            .all()
        )
        return [e for m in models if (e := InboundEventMapper.to_domain(m)) is not None]

    def exists_by_provider_id(self, provider_name: str, provider_event_id: str) -> bool:
        return (
            self._session.query(InboundEventModel)
            .filter_by(provider_name=provider_name, provider_event_id=provider_event_id)
            .first()
            is not None
        )


class SQLAlchemySuppressionRepository:
    """Repositório de SuppressionRecord com SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entity: SuppressionRecord) -> None:
        model = SuppressionRecordMapper.to_orm(entity)
        if model:
            self._session.add(model)

    def get(self, entity_id: UUID | str) -> SuppressionRecord | None:
        model = self._session.query(SuppressionListModel).filter_by(id=entity_id).first()
        return SuppressionRecordMapper.to_domain(model) if model else None

    def save(self, entity: SuppressionRecord) -> None:
        model = SuppressionRecordMapper.to_orm(entity)
        if model:
            self._session.merge(model)

    def remove(self, entity: SuppressionRecord) -> None:
        self._session.query(SuppressionListModel).filter_by(id=entity.id).delete()

    def get_by_phone(self, phone_e164: str) -> SuppressionRecord | None:
        model = self._session.query(SuppressionListModel).filter_by(phone_e164=phone_e164).first()
        return SuppressionRecordMapper.to_domain(model) if model else None

    def is_suppressed(self, phone_e164: str) -> bool:
        from datetime import datetime

        now = datetime.now()
        model = (
            self._session.query(SuppressionListModel)
            .filter_by(phone_e164=phone_e164)
            .filter(
                (SuppressionListModel.expires_at.is_(None))
                | (SuppressionListModel.expires_at > now)
            )
            .first()
        )
        return model is not None

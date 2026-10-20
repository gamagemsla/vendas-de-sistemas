from sqlalchemy import or_
from sqlalchemy.orm import Session

from vendas.domain.entities.outbox_payloads import validate_outbox_payload
from vendas.domain.policies.retry_policy import compute_next_retry_at
from vendas.domain.ports import Clock
from vendas.infrastructure.clock import SystemClock
from vendas.infrastructure.persistence.orm_models import OutboxModel, OutboxStatus


class SQLAlchemyOutboxRepository:
    def __init__(self, session: Session, clock: Clock | None = None) -> None:
        self._session = session
        self._clock = clock or SystemClock()

    def add(self, event_type: str, payload: dict, idempotency_key: str) -> None:
        # Valida payload antes de persistir
        validated_payload = validate_outbox_payload(event_type, payload)

        model = OutboxModel(
            event_type=event_type,
            payload=validated_payload,
            idempotency_key=idempotency_key,
            status=OutboxStatus.PENDING,
            retry_count=0,
        )
        self._session.add(model)

    def claim_pending(self, batch_size: int = 10) -> list[OutboxModel]:
        """Busca mensagens pendentes na outbox usando SKIP LOCKED para concorrência segura entre workers.
        Considera apenas mensagens cujo scheduled_at é None ou <= now.
        """
        now = self._clock.now()
        models = (
            self._session.query(OutboxModel)
            .filter(OutboxModel.status == OutboxStatus.PENDING)
            .filter(or_(OutboxModel.scheduled_at.is_(None), OutboxModel.scheduled_at <= now))
            .with_for_update(skip_locked=True)
            .limit(batch_size)
            .all()
        )
        return models

    def mark_as_sent(self, outbox_id: str) -> None:
        model = self._session.query(OutboxModel).filter_by(id=outbox_id).first()
        if model:
            model.status = OutboxStatus.SENT

    def mark_as_failed(self, outbox_id: str, error_message: str) -> None:
        model = self._session.query(OutboxModel).filter_by(id=outbox_id).first()
        if model:
            model.retry_count += 1
            if model.retry_count >= model.max_retries:
                model.status = OutboxStatus.DEAD_LETTER  # Usando o Enum
            else:
                model.status = OutboxStatus.PENDING  # Usando o Enum
                now = self._clock.now()
                model.scheduled_at = compute_next_retry_at(
                    now=now,
                    retry_count=model.retry_count,
                    jitter=True,
                )

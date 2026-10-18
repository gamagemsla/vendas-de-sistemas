from sqlalchemy.orm import Session

from vendas.infrastructure.persistence.orm_models import OutboxModel, OutboxStatus


class SQLAlchemyOutboxRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event_type: str, payload: dict, idempotency_key: str) -> None:
        model = OutboxModel(
            event_type=event_type,
            payload=payload,
            idempotency_key=idempotency_key,
            status="PENDING",
            attempts=0,
        )
        self._session.add(model)

    def claim_pending(self, batch_size: int = 10) -> list[OutboxModel]:
        """Busca mensagens pendentes na outbox usando SKIP LOCKED para concorrência segura entre workers."""
        models = (
            self._session.query(OutboxModel)
            .filter(OutboxModel.status == "PENDING")
            .with_for_update(skip_locked=True)
            .limit(batch_size)
            .all()
        )
        return models

    def mark_as_sent(self, outbox_id: str) -> None:
        model = self._session.query(OutboxModel).filter_by(id=outbox_id).first()
        if model:
            model.status = "SENT"

    def mark_as_failed(self, outbox_id: str, error_message: str) -> None:
        model = self._session.query(OutboxModel).filter_by(id=outbox_id).first()
        if model:
            model.retry_count += 1
            if model.retry_count >= 5:
                model.status = OutboxStatus.DEAD_LETTER  # Usando o Enum
            else:
                model.status = OutboxStatus.PENDING  # Usando o Enum

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vendas.domain.ports.outbox import OutboxQueryPort
from vendas.infrastructure.persistence.orm_models import OutboxModel


class SqlAlchemyOutboxQuery(OutboxQueryPort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_outbox(
        self,
        *,
        status: Sequence[str] | None = None,
        channel: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        stmt = select(OutboxModel)
        if status:
            stmt = stmt.where(OutboxModel.status.in_(status))
        if channel:
            stmt = stmt.where(OutboxModel.channel.in_(channel))
        stmt = stmt.order_by(OutboxModel.created_at.desc()).limit(limit).offset(offset)
        rows = self._session.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "event_type": r.event_type,
                "channel": r.channel,
                "status": r.status,
                "attempts": r.attempts,
                "max_attempts": r.max_attempts,
                "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def count_by_status(self) -> dict[str, int]:
        stmt = select(OutboxModel.status, func.count(OutboxModel.id)).group_by(OutboxModel.status)
        rows = self._session.execute(stmt).all()
        return {status: count for status, count in rows}

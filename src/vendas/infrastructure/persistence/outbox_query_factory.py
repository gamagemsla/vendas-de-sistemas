from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from vendas.domain.ports.outbox import OutboxQueryPort
from vendas.infrastructure.persistence.outbox_queries import SqlAlchemyOutboxQuery

SessionFactory = Callable[[], Session]
T = TypeVar("T")


class SessionFactoryOutboxQuery(OutboxQueryPort):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def _run(self, func: Callable[[SqlAlchemyOutboxQuery], T]) -> T:
        session: Session = self._session_factory()
        try:
            adapter = SqlAlchemyOutboxQuery(session)
            return func(adapter)
        finally:
            session.close()

    def list_outbox(
        self,
        *,
        status: Sequence[str] | None = None,
        channel: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._run(
            lambda a: a.list_outbox(
                status=status,
                channel=channel,
                limit=limit,
                offset=offset,
            )
        )

    def count_by_status(self) -> dict[str, int]:
        return self._run(lambda a: a.count_by_status())

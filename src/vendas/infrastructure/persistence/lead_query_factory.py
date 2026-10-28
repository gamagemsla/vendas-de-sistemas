from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from vendas.domain.ports.lead import LeadQueryPort
from vendas.infrastructure.persistence.lead_queries import SqlAlchemyLeadQuery

SessionFactory = Callable[[], Session]
T = TypeVar("T")


class SessionFactoryLeadQuery(LeadQueryPort):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def _run(self, func: Callable[[SqlAlchemyLeadQuery], T]) -> T:
        session: Session = self._session_factory()
        try:
            adapter = SqlAlchemyLeadQuery(session)
            return func(adapter)
        finally:
            session.close()

    def list_leads(
        self,
        *,
        search: str | None = None,
        status: Sequence[str] | None = None,
        grade: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._run(
            lambda a: a.list_leads(
                search=search,
                status=status,
                grade=grade,
                limit=limit,
                offset=offset,
            )
        )

    def count_by_status(self) -> dict[str, int]:
        return self._run(lambda a: a.count_by_status())

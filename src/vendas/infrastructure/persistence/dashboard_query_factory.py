from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from vendas.domain.ports.dashboard import DashboardQueryPort
from vendas.infrastructure.persistence.dashboard_queries import SqlAlchemyDashboardQuery

SessionFactory = Callable[[], Session]
T = TypeVar("T")


class SessionFactoryDashboardQuery(DashboardQueryPort):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def _run(self, func: Callable[[SqlAlchemyDashboardQuery], T]) -> T:
        session: Session = self._session_factory()
        try:
            adapter = SqlAlchemyDashboardQuery(session)
            return func(adapter)
        finally:
            session.close()

    def get_overview_kpis(self) -> dict[str, Any]:
        return self._run(lambda a: a.get_overview_kpis())

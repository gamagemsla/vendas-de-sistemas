from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from vendas.domain.ports.knowledge_base import KnowledgeBasePort
from vendas.infrastructure.knowledge_base import SqlAlchemyKnowledgeBase

SessionFactory = Callable[[], Session]
T = TypeVar("T")


class SessionFactoryKnowledgeBase(KnowledgeBasePort):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def _run(self, func: Callable[[SqlAlchemyKnowledgeBase], T]) -> T:
        session: Session = self._session_factory()
        try:
            adapter = SqlAlchemyKnowledgeBase(session)
            return func(adapter)
        finally:
            session.close()

    def preview(self, text: str, at: datetime | None = None) -> dict[str, Any]:
        return self._run(lambda a: a.preview(text, at=at))

    def find_services(
        self, text: str | None = None, at: datetime | None = None
    ) -> list[dict[str, Any]]:
        return self._run(lambda a: a.find_services(text=text, at=at))

    def list_services(self) -> list[dict[str, Any]]:
        return self._run(lambda a: a.list_services())

    def find_prices(self, service_id: str, at: datetime | None = None) -> list[dict[str, Any]]:
        return self._run(lambda a: a.find_prices(service_id=service_id, at=at))

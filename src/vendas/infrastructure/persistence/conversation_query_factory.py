from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from vendas.domain.ports.conversation import ConversationQueryPort
from vendas.infrastructure.persistence.conversation_queries import SqlAlchemyConversationQuery

SessionFactory = Callable[[], Session]
T = TypeVar("T")


class SessionFactoryConversationQuery(ConversationQueryPort):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def _run(self, func: Callable[[SqlAlchemyConversationQuery], T]) -> T:
        session: Session = self._session_factory()
        try:
            adapter = SqlAlchemyConversationQuery(session)
            return func(adapter)
        finally:
            session.close()

    def get_handoff_conversations(self) -> list[dict[str, Any]]:
        return self._run(lambda a: a.get_handoff_conversations())

    def get_conversation_history(self, conversation_id: str) -> list[dict[str, Any]]:
        return self._run(lambda a: a.get_conversation_history(conversation_id))

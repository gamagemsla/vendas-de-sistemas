from __future__ import annotations

from contextlib import AbstractContextManager
from types import TracebackType
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from vendas.domain.ports import ConversationLock


class _PgLockContext(AbstractContextManager[None]):
    def __init__(self, session: Session, lead_id: UUID) -> None:
        self._session = session
        self._lead_id = lead_id

    def __enter__(self) -> None:
        lock_key_sql = "('x' || substr(md5(:lid), 1, 16))::bit(64)::bigint"
        self._session.execute(
            text(f"SELECT pg_advisory_xact_lock({lock_key_sql})"),
            {"lid": str(self._lead_id)},
        )

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # pg_advisory_xact_lock released automatically at transaction end
        return None


class PgAdvisoryConversationLock(ConversationLock):
    """Implementação de lock por conversa usando advisory locks do PostgreSQL.

    O lock é transacional (pg_advisory_xact_lock) e liberado automaticamente
    no commit ou rollback da transação atual.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def acquire(self, lead_id: UUID) -> AbstractContextManager[None]:
        return _PgLockContext(self._session, lead_id)

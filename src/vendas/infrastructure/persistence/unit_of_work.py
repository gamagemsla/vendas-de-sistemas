from types import TracebackType
from typing import Any, Self

from sqlalchemy.orm import Session, sessionmaker

from vendas.infrastructure.persistence.repositories import SQLAlchemyLeadRepository


class SQLAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None
        self.leads: SQLAlchemyLeadRepository | None = None
        self.conversations: Any = None
        self.outbox: Any = None
        self.enrollments: Any = None
        self.bookings: Any = None
        self.inbound_events: Any = None
        self.suppression: Any = None

    def __enter__(self) -> Self:
        self.session = self._session_factory()
        self.leads = SQLAlchemyLeadRepository(self.session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type:
            self.rollback()
        if self.session:
            self.session.close()

    def commit(self) -> None:
        if self.session:
            self.session.commit()

    def rollback(self) -> None:
        if self.session:
            self.session.rollback()

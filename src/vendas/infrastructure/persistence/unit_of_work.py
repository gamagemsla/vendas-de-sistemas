from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from vendas.domain.ports import Clock
from vendas.infrastructure.persistence.catalog_repository import SqlAlchemyCatalogRepository
from vendas.infrastructure.persistence.repositories import (
    SQLAlchemyBookingRepository,
    SQLAlchemyConversationRepository,
    SQLAlchemyEnrollmentRepository,
    SQLAlchemyInboundEventRepository,
    SQLAlchemyLeadRepository,
    SQLAlchemyOutboxRepository,
    SQLAlchemySuppressionRepository,
)


class SQLAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session], clock: Clock) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self.session: Session | None = None
        self.leads: SQLAlchemyLeadRepository | None = None
        self.conversations: SQLAlchemyConversationRepository | None = None
        self.outbox: SQLAlchemyOutboxRepository | None = None
        self.enrollments: SQLAlchemyEnrollmentRepository | None = None
        self.bookings: SQLAlchemyBookingRepository | None = None
        self.inbound_events: SQLAlchemyInboundEventRepository | None = None
        self.suppression: SQLAlchemySuppressionRepository | None = None
        self.catalog: SqlAlchemyCatalogRepository | None = None

    def __enter__(self) -> Self:
        self.session = self._session_factory()
        self.leads = SQLAlchemyLeadRepository(self.session)
        self.conversations = SQLAlchemyConversationRepository(self.session, self._clock)
        self.outbox = SQLAlchemyOutboxRepository(self.session, self._clock)
        self.enrollments = SQLAlchemyEnrollmentRepository(self.session)
        self.bookings = SQLAlchemyBookingRepository(self.session, self._clock)
        self.inbound_events = SQLAlchemyInboundEventRepository(self.session)
        self.suppression = SQLAlchemySuppressionRepository(self.session, self._clock)
        self.catalog = SqlAlchemyCatalogRepository(self.session, self._clock)
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

from __future__ import annotations

from sqlalchemy import create_engine

from vendas.bootstrap.settings import settings
from vendas.domain.ports import SuppressionListPort
from vendas.domain.value_objects import Phone
from vendas.infrastructure.clock import SystemClock
from vendas.infrastructure.persistence.repositories import SQLAlchemySuppressionRepository


class SQLAlchemySuppressionPort(SuppressionListPort):
    """Adapter that uses SQLAlchemySuppressionRepository with a fresh session per call."""

    def __init__(self) -> None:
        self._engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        self._clock = SystemClock()

    def is_suppressed(self, phone: Phone, email: str | None = None) -> bool:
        from sqlalchemy.orm import sessionmaker

        session_factory = sessionmaker(
            bind=self._engine, autoflush=False, autocommit=False, expire_on_commit=False
        )
        with session_factory() as session:
            repo = SQLAlchemySuppressionRepository(session, self._clock)
            return repo.is_suppressed(phone, email)

"""Teste para garantir que SQLAlchemyUnitOfWork inicializa todos os repositórios do protocolo."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from vendas.domain.ports import SystemClock
from vendas.infrastructure.persistence.base import Base
from vendas.infrastructure.persistence.unit_of_work import SQLAlchemyUnitOfWork


def test_uow_initializes_all_repositories():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    clock = SystemClock()

    with SQLAlchemyUnitOfWork(SessionLocal, clock) as uow:
        # Todos os atributos de repositório devem estar instanciados (não None)
        assert uow.leads is not None
        assert uow.conversations is not None
        assert uow.outbox is not None
        assert uow.enrollments is not None
        assert uow.bookings is not None
        assert uow.inbound_events is not None
        assert uow.suppression is not None
        assert uow.catalog is not None

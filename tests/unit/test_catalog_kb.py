"""Teste de integração da KnowledgeBase: preço desativado não deve ser retornado."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vendas.application.commands.catalog import (
    CreatePriceCommand,
    CreateServiceCommand,
    DeactivatePriceCommand,
)
from vendas.infrastructure.clock import SystemClock
from vendas.infrastructure.knowledge_base import SqlAlchemyKnowledgeBase
from vendas.infrastructure.persistence.base import Base
from vendas.infrastructure.persistence.catalog_repository import SqlAlchemyCatalogRepository


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def clock() -> SystemClock:
    return SystemClock()


@pytest.fixture
def catalog_repo(db_session: Session, clock: SystemClock) -> SqlAlchemyCatalogRepository:
    return SqlAlchemyCatalogRepository(db_session, clock)


@pytest.fixture
def knowledge_base(db_session: Session) -> SqlAlchemyKnowledgeBase:
    return SqlAlchemyKnowledgeBase(db_session)


def test_deactivate_price_removes_from_knowledge_base(
    catalog_repo: SqlAlchemyCatalogRepository,
    knowledge_base: SqlAlchemyKnowledgeBase,
    clock: SystemClock,
    db_session: Session,
) -> None:
    # cria serviço
    service = CreateServiceCommand(catalog_repo, clock).execute(
        name="Serviço Teste KB",
        description="desc",
        actor_id="admin-1",
        actor_role="admin",
    )
    db_session.commit()
    service_id = service.id

    now = datetime.now(UTC)

    # cria preço ativo
    price = CreatePriceCommand(catalog_repo, clock).execute(
        service_id=service_id,
        price_cents=1500,
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=10),
        actor_id="admin-1",
        actor_role="admin",
    )
    db_session.commit()
    price_id = price.id

    # knowledge base deve retornar o preço
    knowledge_base.invalidate()
    prices = knowledge_base.find_prices(service_id=str(service_id), at=now)
    assert any(p["id"] == str(price_id) for p in prices)

    # desativa preço
    DeactivatePriceCommand(catalog_repo, clock).execute(
        price_id=price_id,
        actor_id="admin-1",
        actor_role="admin",
    )
    db_session.commit()

    # knowledge base não deve mais retornar o preço desativado
    knowledge_base.invalidate()
    prices_after = knowledge_base.find_prices(service_id=str(service_id), at=now)
    assert not any(p["id"] == str(price_id) for p in prices_after)

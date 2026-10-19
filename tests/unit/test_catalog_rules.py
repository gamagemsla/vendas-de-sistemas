from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vendas.application.commands.catalog import (
    CatalogValidationError,
    CreatePriceCommand,
    CreateServiceCommand,
    DeactivateServiceCommand,
)
from vendas.domain.ports import SystemClock
from vendas.infrastructure.persistence.base import Base
from vendas.infrastructure.persistence.catalog_repository import SqlAlchemyCatalogRepository
from vendas.infrastructure.persistence.orm_models import CatalogService


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.drop_all(bind=engine)
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


def test_price_zero_is_rejected(
    catalog_repo: SqlAlchemyCatalogRepository, clock: SystemClock
) -> None:
    with pytest.raises(CatalogValidationError, match="maior que zero"):
        CreatePriceCommand(catalog_repo, clock).execute(
            service_id=uuid4(),
            price_cents=0,
            valid_from=datetime.now(UTC),
        )


def test_overlapping_price_windows_are_rejected(
    catalog_repo: SqlAlchemyCatalogRepository, clock: SystemClock, db_session: Session
) -> None:
    service = CreateServiceCommand(catalog_repo, clock).execute(
        name="Servico Base",
        description="Desc",
        actor_id="admin-1",
        actor_role="admin",
    )
    db_session.commit()
    service_id = service.id
    now = datetime.now(UTC)

    CreatePriceCommand(catalog_repo, clock).execute(
        service_id=service_id,
        price_cents=1500,
        valid_from=now - timedelta(days=7),
        valid_to=now + timedelta(days=7),
        actor_id="admin-1",
        actor_role="admin",
    )
    db_session.commit()

    with pytest.raises(CatalogValidationError, match="sobreposta"):
        CreatePriceCommand(catalog_repo, clock).execute(
            service_id=service_id,
            price_cents=2000,
            valid_from=now - timedelta(days=2),
            valid_to=now + timedelta(days=2),
            actor_id="admin-1",
            actor_role="admin",
        )


def test_deactivate_service_instead_of_delete(
    catalog_repo: SqlAlchemyCatalogRepository, clock: SystemClock, db_session: Session
) -> None:
    service = CreateServiceCommand(catalog_repo, clock).execute(
        name="Servico de teste",
        description="Descricao",
        actor_id="admin-1",
        actor_role="admin",
    )
    db_session.commit()

    DeactivateServiceCommand(catalog_repo, clock).execute(
        service_id=service.id,
        actor_id="admin-1",
        actor_role="admin",
    )
    db_session.commit()

    stored = db_session.query(CatalogService).filter_by(id=service.id).one()
    assert stored.active is False

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
from vendas.infrastructure.persistence.base import Base


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


def test_price_zero_is_rejected(db_session: Session) -> None:
    with pytest.raises(CatalogValidationError, match="maior que zero"):
        CreatePriceCommand().execute(
            db_session,
            service_id=uuid4(),
            price_cents=0,
            valid_from=datetime.now(UTC),
        )


def test_overlapping_price_windows_are_rejected(db_session: Session) -> None:
    service_id = uuid4()
    now = datetime.now(UTC)
    CreatePriceCommand().execute(
        db_session,
        service_id=service_id,
        price_cents=1500,
        valid_from=now - timedelta(days=7),
        valid_to=now + timedelta(days=7),
    )
    db_session.commit()

    with pytest.raises(CatalogValidationError, match="sobreposta"):
        CreatePriceCommand().execute(
            db_session,
            service_id=service_id,
            price_cents=2000,
            valid_from=now - timedelta(days=2),
            valid_to=now + timedelta(days=2),
        )


def test_deactivate_service_instead_of_delete(db_session: Session) -> None:
    service = CreateServiceCommand().execute(
        db_session,
        name="Serviço de teste",
        description="Descrição",
        actor_id="admin-1",
        actor_role="admin",
    )
    db_session.commit()

    DeactivateServiceCommand().execute(
        db_session,
        service_id=service.id,
        actor_id="admin-1",
        actor_role="admin",
    )
    db_session.commit()

    stored = db_session.query(type(service)).filter_by(id=service.id).one()
    assert stored.active is False

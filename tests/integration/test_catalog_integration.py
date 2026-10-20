from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vendas.application.commands.catalog import (
    CreatePriceCommand,
    CreateServiceCommand,
    UpdatePriceCommand,
)
from vendas.bootstrap.settings import settings
from vendas.domain.ports import SystemClock
from vendas.infrastructure.knowledge_base import SqlAlchemyKnowledgeBase
from vendas.infrastructure.persistence.base import Base
from vendas.infrastructure.persistence.catalog_repository import SqlAlchemyCatalogRepository
from vendas.infrastructure.persistence.orm_models import AuditLog, KnowledgeChangeLog
from vendas.interfaces.api.app import app


def _make_session() -> Session:
    db_url = settings.DATABASE_URL.replace("@postgres:", "@localhost:")
    engine = create_engine(db_url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return SessionLocal()


def _make_catalog_repo(session: Session) -> SqlAlchemyCatalogRepository:
    clock = SystemClock()
    return SqlAlchemyCatalogRepository(session, clock)


def _make_clock() -> SystemClock:
    return SystemClock()


def test_price_update_refreshes_knowledge_base_and_excludes_old_window() -> None:
    session = _make_session()
    catalog_repo = _make_catalog_repo(session)
    clock = _make_clock()
    try:
        service = CreateServiceCommand(catalog_repo, clock).execute(
            name=f"Atendimento KB {uuid4()}",
            description="Catalog integration",
            actor_id="admin-1",
            actor_role="admin",
        )
        now = datetime.now(UTC)

        old_price = CreatePriceCommand(catalog_repo, clock).execute(
            service_id=service.id,
            price_cents=900,
            valid_from=now - timedelta(days=15),
            valid_to=now - timedelta(days=10),
            actor_id="admin-1",
            actor_role="admin",
        )
        current_price = CreatePriceCommand(catalog_repo, clock).execute(
            service_id=service.id,
            price_cents=1500,
            valid_from=now - timedelta(days=2),
            valid_to=now + timedelta(days=5),
            actor_id="admin-1",
            actor_role="admin",
        )
        session.commit()

        kb = SqlAlchemyKnowledgeBase(session)
        kb.invalidate()
        UpdatePriceCommand(catalog_repo, clock).execute(
            price_id=current_price.id,
            price_cents=2500,
            valid_from=now - timedelta(days=1),
            valid_to=now + timedelta(days=7),
            actor_id="admin-1",
            actor_role="admin",
        )
        session.commit()
        kb.invalidate()

        prices = kb.find_prices(service_id=str(service.id), at=now)
        assert [price["price_cents"] for price in prices] == [2500]
        assert all(price["id"] != str(old_price.id) for price in prices)
        preview = kb.preview("Atendimento", at=now)
        assert preview["services"][0]["current_price_cents"] == 2500
    finally:
        session.close()


def test_changes_write_knowledge_and_audit_logs() -> None:
    session = _make_session()
    catalog_repo = _make_catalog_repo(session)
    clock = _make_clock()
    try:
        service = CreateServiceCommand(catalog_repo, clock).execute(
            name=f"Servico Log {uuid4()}",
            description="Log test",
            actor_id="admin-1",
            actor_role="admin",
        )
        price = CreatePriceCommand(catalog_repo, clock).execute(
            service_id=service.id,
            price_cents=1200,
            valid_from=datetime.now(UTC),
            valid_to=datetime.now(UTC) + timedelta(days=3),
            actor_id="admin-1",
            actor_role="admin",
        )
        session.commit()

        UpdatePriceCommand(catalog_repo, clock).execute(
            price_id=price.id,
            price_cents=1800,
            valid_from=datetime.now(UTC),
            valid_to=datetime.now(UTC) + timedelta(days=10),
            actor_id="admin-1",
            actor_role="admin",
        )
        session.commit()

        knowledge_logs = (
            session.query(KnowledgeChangeLog).filter_by(entity_type="catalog_price").all()
        )
        audit_logs = session.query(AuditLog).filter_by(entity_type="catalog_price").all()
        assert len(knowledge_logs) >= 2
        assert len(audit_logs) >= 2
    finally:
        session.close()


def test_catalog_routes_require_admin_or_auth() -> None:
    client = TestClient(app)
    admin_headers = {
        "Authorization": "Bearer token",
        "X-User-Role": "admin",
        "X-User-Id": "admin-1",
    }
    service_payload = {"name": f"Servico API {uuid4()}", "description": "api route"}
    created = client.post("/catalog/services", json=service_payload, headers=admin_headers)
    assert created.status_code == 201, created.text
    service_id = created.json()["id"]

    forbidden = client.post(
        "/catalog/prices",
        json={
            "service_id": service_id,
            "price_cents": 2000,
            "valid_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "valid_to": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
        },
        headers={
            "Authorization": "Bearer token",
            "X-User-Role": "operator",
            "X-User-Id": "op-1",
        },
    )
    assert forbidden.status_code == 403

    unauthorized = client.post(
        "/catalog/prices",
        json={
            "service_id": service_id,
            "price_cents": 2000,
            "valid_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "valid_to": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
        },
    )
    assert unauthorized.status_code == 401

    client.close()

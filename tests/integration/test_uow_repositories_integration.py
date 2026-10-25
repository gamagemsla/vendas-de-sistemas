"""Testes de integração para UnitOfWork e Repositórios (PostgreSQL real)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import vendas.infrastructure.persistence.orm_models  # noqa: F401
from vendas.bootstrap.settings import settings
from vendas.domain.entities.booking import Booking
from vendas.domain.entities.lead import Lead
from vendas.domain.entities.suppression_record import SuppressionReason, SuppressionRecord
from vendas.domain.value_objects import Cnpj, Phone
from vendas.infrastructure.clock import SystemClock
from vendas.infrastructure.persistence.base import Base
from vendas.infrastructure.persistence.repositories import (
    SQLAlchemyBookingRepository,
    SQLAlchemyLeadRepository,
    SQLAlchemySuppressionRepository,
)
from vendas.infrastructure.persistence.unit_of_work import SQLAlchemyUnitOfWork


def _make_session() -> Session:
    """Cria uma sessão limpa para cada teste, recriando tabelas e enums."""
    db_url = settings.DATABASE_URL  # aponta para vendas_db_test via conftest.py
    engine = create_engine(db_url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    # Limpar ENUMs do Postgres que persistem após drop_all
    if engine.dialect.name == "postgresql":
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            result = conn.execute(
                text(
                    "SELECT typname FROM pg_type t "
                    "JOIN pg_namespace n ON t.typnamespace = n.oid "
                    "WHERE n.nspname = 'public' AND t.typtype = 'e'"
                )
            )
            for row in result:
                conn.execute(text(f"DROP TYPE IF EXISTS public.{row.typname} CASCADE"))
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return SessionLocal()


def _make_clock() -> SystemClock:
    return SystemClock()


# ---------------------------------------------------------------------------
# Cenário 1 – UniqueConstraint em Lead (phone_e164 e cnpj)
# ---------------------------------------------------------------------------
def test_lead_unique_phone_raises_integrity_error() -> None:
    session = _make_session()
    repo = SQLAlchemyLeadRepository(session)
    clock = _make_clock()
    try:
        now = clock.now()
        phone = Phone("+5511999999999")
        lead1 = Lead.create(name="Lead Um", phone=phone, at=now)
        lead2 = Lead.create(name="Lead Dois", phone=phone, at=now)  # mesmo telefone

        repo.add(lead1)
        session.flush()
        repo.add(lead2)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
    finally:
        session.close()


def test_lead_unique_cnpj_raises_integrity_error() -> None:
    session = _make_session()
    repo = SQLAlchemyLeadRepository(session)
    clock = _make_clock()
    try:
        now = clock.now()
        cnpj = Cnpj("12.345.678/0001-95")
        lead1 = Lead.create(name="Lead Um", phone="+5511999999999", cnpj=cnpj, at=now)
        lead2 = Lead.create(
            name="Lead Dois", phone="+5511988888888", cnpj=cnpj, at=now
        )  # mesmo CNPJ

        repo.add(lead1)
        session.flush()
        repo.add(lead2)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Cenário 2 – Rollback atômico do UnitOfWork
# ---------------------------------------------------------------------------
def test_uow_rollback_on_exception() -> None:
    """Se uma exceção ocorrer dentro do bloco `with uow:`, nada deve ser persistido."""
    db_url = settings.DATABASE_URL
    engine = create_engine(db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    clock = _make_clock()
    uow = SQLAlchemyUnitOfWork(SessionLocal, clock)

    phone = Phone("+5511977777777")
    now = clock.now()
    lead = Lead.create(name="Lead Rollback", phone=phone, at=now)

    # Dentro do contexto, adicionamos o lead e depois levantamos erro
    with pytest.raises(RuntimeError), uow:
        uow.leads.add(lead)
        # Simula falha de negócio
        raise RuntimeError("falha simulada")

    # Nova sessão para verificar que o lead NÃO foi persistido
    verify_session = SessionLocal()
    try:
        repo = SQLAlchemyLeadRepository(verify_session)
        found = repo.get_by_phone(phone)
        assert found is None, "Rollback falhou: lead foi persistido mesmo após exceção"
    finally:
        verify_session.close()


# ---------------------------------------------------------------------------
# Cenário 3 – Booking com datetime timezone-aware
# ---------------------------------------------------------------------------
def test_booking_timezone_aware_persistence() -> None:
    session = _make_session()
    repo = SQLAlchemyBookingRepository(session, _make_clock())
    try:
        # Cria um lead pré-requisito (sem unique conflict)
        lead_repo = SQLAlchemyLeadRepository(session)
        clock = _make_clock()
        now = clock.now()
        lead = Lead.create(name="Lead Booking", phone="+5511966666666", at=now)
        lead_repo.add(lead)
        session.flush()

        # Agendamento com timezone America/Sao_Paulo
        tz = ZoneInfo("America/Sao_Paulo")
        scheduled = datetime(2025, 12, 25, 10, 30, tzinfo=tz)  # 25/12/2025 10:30 -03:00
        booking = Booking.create(
            lead_id=lead.id,
            scheduled_at=scheduled,
            timezone="America/Sao_Paulo",
            duration_minutes=45,
            title="Reunião de qualificação",
            at=now,
        )
        repo.add(booking)
        session.commit()

        # Recupera e valida preservação do tzinfo
        fetched = repo.get(booking.id)
        assert fetched is not None
        assert fetched.scheduled_at.tzinfo is not None, "scheduled_at deve ser timezone-aware"
        # O instante no tempo deve ser igual (convertido para UTC internamente)
        assert fetched.scheduled_at.astimezone(UTC) == scheduled.astimezone(UTC)
        assert fetched.timezone == "America/Sao_Paulo"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Cenário 4 (Bônus) – SuppressionRepository CRUD
# ---------------------------------------------------------------------------
def test_suppression_repository_crud() -> None:
    session = _make_session()
    repo = SQLAlchemySuppressionRepository(session, _make_clock())
    try:
        now = datetime.now(UTC)
        phone = "+5511955555555"

        # Inserção
        record = SuppressionRecord.create(
            phone_e164=phone,
            reason=SuppressionReason.OPT_OUT,
            source="whatsapp_opt_out",
            notes="Usuário pediu remoção",
            expires_at=None,  # permanente
            created_at=now,
        )
        repo.add(record)
        session.commit()

        # Consulta por telefone
        fetched = repo.get_by_phone(phone)
        assert fetched is not None
        assert fetched.phone_e164 == phone
        assert fetched.reason == SuppressionReason.OPT_OUT
        assert fetched.expires_at is None
        assert fetched.is_active(now) is True

        # Verifica is_suppressed
        assert repo.is_suppressed(Phone(phone)) is True

        # Tenta inserir duplicado (unique phone_e164) -> IntegrityError
        dup = SuppressionRecord.create(
            phone_e164=phone,
            reason=SuppressionReason.DNC,
            source="manual",
            created_at=now,
        )
        repo.add(dup)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
    finally:
        session.close()

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from vendas.bootstrap.settings import settings
from vendas.domain.ports import EntityId, LegalBasisPort
from vendas.domain.value_objects import Phone
from vendas.infrastructure.persistence.orm_models import ConsentRecord


class SQLAlchemyLegalBasisPort(LegalBasisPort):
    """Implementação que consulta a tabela consent_records para verificar base legal ativa."""

    def __init__(self) -> None:
        self._engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

    def has_legal_basis(self, lead_id: EntityId, phone: Phone) -> bool:
        session_factory = sessionmaker(
            bind=self._engine, autoflush=False, autocommit=False, expire_on_commit=False
        )
        with session_factory() as session:
            # Verifica se existe consentimento ativo (granted=True, não revogado) para o telefone
            consent = (
                session.query(ConsentRecord)
                .filter(
                    ConsentRecord.phone_e164 == phone.value,
                    ConsentRecord.granted.is_(True),
                    ConsentRecord.revoked_at.is_(None),
                )
                .first()
            )
            return consent is not None

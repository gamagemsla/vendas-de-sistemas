from __future__ import annotations

from uuid import UUID

from vendas.domain.ports import LegalBasisPort


class SQLAlchemyLegalBasisPort(LegalBasisPort):
    """Implementação simples que sempre retorna True (base legal assumida)."""

    def has_legal_basis(self, lead_id: UUID) -> bool:  # type: ignore[override]
        # TODO: implement real check against a legal_basis table
        return True

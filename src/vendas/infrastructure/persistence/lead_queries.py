from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from vendas.domain.ports.lead import LeadQueryPort
from vendas.infrastructure.persistence.orm_models import LeadModel, LeadStatus


def _derive_grade(score: int | None) -> str:
    if score is None:
        return "UNCLASSIFIED"
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


class SqlAlchemyLeadQuery(LeadQueryPort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_leads(
        self,
        *,
        search: str | None = None,
        status: Sequence[str] | None = None,
        grade: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        stmt = select(LeadModel)
        if search:
            stmt = stmt.where(
                or_(
                    LeadModel.company_name.ilike(f"%{search}%"),
                    LeadModel.name.ilike(f"%{search}%"),
                )
            )
        if status:
            stmt = stmt.where(LeadModel.status.in_([LeadStatus(s) for s in status]))
        stmt = stmt.order_by(LeadModel.created_at.desc()).limit(limit).offset(offset)
        rows = self._session.execute(stmt).scalars().all()
        result = []
        for r in rows:
            g = _derive_grade(r.qualification_score)
            if grade and g not in grade:
                continue
            result.append(
                {
                    "id": str(r.id),
                    "company_name": r.company_name,
                    "contact_name": r.name,
                    "phone": r.phone_e164,
                    "email": r.email,
                    "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                    "grade": g,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
            )
        return result

    def count_by_status(self) -> dict[str, int]:
        stmt = select(LeadModel.status, func.count(LeadModel.id)).group_by(LeadModel.status)
        rows = self._session.execute(stmt).all()
        return {
            status.value if hasattr(status, "value") else str(status): count
            for status, count in rows
        }

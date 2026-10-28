from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from vendas.domain.ports import BudgetTracker
from vendas.domain.ports.budget import BudgetQueryPort
from vendas.domain.ports.conversation import ConversationQueryPort
from vendas.domain.ports.dashboard import DashboardQueryPort
from vendas.domain.ports.knowledge_base import KnowledgeBasePort
from vendas.domain.ports.lead import LeadQueryPort
from vendas.domain.ports.outbox import OutboxQueryPort
from vendas.infrastructure.knowledge_base import SqlAlchemyKnowledgeBase
from vendas.infrastructure.persistence.orm_models import (
    ConversationModel,
    LeadModel,
    LeadStatus,
    MessageModel,
    OutboxModel,
)

# ---------------------------------------------------------------------------
# Query implementations (receive a Session)
# ---------------------------------------------------------------------------


class SqlAlchemyBudgetQuery(BudgetQueryPort):
    """Agrega os trackers de orçamento dos provedores."""

    def __init__(
        self,
        apify_tracker: BudgetTracker,
        firecrawl_tracker: BudgetTracker,
        gemini_tracker: BudgetTracker,
    ) -> None:
        self._trackers = {
            "apify": apify_tracker,
            "firecrawl": firecrawl_tracker,
            "gemini": gemini_tracker,
        }

    def get_daily_costs(self) -> dict[str, int]:
        return {name: tracker.used_today() for name, tracker in self._trackers.items()}


class SqlAlchemyConversationQuery:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_handoff_conversations(self) -> list[dict[str, Any]]:
        conversations = (
            self._session.query(ConversationModel)
            .filter(ConversationModel.state == "HANDOFF")
            .all()
        )
        result = []
        for c in conversations:
            lead = c.lead
            result.append(
                {
                    "id": str(c.id),
                    "lead_id": str(c.lead_id) if c.lead_id else None,
                    "lead_name": lead.name if lead else "Desconhecido",
                    "contact_phone": c.contact_phone,
                    "channel": c.channel.value if hasattr(c.channel, "value") else str(c.channel),
                }
            )
        return result

    def get_conversation_history(self, conversation_id: str) -> list[dict[str, Any]]:
        conv = (
            self._session.query(ConversationModel)
            .filter(ConversationModel.id == conversation_id)
            .first()
        )
        if not conv:
            return []
        messages = (
            self._session.query(MessageModel)
            .filter(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
            .all()
        )
        history = []
        for m in messages:
            direction = "outbound" if m.direction.value == "outbound" else "inbound"
            history.append(
                {
                    "id": str(m.id),
                    "direction": direction,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
            )
        return history


class SqlAlchemyDashboardQuery:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_overview_kpis(self) -> dict[str, Any]:
        query = self._session.query(LeadModel)
        total_leads = query.count()
        qualified_leads = query.filter(LeadModel.status == "QUALIFIED").count()
        opted_out_leads = query.filter(LeadModel.status == "OPTED_OUT").count()
        in_cadence = query.filter(LeadModel.status == "IN_CADENCE").count()
        conversion_rate = (qualified_leads / total_leads * 100) if total_leads > 0 else 0.0

        return {
            "total_leads": total_leads,
            "qualified_leads": qualified_leads,
            "opted_out_leads": opted_out_leads,
            "in_cadence": in_cadence,
            "conversion_rate": round(conversion_rate, 2),
        }


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


class SqlAlchemyOutboxQuery(OutboxQueryPort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_outbox(
        self,
        *,
        status: Sequence[str] | None = None,
        channel: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        stmt = select(OutboxModel)
        if status:
            stmt = stmt.where(OutboxModel.status.in_(status))
        if channel:
            stmt = stmt.where(OutboxModel.channel.in_(channel))
        stmt = stmt.order_by(OutboxModel.created_at.desc()).limit(limit).offset(offset)
        rows = self._session.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "event_type": r.event_type,
                "channel": r.channel,
                "status": r.status,
                "attempts": r.attempts,
                "max_attempts": r.max_attempts,
                "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def count_by_status(self) -> dict[str, int]:
        stmt = select(OutboxModel.status, func.count(OutboxModel.id)).group_by(OutboxModel.status)
        rows = self._session.execute(stmt).all()
        return {status: count for status, count in rows}


# ---------------------------------------------------------------------------
# Factory adapters (receive a session_factory) – kept for compatibility
# ---------------------------------------------------------------------------

SessionFactory = Callable[[], Session]
T = TypeVar("T")


class SessionFactoryConversationQuery(ConversationQueryPort):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def _run(self, func: Callable[[SqlAlchemyConversationQuery], T]) -> T:
        session: Session = self._session_factory()
        try:
            adapter = SqlAlchemyConversationQuery(session)
            return func(adapter)
        finally:
            session.close()

    def get_handoff_conversations(self) -> list[dict[str, Any]]:
        return self._run(lambda a: a.get_handoff_conversations())

    def get_conversation_history(self, conversation_id: str) -> list[dict[str, Any]]:
        return self._run(lambda a: a.get_conversation_history(conversation_id))


class SessionFactoryDashboardQuery(DashboardQueryPort):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def _run(self, func: Callable[[SqlAlchemyDashboardQuery], T]) -> T:
        session: Session = self._session_factory()
        try:
            adapter = SqlAlchemyDashboardQuery(session)
            return func(adapter)
        finally:
            session.close()

    def get_overview_kpis(self) -> dict[str, Any]:
        return self._run(lambda a: a.get_overview_kpis())


class SessionFactoryLeadQuery(LeadQueryPort):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def _run(self, func: Callable[[SqlAlchemyLeadQuery], T]) -> T:
        session: Session = self._session_factory()
        try:
            adapter = SqlAlchemyLeadQuery(session)
            return func(adapter)
        finally:
            session.close()

    def list_leads(
        self,
        *,
        search: str | None = None,
        status: Sequence[str] | None = None,
        grade: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._run(
            lambda a: a.list_leads(
                search=search,
                status=status,
                grade=grade,
                limit=limit,
                offset=offset,
            )
        )

    def count_by_status(self) -> dict[str, int]:
        return self._run(lambda a: a.count_by_status())


class SessionFactoryOutboxQuery(OutboxQueryPort):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def _run(self, func: Callable[[SqlAlchemyOutboxQuery], T]) -> T:
        session: Session = self._session_factory()
        try:
            adapter = SqlAlchemyOutboxQuery(session)
            return func(adapter)
        finally:
            session.close()

    def list_outbox(
        self,
        *,
        status: Sequence[str] | None = None,
        channel: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._run(
            lambda a: a.list_outbox(
                status=status,
                channel=channel,
                limit=limit,
                offset=offset,
            )
        )

    def count_by_status(self) -> dict[str, int]:
        return self._run(lambda a: a.count_by_status())


class SessionFactoryKnowledgeBase(KnowledgeBasePort):
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def _run(self, func: Callable[[SqlAlchemyKnowledgeBase], T]) -> T:
        session: Session = self._session_factory()
        try:
            adapter = SqlAlchemyKnowledgeBase(session)
            return func(adapter)
        finally:
            session.close()

    def preview(self, text: str, at: datetime | None = None) -> dict[str, Any]:
        return self._run(lambda a: a.preview(text, at=at))

    def find_services(
        self, text: str | None = None, at: datetime | None = None
    ) -> list[dict[str, Any]]:
        return self._run(lambda a: a.find_services(text=text, at=at))

    def list_services(self) -> list[dict[str, Any]]:
        return self._run(lambda a: a.list_services())

    def find_prices(self, service_id: str, at: datetime | None = None) -> list[dict[str, Any]]:
        return self._run(lambda a: a.find_prices(service_id=service_id, at=at))

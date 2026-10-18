from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from vendas.domain.ports.catalog import CatalogRepository
from vendas.domain.ports import Clock
from vendas.infrastructure.persistence.orm_models import (
    CatalogService,
    CatalogPrice,
    FaqEntry,
    KnowledgeChangeLog,
    AuditLog,
)


class SqlAlchemyCatalogRepository(CatalogRepository):
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    def _now(self) -> datetime:
        return self._clock.now()

    def _log_change(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        action: str,
        old_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
        actor_id: str | None,
        actor_role: str,
    ) -> None:
        chg = KnowledgeChangeLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            actor_id=UUID(actor_id) if actor_id else None,
            actor_role=actor_role,
        )
        self._session.add(chg)

        audit = AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            actor_id=actor_id,
            actor_type="user",
            changes={"old": old_value, "new": new_value},
        )
        self._session.add(audit)

    # --- Services ---
    def add_service(
        self,
        name: str,
        description: str,
        category: str | None,
        requires_human_approval: bool,
        discount_allowed: bool,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        service = CatalogService(
            name=name.strip(),
            description=description,
            category=category,
            requires_human_approval=requires_human_approval,
            discount_allowed=discount_allowed,
            active=True,
            created_at=self._now(),
            updated_at=self._now(),
        )
        self._session.add(service)
        self._session.flush()

        self._log_change(
            entity_type="catalog_service",
            entity_id=service.id,
            action="create",
            old_value=None,
            new_value={"name": service.name, "active": service.active},
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return service

    def update_service(
        self,
        service_id: UUID,
        name: str | None,
        description: str | None,
        category: str | None,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        service = self._session.query(CatalogService).filter_by(id=service_id).first()
        if not service:
            raise ValueError("Serviço não encontrado")

        old_val = {
            "name": service.name,
            "description": service.description,
            "category": service.category,
        }
        if name is not None:
            if not name.strip():
                raise ValueError("Nome não pode ser vazio")
            service.name = name.strip()
        if description is not None:
            service.description = description
        if category is not None:
            service.category = category

        service.updated_at = self._now()
        self._session.flush()

        self._log_change(
            entity_type="catalog_service",
            entity_id=service.id,
            action="update",
            old_value=old_val,
            new_value={
                "name": service.name,
                "description": service.description,
                "category": service.category,
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return service
def update_service_rules(
        self,
        service_id: UUID,
        requires_human_approval: bool | None,
        discount_allowed: bool | None,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        service = self._session.query(CatalogService).filter_by(id=service_id).first()
        if not service:
            raise ValueError("Serviço não encontrado")

        old_val = {
            "requires_human_approval": service.requires_human_approval,
            "discount_allowed": service.discount_allowed,
        }
        if requires_human_approval is not None:
            service.requires_human_approval = requires_human_approval
        if discount_allowed is not None:
            service.discount_allowed = discount_allowed

        service.updated_at = self._now()
        self._session.flush()

        self._log_change(
            entity_type="catalog_service",
            entity_id=service.id,
            action="rules_update",
            old_value=old_val,
            new_value={
                "requires_human_approval": service.requires_human_approval,
                "discount_allowed": service.discount_allowed,
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return service

    def deactivate_service(self, service_id: UUID, actor_id: str, actor_role: str) -> Any:
        service = self._session.query(CatalogService).filter_by(id=service_id).first()
        if not service:
            raise ValueError("Serviço não encontrado")

        old_val = {"active": service.active}
        service.active = False
        service.updated_at = self._now()
        self._session.flush()

        self._log_change(
            entity_type="catalog_service",
            entity_id=service.id,
            action="deactivate",
            old_value=old_val,
            new_value={"active": False},
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return service

    # --- Prices ---
    def add_price(
        self,
        service_id: UUID,
        price_cents: int,
        valid_from: datetime,
        valid_to: datetime | None,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        service = self._session.query(CatalogService).filter_by(id=service_id).first()
        if not service:
            raise ValueError("Serviço não encontrado")

        price = CatalogPrice(
            service_id=service_id,
            price_cents=price_cents,
            valid_from=valid_from,
            valid_to=valid_to,
            active=True,
            created_at=self._now(),
            updated_at=self._now(),
        )
        self._session.add(price)
        self._session.flush()

        self._log_change(
            entity_type="catalog_price",
            entity_id=price.id,
            action="create",
            old_value=None,
            new_value={
                "service_id": str(service_id),
                "price_cents": price_cents,
                "valid_from": valid_from.isoformat(),
                "valid_to": valid_to.isoformat() if valid_to else None,
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return price

    def update_price(
        self,
        price_id: UUID,
        price_cents: int | None,
        valid_from: datetime | None,
        valid_to: datetime | None,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        price = self._session.query(CatalogPrice).filter_by(id=price_id).first()
        if not price:
            raise ValueError("Preço não encontrado")

        old_val = {
            "price_cents": price.price_cents,
            "valid_from": price.valid_from.isoformat(),
            "valid_to": price.valid_to.isoformat() if price.valid_to else None,
        }
        if price_cents is not None:
            price.price_cents = price_cents
        if valid_from is not None:
            price.valid_from = valid_from
        if valid_to is not None:
            price.valid_to = valid_to

        price.updated_at = self._now()
        self._session.flush()

        self._log_change(
            entity_type="catalog_price",
            entity_id=price.id,
            action="update",
            old_value=old_val,
            new_value={
                "price_cents": price.price_cents,
                "valid_from": price.valid_from.isoformat(),
                "valid_to": price.valid_to.isoformat() if price.valid_to else None,
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return price

    def deactivate_price(self, price_id: UUID, actor_id: str, actor_role: str) -> Any:
        price = self._session.query(CatalogPrice).filter_by(id=price_id).first()
        if not price:
            raise ValueError("Preço não encontrado")

        old_val = {"active": price.active}
        price.active = False
        price.updated_at = self._now()
        self._session.flush()

        self._log_change(
            entity_type="catalog_price",
            entity_id=price.id,
            action="deactivate",
            old_value=old_val,
            new_value={"active": False},
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return price
# --- FAQs ---
    def add_faq(
        self,
        service_id: UUID,
        question: str,
        answer: str,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        service = self._session.query(CatalogService).filter_by(id=service_id).first()
        if not service:
            raise ValueError("Serviço não encontrado")

        faq = FaqEntry(
            service_id=service_id,
            question=question.strip(),
            answer=answer.strip(),
            active=True,
            created_at=self._now(),
            updated_at=self._now(),
        )
        self._session.add(faq)
        self._session.flush()

        self._log_change(
            entity_type="catalog_faq",
            entity_id=faq.id,
            action="create",
            old_value=None,
            new_value={"question": faq.question},
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return faq

    def update_faq(
        self,
        faq_id: UUID,
        question: str | None,
        answer: str | None,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        faq = self._session.query(FaqEntry).filter_by(id=faq_id).first()
        if not faq:
            raise ValueError("FAQ não encontrado")

        old_val = {"question": faq.question}
        if question is not None:
            if not question.strip():
                raise ValueError("A pergunta não pode ser vazia")
            faq.question = question.strip()
        if answer is not None:
            if not answer.strip():
                raise ValueError("A resposta não pode ser vazia")
            faq.answer = answer.strip()

        faq.updated_at = self._now()
        self._session.flush()

        self._log_change(
            entity_type="catalog_faq",
            entity_id=faq.id,
            action="update",
            old_value=old_val,
            new_value={"question": faq.question},
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return faq

    def deactivate_faq(self, faq_id: UUID, actor_id: str, actor_role: str) -> Any:
        faq = self._session.query(FaqEntry).filter_by(id=faq_id).first()
        if not faq:
            raise ValueError("FAQ não encontrado")

        old_val = {"active": faq.active}
        faq.active = False
        faq.updated_at = self._now()
        self._session.flush()

        self._log_change(
            entity_type="catalog_faq",
            entity_id=faq.id,
            action="deactivate",
            old_value=old_val,
            new_value={"active": False},
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return faq
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


class CatalogRepository(Protocol):
    """Port de domínio para gerenciar operações de persistência do Catálogo e Regras Comerciais."""

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
        ...

    def update_service(
        self,
        service_id: UUID,
        name: str | None,
        description: str | None,
        category: str | None,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        ...

    def update_service_rules(
        self,
        service_id: UUID,
        requires_human_approval: bool | None,
        discount_allowed: bool | None,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        ...

    def deactivate_service(self, service_id: UUID, actor_id: str, actor_role: str) -> Any:
        ...

    def add_price(
        self,
        service_id: UUID,
        price_cents: int,
        valid_from: datetime,
        valid_to: datetime | None,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        ...

    def update_price(
        self,
        price_id: UUID,
        price_cents: int | None,
        valid_from: datetime | None,
        valid_to: datetime | None,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        ...

    def deactivate_price(self, price_id: UUID, actor_id: str, actor_role: str) -> Any:
        ...

    def add_faq(
        self,
        service_id: UUID,
        question: str,
        answer: str,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        ...

    def update_faq(
        self,
        faq_id: UUID,
        question: str | None,
        answer: str | None,
        actor_id: str,
        actor_role: str,
    ) -> Any:
        ...

    def deactivate_faq(self, faq_id: UUID, actor_id: str, actor_role: str) -> Any:
        ...
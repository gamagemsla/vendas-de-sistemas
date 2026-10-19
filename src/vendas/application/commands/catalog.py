from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from vendas.domain.ports import Clock
from vendas.domain.ports.catalog import CatalogRepository


class CatalogValidationError(ValueError):
    pass


@dataclass(slots=True)
class CatalogMutation:
    entity_type: str
    entity_id: UUID
    action: str
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    actor_id: str | None = None
    actor_role: str = "admin"


class CreateServiceCommand:
    def __init__(self, catalog_repo: CatalogRepository, clock: Clock) -> None:
        self._catalog_repo = catalog_repo
        self._clock = clock

    def execute(
        self,
        *,
        name: str,
        description: str = "",
        category: str | None = None,
        requires_human_approval: bool = False,
        discount_allowed: bool = False,
        actor_id: str | None = None,
        actor_role: str = "admin",
    ) -> Any:
        if not name.strip():
            raise CatalogValidationError("Nome do serviço é obrigatório")

        return self._catalog_repo.add_service(
            name=name.strip(),
            description=description,
            category=category,
            requires_human_approval=requires_human_approval,
            discount_allowed=discount_allowed,
            actor_id=actor_id or "system",
            actor_role=actor_role,
        )


class UpdateServiceCommand:
    def __init__(self, catalog_repo: CatalogRepository, clock: Clock) -> None:
        self._catalog_repo = catalog_repo
        self._clock = clock

    def execute(
        self,
        *,
        service_id: UUID,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        actor_id: str | None = None,
        actor_role: str = "admin",
    ) -> Any:
        return self._catalog_repo.update_service(
            service_id=service_id,
            name=name,
            description=description,
            category=category,
            actor_id=actor_id or "system",
            actor_role=actor_role,
        )


class UpdateServiceRulesCommand:
    def __init__(self, catalog_repo: CatalogRepository, clock: Clock) -> None:
        self._catalog_repo = catalog_repo
        self._clock = clock

    def execute(
        self,
        *,
        service_id: UUID,
        requires_human_approval: bool | None = None,
        discount_allowed: bool | None = None,
        actor_id: str | None = None,
        actor_role: str = "admin",
    ) -> Any:
        return self._catalog_repo.update_service_rules(
            service_id=service_id,
            requires_human_approval=requires_human_approval,
            discount_allowed=discount_allowed,
            actor_id=actor_id or "system",
            actor_role=actor_role,
        )


class DeactivateServiceCommand:
    def __init__(self, catalog_repo: CatalogRepository, clock: Clock) -> None:
        self._catalog_repo = catalog_repo
        self._clock = clock

    def execute(
        self,
        *,
        service_id: UUID,
        actor_id: str | None = None,
        actor_role: str = "admin",
    ) -> Any:
        return self._catalog_repo.deactivate_service(
            service_id=service_id,
            actor_id=actor_id or "system",
            actor_role=actor_role,
        )


class CreatePriceCommand:
    def __init__(self, catalog_repo: CatalogRepository, clock: Clock) -> None:
        self._catalog_repo = catalog_repo
        self._clock = clock

    def execute(
        self,
        *,
        service_id: UUID,
        price_cents: int,
        valid_from: datetime,
        valid_to: datetime | None = None,
        actor_id: str | None = None,
        actor_role: str = "admin",
    ) -> Any:
        if price_cents <= 0:
            raise CatalogValidationError("Preço deve ser maior que zero")

        try:
            return self._catalog_repo.add_price(
                service_id=service_id,
                price_cents=price_cents,
                valid_from=valid_from,
                valid_to=valid_to,
                actor_id=actor_id or "system",
                actor_role=actor_role,
            )
        except ValueError as exc:
            raise CatalogValidationError(str(exc)) from exc


class UpdatePriceCommand:
    def __init__(self, catalog_repo: CatalogRepository, clock: Clock) -> None:
        self._catalog_repo = catalog_repo
        self._clock = clock

    def execute(
        self,
        *,
        price_id: UUID,
        price_cents: int | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        actor_id: str | None = None,
        actor_role: str = "admin",
    ) -> Any:
        if price_cents is not None and price_cents <= 0:
            raise CatalogValidationError("Preço deve ser maior que zero")

        try:
            return self._catalog_repo.update_price(
                price_id=price_id,
                price_cents=price_cents,
                valid_from=valid_from,
                valid_to=valid_to,
                actor_id=actor_id or "system",
                actor_role=actor_role,
            )
        except ValueError as exc:
            raise CatalogValidationError(str(exc)) from exc


class DeactivatePriceCommand:
    def __init__(self, catalog_repo: CatalogRepository, clock: Clock) -> None:
        self._catalog_repo = catalog_repo
        self._clock = clock

    def execute(
        self,
        *,
        price_id: UUID,
        actor_id: str | None = None,
        actor_role: str = "admin",
    ) -> Any:
        return self._catalog_repo.deactivate_price(
            price_id=price_id,
            actor_id=actor_id or "system",
            actor_role=actor_role,
        )


class CreateFaqCommand:
    def __init__(self, catalog_repo: CatalogRepository, clock: Clock) -> None:
        self._catalog_repo = catalog_repo
        self._clock = clock

    def execute(
        self,
        *,
        service_id: UUID,
        question: str,
        answer: str,
        actor_id: str | None = None,
        actor_role: str = "admin",
    ) -> Any:
        if not question.strip() or not answer.strip():
            raise CatalogValidationError("Pergunta e resposta são obrigatórias")

        return self._catalog_repo.add_faq(
            service_id=service_id,
            question=question.strip(),
            answer=answer.strip(),
            actor_id=actor_id or "system",
            actor_role=actor_role,
        )


class UpdateFaqCommand:
    def __init__(self, catalog_repo: CatalogRepository, clock: Clock) -> None:
        self._catalog_repo = catalog_repo
        self._clock = clock

    def execute(
        self,
        *,
        faq_id: UUID,
        question: str | None = None,
        answer: str | None = None,
        actor_id: str | None = None,
        actor_role: str = "admin",
    ) -> Any:
        return self._catalog_repo.update_faq(
            faq_id=faq_id,
            question=question,
            answer=answer,
            actor_id=actor_id or "system",
            actor_role=actor_role,
        )


class DeactivateFaqCommand:
    def __init__(self, catalog_repo: CatalogRepository, clock: Clock) -> None:
        self._catalog_repo = catalog_repo
        self._clock = clock

    def execute(
        self,
        *,
        faq_id: UUID,
        actor_id: str | None = None,
        actor_role: str = "admin",
    ) -> Any:
        return self._catalog_repo.deactivate_faq(
            faq_id=faq_id,
            actor_id=actor_id or "system",
            actor_role=actor_role,
        )

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from vendas.application.commands.catalog import (
    CreateFaqCommand,
    CreatePriceCommand,
    CreateServiceCommand,
    DeactivateFaqCommand,
    DeactivatePriceCommand,
    DeactivateServiceCommand,
    UpdateFaqCommand,
    UpdatePriceCommand,
    UpdateServiceCommand,
    UpdateServiceRulesCommand,
)
from vendas.application.queries.catalog import CatalogPreviewQuery, ListCatalogServicesQuery
from vendas.bootstrap.container import container
from vendas.domain.ports.catalog import CatalogRepository
from vendas.domain.ports.knowledge_base import KnowledgeBasePort

router = APIRouter(prefix="/catalog", tags=["Catálogo e Knowledge Base"])


class AuthContext(BaseModel):
    user_id: str | None = None
    role: str = "operator"


def get_db() -> Generator[Session, None, None]:
    session = container.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_catalog_repository(session: Annotated[Session, Depends(get_db)]) -> CatalogRepository:
    return container.get_catalog_repository(session)


def get_knowledge_base(session: Annotated[Session, Depends(get_db)]) -> KnowledgeBasePort:
    return container.get_knowledge_base(session)


def get_current_user(request: Request) -> AuthContext:
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    role = request.headers.get("x-user-role", "operator")
    user_id = request.headers.get("x-user-id", "system")

    return AuthContext(user_id=user_id, role=role)


def require_admin(request: Request) -> AuthContext:
    user = get_current_user(request)
    if user.role.lower() != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente")
    return user


class ServiceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    category: str | None = None
    requires_human_approval: bool = False
    discount_allowed: bool = False


class ServiceUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    requires_human_approval: bool | None = None
    discount_allowed: bool | None = None


class PriceCreateRequest(BaseModel):
    service_id: UUID
    price_cents: int = Field(..., gt=0)
    valid_from: datetime
    valid_to: datetime | None = None


class PriceUpdateRequest(BaseModel):
    price_cents: int | None = Field(default=None, gt=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class FaqCreateRequest(BaseModel):
    service_id: UUID
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class FaqUpdateRequest(BaseModel):
    question: str | None = None
    answer: str | None = None


@router.get("/services", status_code=status.HTTP_200_OK)
def list_services(
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(get_current_user)],
    kb: Annotated[KnowledgeBasePort, Depends(get_knowledge_base)],
) -> list[dict[str, Any]]:
    _ = user
    return ListCatalogServicesQuery(kb).execute()


@router.post("/services", status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreateRequest,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_admin)],
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> dict[str, Any]:
    cmd = CreateServiceCommand(catalog_repo, container.clock)
    service = cmd.execute(
        name=payload.name,
        description=payload.description,
        category=payload.category,
        requires_human_approval=payload.requires_human_approval,
        discount_allowed=payload.discount_allowed,
        actor_id=user.user_id or "system",
        actor_role=user.role,
    )
    session.commit()
    return {"id": str(service.id), "status": "created"}


@router.patch("/services/{service_id}", status_code=status.HTTP_200_OK)
def update_service(
    service_id: UUID,
    payload: ServiceUpdateRequest,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_admin)],
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> dict[str, Any]:
    cmd = UpdateServiceCommand(catalog_repo, container.clock)
    service = cmd.execute(
        service_id=service_id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        actor_id=user.user_id or "system",
        actor_role=user.role,
    )
    session.commit()
    return {"id": str(service.id), "status": "updated"}


@router.patch("/services/{service_id}/rules", status_code=status.HTTP_200_OK)
def update_service_rules(
    service_id: UUID,
    payload: ServiceUpdateRequest,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_admin)],
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> dict[str, Any]:
    cmd = UpdateServiceRulesCommand(catalog_repo, container.clock)
    service = cmd.execute(
        service_id=service_id,
        requires_human_approval=payload.requires_human_approval,
        discount_allowed=payload.discount_allowed,
        actor_id=user.user_id or "system",
        actor_role=user.role,
    )
    session.commit()
    return {"id": str(service.id), "status": "updated"}


@router.delete("/services/{service_id}", status_code=status.HTTP_200_OK)
def deactivate_service(
    service_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_admin)],
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> dict[str, Any]:
    cmd = DeactivateServiceCommand(catalog_repo, container.clock)
    service = cmd.execute(
        service_id=service_id,
        actor_id=user.user_id or "system",
        actor_role=user.role,
    )
    session.commit()
    return {"id": str(service.id), "status": "deactivated"}


@router.post("/prices", status_code=status.HTTP_201_CREATED)
def create_price(
    payload: PriceCreateRequest,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_admin)],
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> dict[str, Any]:
    cmd = CreatePriceCommand(catalog_repo, container.clock)
    price = cmd.execute(
        service_id=payload.service_id,
        price_cents=payload.price_cents,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        actor_id=user.user_id or "system",
        actor_role=user.role,
    )
    session.commit()
    return {"id": str(price.id), "status": "created"}


@router.patch("/prices/{price_id}", status_code=status.HTTP_200_OK)
def update_price(
    price_id: UUID,
    payload: PriceUpdateRequest,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_admin)],
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> dict[str, Any]:
    cmd = UpdatePriceCommand(catalog_repo, container.clock)
    price = cmd.execute(
        price_id=price_id,
        price_cents=payload.price_cents,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        actor_id=user.user_id or "system",
        actor_role=user.role,
    )
    session.commit()
    return {"id": str(price.id), "status": "updated"}


@router.delete("/prices/{price_id}", status_code=status.HTTP_200_OK)
def deactivate_price(
    price_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_admin)],
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> dict[str, Any]:
    cmd = DeactivatePriceCommand(catalog_repo, container.clock)
    price = cmd.execute(
        price_id=price_id,
        actor_id=user.user_id or "system",
        actor_role=user.role,
    )
    session.commit()
    return {"id": str(price.id), "status": "deactivated"}


@router.post("/faqs", status_code=status.HTTP_201_CREATED)
def create_faq(
    payload: FaqCreateRequest,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_admin)],
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> dict[str, Any]:
    cmd = CreateFaqCommand(catalog_repo, container.clock)
    faq = cmd.execute(
        service_id=payload.service_id,
        question=payload.question,
        answer=payload.answer,
        actor_id=user.user_id or "system",
        actor_role=user.role,
    )
    session.commit()
    return {"id": str(faq.id), "status": "created"}


@router.patch("/faqs/{faq_id}", status_code=status.HTTP_200_OK)
def update_faq(
    faq_id: UUID,
    payload: FaqUpdateRequest,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_admin)],
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> dict[str, Any]:
    cmd = UpdateFaqCommand(catalog_repo, container.clock)
    faq = cmd.execute(
        faq_id=faq_id,
        question=payload.question,
        answer=payload.answer,
        actor_id=user.user_id or "system",
        actor_role=user.role,
    )
    session.commit()
    return {"id": str(faq.id), "status": "updated"}


@router.delete("/faqs/{faq_id}", status_code=status.HTTP_200_OK)
def deactivate_faq(
    faq_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_admin)],
    catalog_repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> dict[str, Any]:
    cmd = DeactivateFaqCommand(catalog_repo, container.clock)
    faq = cmd.execute(
        faq_id=faq_id,
        actor_id=user.user_id or "system",
        actor_role=user.role,
    )
    session.commit()
    return {"id": str(faq.id), "status": "deactivated"}


@router.post("/preview", status_code=status.HTTP_200_OK)
def preview_knowledge_base(
    payload: dict[str, str],
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(get_current_user)],
    kb: Annotated[KnowledgeBasePort, Depends(get_knowledge_base)],
) -> dict[str, Any]:
    _ = user
    question = payload.get("question", "")
    return CatalogPreviewQuery(kb).execute(question)

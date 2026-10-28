"""Rotas da API para direitos do titular de dados (LGPD)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict

from vendas.application.commands.lead_data_subject import (
    AnonymizeLeadDataCommand,
    AnonymizeLeadDataHandler,
    DeleteLeadDataCommand,
    DeleteLeadDataHandler,
    ExportLeadDataCommand,
    ExportLeadDataHandler,
)
from vendas.domain.ports.auth import Role
from vendas.interfaces.api.deps import require_role

router = APIRouter(prefix="/lgpd", tags=["LGPD"])


class LeadDataExportResponse(BaseModel):
    """Response model para exportação de dados do lead."""

    model_config = ConfigDict(from_attributes=True)

    lead_id: UUID
    phone: str
    email: str | None
    name: str | None
    cnpj: str | None
    status: str
    created_at: str
    updated_at: str
    inbound_events: list[dict[str, object]]
    outbox_messages: list[dict[str, object]]
    cadence_enrollments: list[dict[str, object]]
    conversation_history: list[dict[str, object]]
    suppression_records: list[dict[str, object]]


def get_export_lead_data_handler() -> ExportLeadDataHandler:
    """Dependency para obter handler de exportação."""
    from vendas.bootstrap.container import container

    return container.get_export_lead_data_handler()


def get_anonymize_lead_data_handler() -> AnonymizeLeadDataHandler:
    """Dependency para obter handler de anonimização."""
    from vendas.bootstrap.container import container

    return container.get_anonymize_lead_data_handler()


def get_delete_lead_data_handler() -> DeleteLeadDataHandler:
    """Dependency para obter handler de exclusão."""
    from vendas.bootstrap.container import container

    return container.get_delete_lead_data_handler()


@router.get(
    "/leads/{lead_id}/export",
    response_model=LeadDataExportResponse,
    summary="Exportar dados do lead (LGPD Art. 18 - Direito de Acesso)",
    description="Retorna todos os dados pessoais associados a um lead específico.",
)
async def export_lead_data(
    lead_id: UUID,
    _: Annotated[None, Depends(require_role(Role.ADMIN))],
    handler: Annotated[ExportLeadDataHandler, Depends(get_export_lead_data_handler)],
) -> LeadDataExportResponse:
    """Exporta todos os dados do lead para atendimento ao direito de acesso."""
    command = ExportLeadDataCommand(lead_id=lead_id)
    result = await handler.handle(command)

    return LeadDataExportResponse(
        lead_id=result.lead_id,
        phone=result.phone,
        email=result.email,
        name=result.name,
        cnpj=result.cnpj,
        status=result.status,
        created_at=result.created_at.isoformat() if result.created_at else "",
        updated_at=result.updated_at.isoformat() if result.updated_at else "",
        inbound_events=result.inbound_events,
        outbox_messages=result.outbox_messages,
        cadence_enrollments=result.cadence_enrollments,
        conversation_history=result.conversation_history,
        suppression_records=result.suppression_records,
    )


@router.post(
    "/leads/{lead_id}/anonymize",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Anonimizar dados do lead (LGPD Art. 18 - Direito ao Esquecimento)",
    description="Anonimiza dados pessoais do lead mantendo integridade referencial.",
)
async def anonymize_lead_data(
    lead_id: UUID,
    _: Annotated[None, Depends(require_role(Role.ADMIN))],
    handler: Annotated[AnonymizeLeadDataHandler, Depends(get_anonymize_lead_data_handler)],
) -> None:
    """Anonimiza dados pessoais do lead."""
    command = AnonymizeLeadDataCommand(lead_id=lead_id)
    await handler.handle(command)


@router.delete(
    "/leads/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir dados do lead (LGPD Art. 18 - Direito à Exclusão)",
    description="Exclui permanentemente todos os dados do lead (cascata).",
)
async def delete_lead_data(
    lead_id: UUID,
    _: Annotated[None, Depends(require_role(Role.ADMIN))],
    handler: Annotated[DeleteLeadDataHandler, Depends(get_delete_lead_data_handler)],
) -> None:
    """Exclui permanentemente todos os dados do lead."""
    command = DeleteLeadDataCommand(lead_id=lead_id)
    await handler.handle(command)

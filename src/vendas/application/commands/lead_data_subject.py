"""Casos de uso para direitos do titular de dados (LGPD)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from vendas.domain.ports.lead_data_subject import LeadDataExport, LeadDataSubjectPort
from vendas.domain.ports.uow import UnitOfWork


@dataclass(frozen=True, slots=True)
class ExportLeadDataCommand:
    """Comando para exportar todos os dados de um lead."""

    lead_id: UUID


@dataclass(frozen=True, slots=True)
class AnonymizeLeadDataCommand:
    """Comando para anonimizar dados pessoais de um lead."""

    lead_id: UUID


@dataclass(frozen=True, slots=True)
class DeleteLeadDataCommand:
    """Comando para excluir permanentemente todos os dados de um lead."""

    lead_id: UUID


class ExportLeadDataHandler:
    """Handler para exportação de dados do lead."""

    def __init__(self, port: LeadDataSubjectPort) -> None:
        self._port = port

    async def handle(self, command: ExportLeadDataCommand) -> LeadDataExport:
        return await self._port.export(command.lead_id)


class AnonymizeLeadDataHandler:
    """Handler para anonimização de dados do lead."""

    def __init__(self, port: LeadDataSubjectPort, uow: UnitOfWork) -> None:
        self._port = port
        self._uow = uow

    async def handle(self, command: AnonymizeLeadDataCommand) -> None:
        with self._uow:
            await self._port.anonymize(command.lead_id)
            self._uow.commit()


class DeleteLeadDataHandler:
    """Handler para exclusão de dados do lead."""

    def __init__(self, port: LeadDataSubjectPort, uow: UnitOfWork) -> None:
        self._port = port
        self._uow = uow

    async def handle(self, command: DeleteLeadDataCommand) -> None:
        with self._uow:
            await self._port.delete(command.lead_id)
            self._uow.commit()
